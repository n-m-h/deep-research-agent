"""
RAG interactive test script: upload docs, search, compare strategies
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.rag import RAGService  # noqa: E402
from config import config


def main():
    parser = argparse.ArgumentParser(description="RAG Test & Debug Tool")
    parser.add_argument("action", nargs="?", default="status",
                        choices=["status", "upload", "search", "delete", "clear", "eval", "compare"])
    parser.add_argument("--file", "-f", help="File path to upload")
    parser.add_argument("--query", "-q", help="Search query")
    parser.add_argument("--top-k", type=int, default=5, help="Top K results")
    parser.add_argument("--doc-id", help="Document ID to delete")
    parser.add_argument("--strategy", help="Chunk strategy for eval: recursive/heading/parent_child")

    args = parser.parse_args()
    rag = RAGService()

    if args.action == "status":
        print(f"\n{'='*50}")
        print(f"🔍 RAG 服务状态")
        print(f"{'='*50}")
        print(f"  启用: {config.rag_enabled}")
        print(f"  文档数: {rag.document_count}")
        print(f"  分块策略: {config.rag_chunk_strategy}")
        print(f"  重排序: {config.rag_use_rerank}")
        print(f"  Embedding模型: {config.rag_embedding_model}")
        print(f"  Rerank模型: {config.rag_rerank_model}")
        print(f"  Chunk大小: {config.rag_chunk_size}")
        print(f"  候选K: {config.rag_candidate_k}")
        print(f"  Top K: {config.rag_top_k}")

        if rag.has_documents:
            print(f"\n  📄 已索引文档:")
            for doc in rag.list_documents():
                print(f"    - {doc['filename']} ({doc['chunk_count']} chunks, id: {doc['doc_id']})")

    elif args.action == "upload":
        if not args.file:
            print("❌ 请指定文件路径: --file <path>")
            return
        if not os.path.exists(args.file):
            print(f"❌ 文件不存在: {args.file}")
            return

        print(f"\n📤 上传文档: {args.file}")
        result = rag.index_document(args.file)
        print(f"  ✅ 完成: {json.dumps(result, ensure_ascii=False, indent=2)}")

    elif args.action == "search":
        if not args.query:
            print("❌ 请指定搜索查询: --query <query>")
            return
        if not rag.has_documents:
            print("⚠️  没有已索引的文档，请先上传")
            return

        print(f"\n🔎 搜索: \"{args.query}\" (strategy={config.rag_chunk_strategy}, rerank={config.rag_use_rerank})")
        result = rag.search_debug(args.query, args.top_k)
        print(f"  延迟: {result['latency_ms']}ms | 总文档数: {result['total_documents']}")

        for i, r in enumerate(result["results"], 1):
            print(f"\n  [{i}] 📄 {r['source_doc']}  (score: {r['relevance_score']:.4f})")
            if r.get("section_path"):
                print(f"      章节: {r['section_path']}")
            print(f"      摘要: {r['snippet'][:150]}...")

        if args.action == "search":
            print(f"\n  📊 配置文件:")
            print(f"    strategy={result['strategy']}, rerank={result['use_rerank']}")

    elif args.action == "delete":
        if not args.doc_id:
            print("❌ 请指定文档ID: --doc-id <id>")
            return
        success = rag.delete_document(args.doc_id)
        print(f"{'✅' if success else '❌'} 删除文档 {args.doc_id}: {'成功' if success else '未找到'}")

    elif args.action == "clear":
        confirm = input("⚠️  确定要清除所有文档? (yes/no): ")
        if confirm == "yes":
            rag.clear_all()
            print("✅ 已清除所有文档")
        else:
            print("已取消")

    elif args.action == "eval":
        from evaluation.run_evaluation import RAGEvaluator, format_report
        test_set_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evaluation", "test_queries.json")
        if not os.path.exists(test_set_path):
            print(f"❌ 测试集不存在: {test_set_path}")
            return

        evaluator = RAGEvaluator(rag)
        test_queries = evaluator.load_test_set(test_set_path)

        if args.strategy:
            config.rag_chunk_strategy = args.strategy
            rag._processor.strategy = args.strategy

        result = evaluator.evaluate_retrieval(test_queries)
        print(format_report(result))

    elif args.action == "compare":
        from evaluation.run_evaluation import RAGEvaluator
        test_set_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evaluation", "test_queries.json")
        if not os.path.exists(test_set_path):
            print(f"❌ 测试集不存在: {test_set_path}")
            return

        evaluator = RAGEvaluator(rag)
        test_queries = evaluator.load_test_set(test_set_path)

        strategies = ["recursive", "heading", "parent_child"]
        if args.strategy:
            strategies = [s.strip() for s in args.strategy.split(",")]

        print(f"\n{'='*60}")
        print(f"📊 策略 A/B 对比")
        print(f"{'='*60}")
        print(f"\n{'策略':<20} {'Precision':<12} {'Recall':<12} {'F1':<12} {'MRR':<12}")
        print(f"{'-'*68}")

        current_strategy = config.rag_chunk_strategy
        for strategy in strategies:
            config.rag_chunk_strategy = strategy
            rag._processor.strategy = strategy
            result = evaluator.evaluate_retrieval(test_queries)
            m = result["metrics"]
            print(f"{strategy:<20} {m['avg_precision']:<12.3f} {m['avg_recall']:<12.3f} {m['f1']:<12.3f} {m['avg_mrr']:<12.3f}")

        config.rag_chunk_strategy = current_strategy


if __name__ == "__main__":
    main()
