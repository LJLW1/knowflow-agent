from knowflow.document.splitter import make_chunk
from knowflow.retrieval.embedding import HashEmbedding
from knowflow.retrieval.hybrid import HybridRetriever, reciprocal_rank_fusion
from knowflow.retrieval.store import InMemoryVectorStore


def test_vector_store_requires_project_filter() -> None:
    store = InMemoryVectorStore(HashEmbedding(dimensions=64))
    store.add(
        [
            make_chunk("p1", "d1", "v1", 0, "API uses FastAPI.", ["Architecture"]),
            make_chunk("p2", "d2", "v1", 0, "The secret launch code.", ["Confidential"]),
        ]
    )
    hits = store.search(project_id="p1", query="launch code", top_k=5)
    assert {hit.chunk.project_id for hit in hits} <= {"p1"}


def test_rrf_rewards_items_found_by_both_retrievers() -> None:
    scores = reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60)
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["c"]


def test_hybrid_retrieval_returns_stable_ranked_hits() -> None:
    store = InMemoryVectorStore(HashEmbedding(dimensions=128))
    chunks = [
        make_chunk("p1", "d1", "v1", 0, "发布前必须运行回归测试。", ["发布"]),
        make_chunk("p1", "d1", "v1", 1, "数据库使用 SQLite 保存元数据。", ["架构"]),
        make_chunk("p1", "d2", "v1", 0, "事故发生后首先执行服务隔离。", ["事故"]),
    ]
    store.add(chunks)
    retriever = HybridRetriever(store)
    retriever.replace_project_chunks("p1", chunks)

    hits = retriever.search("p1", "发布 回归测试", top_k=2)
    assert hits[0].chunk.ordinal == 0
    assert hits[0].retrieval_method == "hybrid_rrf"
    assert [hit.rank for hit in hits] == [1, 2]
