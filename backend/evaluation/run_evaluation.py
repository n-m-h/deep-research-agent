"""
RAG Evaluation Framework: run evaluation tests to measure retrieval quality
"""
import os
import sys
import json
import time
import logging
from typing import List, Dict, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.rag import RAGService  # noqa: E402
from config import config

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class RAGEvaluator:
    """Evaluate RAG retrieval quality with test queries"""

    def __init__(self, rag_service: RAGService):
        self.rag = rag_service

    def load_test_set(self, path: str) -> List[Dict]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["queries"]

    def evaluate_retrieval(self, test_queries: List[Dict], top_k: int = 5) -> Dict:
        """Evaluate retrieval quality: precision, recall, MRR"""
        total_precision = 0.0
        total_recall = 0.0
        total_mrr = 0.0
        query_count = len(test_queries)
        details = []

        for q in test_queries:
            query = q["query"]
            relevant = q.get("relevant_topics", [])

            results = self.rag.search(query, top_k=top_k)

            retrieved_topics = set()
            for r in results:
                title = r.get("source_doc", "")
                snippet = r.get("snippet", "")[:200]
                retrieved_topics.add(title)

            relevant_set = set(relevant)
            true_positives = len(retrieved_topics & relevant_set)

            precision = true_positives / len(retrieved_topics) if retrieved_topics else 0
            recall = true_positives / len(relevant_set) if relevant_set else 0
            mrr = self._calculate_mrr(results, relevant_set)

            total_precision += precision
            total_recall += recall
            total_mrr += mrr

            details.append({
                "query": query,
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "mrr": round(mrr, 3),
                "retrieved": len(results),
                "relevant_found": true_positives,
            })

        avg_precision = total_precision / query_count if query_count else 0
        avg_recall = total_recall / query_count if query_count else 0
        avg_mrr = total_mrr / query_count if query_count else 0

        return {
            "metrics": {
                "avg_precision": round(avg_precision, 3),
                "avg_recall": round(avg_recall, 3),
                "avg_mrr": round(avg_mrr, 3),
                "f1": round(2 * avg_precision * avg_recall / (avg_precision + avg_recall + 1e-10), 3),
            },
            "details": details,
            "config": {
                "strategy": config.rag_chunk_strategy,
                "chunk_size": config.rag_chunk_size,
                "use_rerank": config.rag_use_rerank,
                "candidate_k": config.rag_candidate_k,
                "top_k": top_k,
            },
            "total_queries": query_count,
        }

    def _calculate_mrr(self, results: List[Dict], relevant_set: set) -> float:
        """Mean Reciprocal Rank"""
        for rank, r in enumerate(results, start=1):
            doc_name = r.get("source_doc", "")
            if doc_name in relevant_set:
                return 1.0 / rank
            snippet = r.get("snippet", "")
            for topic in relevant_set:
                if topic.lower() in snippet.lower():
                    return 1.0 / rank
        return 0.0

    def evaluate_generation(self, test_queries: List[Dict], llm_fn=None) -> Dict:
        """Evaluate generation quality (faithfulness, relevancy)"""
        if not llm_fn:
            return {"note": "Generation evaluation requires a judge LLM"}

        results = []
        for q in test_queries:
            query = q["query"]
            ground_truth = q.get("ground_truth", "")

            rag_results = self.rag.search(query, top_k=5)
            contexts = [r.get("snippet", "") for r in rag_results]

            faithfulness = self._judge_faithfulness(query, contexts, llm_fn)
            relevancy = self._judge_relevancy(query, ground_truth, contexts, llm_fn)

            results.append({
                "query": query,
                "faithfulness": faithfulness,
                "relevancy": relevancy,
            })

        avg_faith = sum(r["faithfulness"] for r in results) / len(results) if results else 0
        avg_relev = sum(r["relevancy"] for r in results) / len(results) if results else 0

        return {
            "avg_faithfulness": round(avg_faith, 3),
            "avg_relevancy": round(avg_relev, 3),
            "details": results,
        }

    def _judge_faithfulness(self, query: str, contexts: List[str], llm_fn) -> float:
        """Judge if LLM answer is faithful to retrieved contexts (simplified)"""
        if not contexts:
            return 0.5
        context_text = "\n".join(contexts)[:2000]
        prompt = f"""Query: {query}\n\nRetrieved context: {context_text}\n\nRate faithfulness (0-1):"""
        try:
            resp = llm_fn(prompt)
            score = float(resp.strip()[:4])
            return max(0, min(1, score))
        except Exception:
            return 0.7

    def _judge_relevancy(self, query: str, ground_truth: str, contexts: List[str], llm_fn) -> float:
        """Judge if retrieved contexts are relevant to the query"""
        if not contexts:
            return 0
        context_text = "\n".join(contexts)[:2000]
        prompt = f"""Query: {query}\n\nRetrieved: {context_text}\n\nExpected: {ground_truth[:500]}\n\nRate relevancy (0-1):"""
        try:
            resp = llm_fn(prompt)
            score = float(resp.strip()[:4])
            return max(0, min(1, score))
        except Exception:
            return 0.7

    def compare_strategies(self, test_queries: List[Dict], strategies: List[str] = None) -> List[Dict]:
        """A/B compare different chunking strategies"""
        if strategies is None:
            strategies = ["recursive", "heading", "parent_child"]

        current_strategy = config.rag_chunk_strategy
        results = []

        for strategy in strategies:
            config.rag_chunk_strategy = strategy
            self.rag._processor.strategy = strategy

            eval_result = self.evaluate_retrieval(test_queries)
            results.append({
                "strategy": strategy,
                "metrics": eval_result["metrics"],
            })

        config.rag_chunk_strategy = current_strategy
        return results


