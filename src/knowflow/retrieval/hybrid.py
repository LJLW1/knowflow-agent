"""BM25 plus dense retrieval merged with reciprocal-rank fusion."""

from __future__ import annotations

from collections import defaultdict

from rank_bm25 import BM25Okapi

from knowflow.domain.models import ChunkRecord, RetrievalHit
from knowflow.retrieval.embedding import lexical_tokens
from knowflow.retrieval.store import InMemoryVectorStore


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] += 1 / (k + rank)
    return dict(scores)


class HybridRetriever:
    def __init__(self, vector_store: InMemoryVectorStore) -> None:
        self.vector_store = vector_store
        self._chunks: dict[str, list[ChunkRecord]] = {}

    def replace_project_chunks(self, project_id: str, chunks: list[ChunkRecord]) -> None:
        if any(chunk.project_id != project_id for chunk in chunks):
            raise ValueError("PROJECT_SCOPE_MISMATCH")
        self._chunks[project_id] = list(chunks)

    def search(self, project_id: str, query: str, top_k: int = 6) -> list[RetrievalHit]:
        candidates = self._chunks.get(project_id, self.vector_store.project_chunks(project_id))
        if not candidates:
            return []
        dense = self.vector_store.search(project_id=project_id, query=query, top_k=max(top_k * 3, 10))
        corpus = [lexical_tokens(chunk.text) or [""] for chunk in candidates]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(lexical_tokens(query))
        lexical = sorted(
            zip(candidates, scores, strict=True),
            key=lambda item: (-float(item[1]), item[0].chunk_id),
        )
        rrf = reciprocal_rank_fusion(
            [
                [hit.chunk.chunk_id for hit in dense],
                [chunk.chunk_id for chunk, _ in lexical],
            ]
        )
        by_id = {chunk.chunk_id: chunk for chunk in candidates}
        ordered = sorted(rrf.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        return [
            RetrievalHit(
                chunk=by_id[chunk_id],
                score=score,
                rank=rank,
                retrieval_method="hybrid_rrf",
            )
            for rank, (chunk_id, score) in enumerate(ordered, start=1)
        ]
