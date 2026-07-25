"""Persistent Chroma adapter with project/document/index metadata."""

from __future__ import annotations

import chromadb

from knowflow.domain.models import ChunkRecord, RetrievalHit
from knowflow.retrieval.embedding import EmbeddingModel


class ChromaVectorStore:
    def __init__(self, path: str, embedding: EmbeddingModel, collection: str = "knowflow") -> None:
        self.embedding = embedding
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(collection)

    def add(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=self.embedding.encode([chunk.text for chunk in chunks]),
            metadatas=[
                {
                    "project_id": chunk.project_id,
                    "document_id": chunk.document_id,
                    "index_version_id": chunk.index_version_id,
                    "ordinal": chunk.ordinal,
                    "page_start": chunk.page_start or 0,
                    "page_end": chunk.page_end or 0,
                    "section_path": " > ".join(chunk.section_path),
                }
                for chunk in chunks
            ],
        )

    def delete_document(self, project_id: str, document_id: str) -> None:
        self.collection.delete(
            where={"$and": [{"project_id": project_id}, {"document_id": document_id}]}
        )

    def search(self, *, project_id: str, query: str, top_k: int) -> list[RetrievalHit]:
        result = self.collection.query(
            query_embeddings=self.embedding.encode([query]),
            n_results=top_k,
            where={"project_id": project_id},
            include=["documents", "metadatas", "distances"],
        )
        hits: list[RetrievalHit] = []
        for rank, (chunk_id, text, metadata, distance) in enumerate(
            zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
                strict=True,
            ),
            start=1,
        ):
            chunk = ChunkRecord(
                chunk_id=chunk_id,
                project_id=str(metadata["project_id"]),
                document_id=str(metadata["document_id"]),
                index_version_id=str(metadata["index_version_id"]),
                ordinal=int(metadata["ordinal"]),
                text=text,
                token_count=max(1, len(text)),
                page_start=int(metadata["page_start"]) or None,
                page_end=int(metadata["page_end"]) or None,
                section_path=str(metadata["section_path"]).split(" > ")
                if metadata["section_path"]
                else [],
            )
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    score=1.0 / (1.0 + float(distance)),
                    rank=rank,
                    retrieval_method="dense_chroma",
                )
            )
        return hits

    def project_chunks(self, project_id: str) -> list[ChunkRecord]:
        result = self.collection.get(where={"project_id": project_id}, include=["documents", "metadatas"])
        chunks: list[ChunkRecord] = []
        for chunk_id, text, metadata in zip(
            result["ids"], result["documents"], result["metadatas"], strict=True
        ):
            chunks.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    project_id=str(metadata["project_id"]),
                    document_id=str(metadata["document_id"]),
                    index_version_id=str(metadata["index_version_id"]),
                    ordinal=int(metadata["ordinal"]),
                    text=text,
                    token_count=max(1, len(text)),
                    page_start=int(metadata["page_start"]) or None,
                    page_end=int(metadata["page_end"]) or None,
                    section_path=str(metadata["section_path"]).split(" > ")
                    if metadata["section_path"]
                    else [],
                )
            )
        return chunks
