"""
RAG Service: hybrid retrieval (dense+sparse), reranking, query expansion
"""
import os
import json
import hashlib
import logging
import uuid
from typing import List, Dict, Optional
from datetime import datetime

import chromadb
from chromadb.config import Settings

from ..config import config
from .document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


def _get_api_key() -> Optional[str]:
    return config.llm_api_key or os.getenv("LLM_API_KEY")


def _get_embedding(texts: List[str]) -> List[List[float]]:
    """Get embeddings from SiliconFlow API"""
    import httpx
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("LLM API key not configured")

    resp = httpx.post(
        f"{config.llm_base_url.rstrip('/')}/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": config.rag_embedding_model,
            "input": texts,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def _rerank(query: str, documents: List[str], top_n: int) -> List[Dict]:
    """Rerank via SiliconFlow cross-encoder API"""
    if not documents:
        return []

    import httpx
    api_key = _get_api_key()
    if not api_key:
        return [{"index": i, "relevance_score": 1.0 - i * 0.01} for i in range(len(documents))]

    try:
        resp = httpx.post(
            f"{config.llm_base_url.rstrip('/')}/rerank",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": config.rag_rerank_model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as e:
        logger.warning(f"Rerank failed: {e}, falling back to original order")
        return [{"index": i, "relevance_score": 1.0 - i * 0.01} for i in range(min(top_n, len(documents)))]


class RAGService:
    """RAG service: document indexing + hybrid retrieval + reranking"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        rag_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rag_storage")
        os.makedirs(rag_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=rag_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="research_docs",
            metadata={"hnsw:space": "cosine"},
        )

        self._processor = DocumentProcessor(
            strategy=config.rag_chunk_strategy,
            chunk_size=config.rag_chunk_size,
            chunk_overlap=config.rag_chunk_overlap,
            parent_chunk_size=config.rag_parent_chunk_size,
        )

        self._bm25_index = None
        self._bm25_docs = []
        self._bm25_doc_ids = []
        self._rebuild_bm25_index()

    def _rebuild_bm25_index(self):
        """Rebuild BM25 index from current ChromaDB contents"""
        try:
            all_docs = self._collection.get(include=["documents", "metadatas"])
            if not all_docs or not all_docs["documents"]:
                self._bm25_docs = []
                self._bm25_doc_ids = []
                self._bm25_index = None
                return

            self._bm25_docs = all_docs["documents"]
            self._bm25_doc_ids = all_docs["ids"]

            import jieba
            from rank_bm25 import BM25Okapi

            tokenized = []
            for doc in self._bm25_docs:
                words = list(jieba.cut(doc))
                tokenized.append(words)

            self._bm25_index = BM25Okapi(tokenized)
            logger.info(f"BM25 index rebuilt with {len(self._bm25_docs)} documents")
        except Exception as e:
            logger.warning(f"BM25 index rebuild failed: {e}")
            self._bm25_index = None

    @property
    def has_documents(self) -> bool:
        return self._collection.count() > 0

    @property
    def document_count(self) -> int:
        return self._collection.count()

    def index_document(self, file_path: str) -> Dict:
        """Index a document: parse -> chunk -> embed -> store"""
        filename = os.path.basename(file_path)
        logger.info(f"Indexing document: {filename}")

        chunks = self._processor.process(file_path)
        if not chunks:
            raise ValueError(f"No content extracted from {filename}")

        doc_id = hashlib.md5(f"{filename}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        texts = [c["text"] for c in chunks]
        metadatas = []
        for c in chunks:
            m = c["metadata"]
            m["doc_id"] = doc_id
            m["source_doc"] = filename
            m["upload_time"] = datetime.now().isoformat()
            metadatas.append(m)

        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]

        embeddings = _get_embedding(texts)

        self._collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        self._rebuild_bm25_index()

        result = {
            "doc_id": doc_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "status": "indexed",
        }
        logger.info(f"Indexed {filename}: {len(chunks)} chunks")
        return result

    def search(self, query: str, top_k: int = None) -> List[Dict]:
        """Hybrid search: dense + sparse with RRF fusion + optional reranking"""
        if not self.has_documents:
            return []

        top_k = top_k or config.rag_top_k
        candidate_k = max(config.rag_candidate_k, top_k * 3)

        # Phase 1: dense retrieval
        query_emb = _get_embedding([query])[0]
        dense_results = self._collection.query(
            query_embeddings=[query_emb],
            n_results=candidate_k,
            include=["documents", "metadatas", "distances"],
        )

        # Phase 2: sparse retrieval (BM25)
        sparse_results = self._bm25_search(query, candidate_k)

        # Phase 3: RRF fusion
        fused = self._rrf_fusion(dense_results, sparse_results, candidate_k)

        # Phase 4: build result list
        id_map = {}
        for item in dense_results["metadatas"][0] if dense_results["metadatas"] else []:
            pass

        candidates = []
        for rank_item in fused:
            doc_id = rank_item["id"]
            text = rank_item["text"]
            meta = rank_item["metadata"]

            is_parent_child = meta.get("strategy") == "parent_child" and meta.get("role") == "child"
            if is_parent_child and meta.get("parent_text"):
                display_text = meta["parent_text"]
            else:
                display_text = text

            candidates.append({
                "title": f"[个人文档] {meta.get('source_doc', 'unknown')}",
                "url": "",
                "snippet": display_text[:500],
                "text": text,
                "source": "personal_doc",
                "source_doc": meta.get("source_doc", "unknown"),
                "section_path": meta.get("section_path", ""),
                "relevance_score": rank_item["score"],
                "metadata": meta,
            })

        # Phase 5: reranking
        if config.rag_use_rerank and len(candidates) > 1:
            candidate_texts = [c["text"][:2000] for c in candidates]
            reranked = _rerank(query, candidate_texts, top_k)
            reranked_results = []
            for r in reranked:
                idx = r["index"]
                if idx < len(candidates):
                    candidates[idx]["relevance_score"] = r.get("relevance_score", candidates[idx]["relevance_score"])
                    reranked_results.append(candidates[idx])
            candidates = reranked_results
        else:
            candidates = candidates[:top_k]

        return candidates

    def _bm25_search(self, query: str, top_k: int) -> List[Dict]:
        """BM25 sparse retrieval"""
        if not self._bm25_index or not self._bm25_docs:
            return []

        import jieba
        query_tokens = list(jieba.cut(query))
        scores = self._bm25_index.get_scores(query_tokens)

        result = []
        for idx, score in enumerate(scores):
            if score > 0 and idx < len(self._bm25_docs):
                result.append({
                    "id": self._bm25_doc_ids[idx],
                    "text": self._bm25_docs[idx],
                    "score": score,
                    "rank_source": "bm25",
                })

        result.sort(key=lambda x: x["score"], reverse=True)
        return result[:top_k]

    def _rrf_fusion(self, dense_results: Dict, sparse_results: List[Dict], k: int = 60) -> List[Dict]:
        """Reciprocal Rank Fusion for combining dense and sparse results"""
        rank_scores = {}

        if dense_results and dense_results.get("ids") and dense_results["ids"][0]:
            for rank, doc_id in enumerate(dense_results["ids"][0]):
                weight = config.rag_hybrid_weight_dense
                score = weight / (k + rank + 1)
                if doc_id not in rank_scores:
                    idx = dense_results["ids"][0].index(doc_id)
                    rank_scores[doc_id] = {
                        "score": 0,
                        "id": doc_id,
                        "text": dense_results["documents"][0][idx] if dense_results.get("documents") else "",
                        "metadata": dense_results["metadatas"][0][idx] if dense_results.get("metadatas") else {},
                    }
                rank_scores[doc_id]["score"] += score

        for rank, item in enumerate(sparse_results):
            doc_id = item["id"]
            weight = config.rag_hybrid_weight_sparse
            score = weight / (k + rank + 1)
            if doc_id not in rank_scores:
                idx = self._bm25_doc_ids.index(doc_id) if doc_id in self._bm25_doc_ids else -1
                rank_scores[doc_id] = {
                    "score": 0,
                    "id": doc_id,
                    "text": item["text"],
                    "metadata": {},
                }
            rank_scores[doc_id]["score"] += score

        if dense_results and dense_results.get("metadatas") and dense_results["metadatas"][0]:
            for item in rank_scores.values():
                doc_id = item["id"]
                if doc_id in dense_results["ids"][0]:
                    idx = dense_results["ids"][0].index(doc_id)
                    if dense_results.get("metadatas") and idx < len(dense_results["metadatas"][0]):
                        item["metadata"] = dense_results["metadatas"][0][idx]

        sorted_results = sorted(rank_scores.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results

    def list_documents(self) -> List[Dict]:
        """List indexed documents"""
        if not self.has_documents:
            return []

        all_metas = self._collection.get(include=["metadatas"])
        if not all_metas or not all_metas["metadatas"]:
            return []

        seen = {}
        for meta in all_metas["metadatas"]:
            doc_id = meta.get("doc_id", "")
            source_doc = meta.get("source_doc", "unknown")
            if doc_id not in seen:
                seen[doc_id] = {
                    "doc_id": doc_id,
                    "filename": source_doc,
                    "chunk_count": 1,
                    "upload_time": meta.get("upload_time", ""),
                }
            else:
                seen[doc_id]["chunk_count"] += 1

        return list(seen.values())

    def delete_document(self, doc_id: str) -> bool:
        """Delete all chunks belonging to a document"""
        all_metas = self._collection.get(include=["metadatas"])
        if not all_metas or not all_metas["ids"]:
            return False

        ids_to_delete = []
        for idx, meta in enumerate(all_metas["metadatas"]):
            if meta.get("doc_id") == doc_id:
                ids_to_delete.append(all_metas["ids"][idx])

        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
            self._rebuild_bm25_index()
            logger.info(f"Deleted document {doc_id}: {len(ids_to_delete)} chunks")
            return True
        return False

    def clear_all(self):
        """Clear all documents"""
        all_ids = self._collection.get()["ids"]
        if all_ids:
            self._collection.delete(ids=all_ids)
        self._rebuild_bm25_index()
        logger.info("Cleared all documents")

    def search_debug(self, query: str, top_k: int = 5) -> Dict:
        """Debug search: returns detailed info for evaluation"""
        start = datetime.now()
        results = self.search(query, top_k)
        elapsed = (datetime.now() - start).total_seconds() * 1000

        return {
            "query": query,
            "results": results,
            "latency_ms": round(elapsed, 2),
            "total_documents": self.document_count,
            "strategy": config.rag_chunk_strategy,
            "use_rerank": config.rag_use_rerank,
        }
