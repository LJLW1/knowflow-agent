"""Vector store adapters with mandatory project filters."""

from __future__ import annotations

import numpy as np
from typing import Protocol

from knowflow.domain.models import ChunkRecord, RetrievalHit
from knowflow.retrieval.embedding import EmbeddingModel


class VectorStore(Protocol):
    def add(self, chunks: list[ChunkRecord]) -> None: ...

    def delete_document(self, project_id: str, document_id: str) -> None: ...

    def search(self, *, project_id: str, query: str, top_k: int) -> list[RetrievalHit]: ...

    def project_chunks(self, project_id: str) -> list[ChunkRecord]: ...


class InMemoryVectorStore:
    def __init__(self, embedding: EmbeddingModel) -> None:
        self.embedding = embedding
        self._chunks: dict[str, ChunkRecord] = {}
        self._vectors: dict[str, list[float]] = {}

    def add(self, chunks: list[ChunkRecord]) -> None:
        vectors = self.embedding.encode([chunk.text for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._chunks[chunk.chunk_id] = chunk
            self._vectors[chunk.chunk_id] = vector

    def delete_document(self, project_id: str, document_id: str) -> None:
        targets = [
            chunk_id
            for chunk_id, chunk in self._chunks.items()
            if chunk.project_id == project_id and chunk.document_id == document_id
        ]
        for chunk_id in targets:
            del self._chunks[chunk_id]
            del self._vectors[chunk_id]

    def search(self, *, project_id: str, query: str, top_k: int) -> list[RetrievalHit]:
        query_vector = np.asarray(self.embedding.encode([query])[0])
        scored: list[tuple[float, ChunkRecord]] = []
        for chunk_id, chunk in self._chunks.items():
            if chunk.project_id != project_id:
                continue
            score = float(np.dot(query_vector, np.asarray(self._vectors[chunk_id])))
            scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [
            RetrievalHit(chunk=chunk, score=score, rank=rank, retrieval_method="dense")
            for rank, (score, chunk) in enumerate(scored[:top_k], start=1)
        ]

    def project_chunks(self, project_id: str) -> list[ChunkRecord]:
        return [chunk for chunk in self._chunks.values() if chunk.project_id == project_id]
