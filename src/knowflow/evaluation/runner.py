"""Run local retrieval evaluation without cloud model calls."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import statistics
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowflow.document.service import DocumentService
from knowflow.persistence.database import Database
from knowflow.persistence.repositories import KnowledgeRepository
from knowflow.retrieval.embedding import BGEEmbedding, HashEmbedding
from knowflow.retrieval.hybrid import HybridRetriever
from knowflow.retrieval.store import InMemoryVectorStore

ROOT = Path(__file__).parents[3]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_evaluation(
    *,
    embedding_backend: str = "hash",
    top_k: int = 6,
    output_path: Path | None = None,
) -> dict[str, Any]:
    embedding = BGEEmbedding() if embedding_backend == "bge" else HashEmbedding(512)
    cases = load_cases(ROOT / "evaluation" / "questions.jsonl")
    with tempfile.TemporaryDirectory(prefix="knowflow-eval-") as temporary:
        database = Database(f"sqlite:///{Path(temporary) / 'evaluation.db'}")
        database.initialize()
        repository = KnowledgeRepository(database)
        repository.create_project("atlas", "Atlas demo")
        store = InMemoryVectorStore(embedding)
        documents = DocumentService(repository, store)

        corpus = sorted(
            path
            for path in (ROOT / "demo_corpus").rglob("*")
            if path.is_file() and path.suffix.lower() in {".pdf", ".docx", ".md", ".txt"}
        )
        index_started = time.perf_counter()
        document_names: dict[str, str] = {}
        chunk_count = 0
        for path in corpus:
            ingest_result = documents.ingest("atlas", path.name, path.read_bytes())
            document_names[ingest_result.document.document_id] = path.name
            chunk_count += ingest_result.chunks_indexed
        index_ms = (time.perf_counter() - index_started) * 1000

        chunks = repository.list_chunks("atlas")
        hybrid = HybridRetriever(store)
        hybrid.replace_project_chunks("atlas", chunks)
        scored_cases = [case for case in cases if case["expected_documents"]]

        def evaluate(method: str) -> dict[str, Any]:
            latencies: list[float] = []
            recalls: list[float] = []
            details: list[dict[str, Any]] = []
            source_checks = 0
            valid_sources = 0
            for case in scored_cases:
                started = time.perf_counter()
                hits = (
                    store.search(project_id="atlas", query=case["question"], top_k=top_k)
                    if method == "dense"
                    else hybrid.search("atlas", case["question"], top_k=top_k)
                )
                latencies.append((time.perf_counter() - started) * 1000)
                retrieved = {document_names[hit.chunk.document_id] for hit in hits}
                expected = set(case["expected_documents"])
                recall = len(expected & retrieved) / len(expected)
                recalls.append(recall)
                for hit in hits:
                    source_checks += 1
                    if (
                        hit.chunk.chunk_id
                        and hit.chunk.document_id in document_names
                        and hit.chunk.project_id == "atlas"
                    ):
                        valid_sources += 1
                details.append(
                    {
                        "id": case["id"],
                        "expected": sorted(expected),
                        "retrieved": sorted(retrieved),
                        "recall": recall,
                    }
                )
            return {
                "recall_at_k": statistics.fmean(recalls),
                "mean_latency_ms": statistics.fmean(latencies),
                "p95_latency_ms": percentile(latencies, 0.95),
                "cases": len(scored_cases),
                "retrieval_source_checks": source_checks,
                "retrieval_source_integrity": (
                    valid_sources / source_checks if source_checks else 0.0
                ),
                "details": details,
            }

        dense = evaluate("dense")
        optimized = evaluate("hybrid")
        max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes; Linux reports KiB.
        rss_mb = max_rss / (1024 * 1024) if platform.system() == "Darwin" else max_rss / 1024
        evaluation_result = {
            "run_at": datetime.now(UTC).isoformat(),
            "dataset_cases": len(cases),
            "scored_retrieval_cases": len(scored_cases),
            "embedding_backend": embedding_backend,
            "top_k": top_k,
            "documents": len(corpus),
            "chunks": chunk_count,
            "index_time_ms": index_ms,
            "peak_rss_mb": rss_mb,
            "retrieval_source_integrity": optimized["retrieval_source_integrity"],
            "retrieval_source_checks": optimized["retrieval_source_checks"],
            "citation_correctness": "待测量",
            "dense": dense,
            "hybrid": optimized,
            "cloud_metrics": {
                "answer_faithfulness": "待测量",
                "hallucination_rate": "待测量",
                "tool_selection_accuracy": "待测量",
                "task_completion_rate": "待测量",
                "token_api_cost": "待测量",
                "end_to_end_latency": "待测量",
                "error_recovery_rate": "待测量",
            },
            "limitations": [
                "HashEmbedding 仅用于 CI 时，结果不能代表 BGE 语义检索质量。",
                "retrieval_source_integrity 只验证检索存储自洽，不代表回答引用正确率。",
            ],
        }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(evaluation_result, ensure_ascii=False, indent=2) + "\n"
        )
    return evaluation_result


def write_markdown(result: dict[str, Any], path: Path) -> None:
    dense = result["dense"]
    hybrid = result["hybrid"]
    dense_row = (
        f"| 稠密检索 | {dense['recall_at_k']:.4f} | "
        f"{dense['mean_latency_ms']:.2f} ms | {dense['p95_latency_ms']:.2f} ms |"
    )
    hybrid_row = (
        f"| BM25 + 稠密 RRF | {hybrid['recall_at_k']:.4f} | "
        f"{hybrid['mean_latency_ms']:.2f} ms | {hybrid['p95_latency_ms']:.2f} ms |"
    )
    content = f"""# KnowFlow Agent 本地评测报告

- 运行时间：{result['run_at']}
- 数据集：{result['dataset_cases']} 条
- 检索计分样本：{result['scored_retrieval_cases']} 条
- Embedding：{result['embedding_backend']}
- Top-K：{result['top_k']}
- 文档 / Chunk：{result['documents']} / {result['chunks']}
- 索引耗时：{result['index_time_ms']:.2f} ms
- 峰值 RSS：{result['peak_rss_mb']:.2f} MB

| 方案 | Recall@K | 平均检索延迟 | P95 检索延迟 |
|---|---:|---:|---:|
{dense_row}
{hybrid_row}

检索来源完整性为 {result['retrieval_source_integrity']:.0%}。
该指标只验证检索结果的项目、文档和 Chunk 标识自洽。

引用正确率、回答忠实度、幻觉率、工具选择准确率、完整任务完成率、
Token/API 成本、云模型端到端延迟和错误恢复率：**待测量**。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding", choices=["hash", "bge"], default="hash")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/evaluation/latest.json")
    args = parser.parse_args()
    result = run_evaluation(
        embedding_backend=args.embedding,
        top_k=args.top_k,
        output_path=args.output,
    )
    write_markdown(result, args.output.with_suffix(".md"))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