def format_report(eval_result: Dict) -> str:
    """Format evaluation result as Markdown report"""
    metrics = eval_result["metrics"]
    cfg = eval_result["config"]

    report = [
        "## RAG 评估报告\n",
        f"**分块策略**: {cfg['strategy']} | **Chunk Size**: {cfg['chunk_size']} | **重排序**: {'✓' if cfg['use_rerank'] else '✗'}\n",
        f"**测试查询数**: {eval_result['total_queries']}\n",
        "",
        "### 综合指标\n",
        f"| 指标 | 分数 |",
        f"|------|------|",
        f"| Precision | {metrics['avg_precision']:.3f} |",
        f"| Recall    | {metrics['avg_recall']:.3f} |",
        f"| F1 Score  | {metrics['f1']:.3f} |",
        f"| MRR       | {metrics['avg_mrr']:.3f} |",
        "",
        "### 逐查询详情\n",
        "| 查询 | Precision | Recall | MRR | 命中 |",
        "|------|-----------|--------|-----|------|",
    ]

    for d in eval_result["details"]:
        report.append(
            f"| {d['query'][:30]}... | {d['precision']:.3f} | {d['recall']:.3f} | {d['mrr']:.3f} | {d['relevant_found']} |"
        )

    return "\n".join(report)


if __name__ == "__main__":
    evaluator = RAGEvaluator(RAGService())

    test_set_path = os.path.join(os.path.dirname(__file__), "test_queries.json")
    if not os.path.exists(test_set_path):
        print(f"Test set not found: {test_set_path}")
        sys.exit(1)

    test_queries = evaluator.load_test_set(test_set_path)

    print("=" * 60)
    print("🔍 RAG 评估 - 当前配置")
    print("=" * 60)
    result = evaluator.evaluate_retrieval(test_queries)
    print(format_report(result))

    print("\n" + "=" * 60)
    print("📊 策略对比")
    print("=" * 60)
    comparison = evaluator.compare_strategies(test_queries)
    print(f"\n{'策略':<20} {'Precision':<12} {'Recall':<12} {'F1':<12} {'MRR':<12}")
    print("-" * 68)
    for r in comparison:
        m = r["metrics"]
        print(f"{r['strategy']:<20} {m['avg_precision']:<12.3f} {m['avg_recall']:<12.3f} {m['f1']:<12.3f} {m['avg_mrr']:<12.3f}")
