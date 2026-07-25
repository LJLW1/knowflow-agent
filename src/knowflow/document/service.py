"""Document ingestion and index lifecycle."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from knowflow.document.parsers import DocumentParser
from knowflow.document.splitter import StructureAwareSplitter
from knowflow.domain.models import DocumentRecord, DocumentStatus
from knowflow.persistence.repositories import KnowledgeRepository
from knowflow.retrieval.store import VectorStore


@dataclass(frozen=True, slots=True)
class IngestResult:
    document: DocumentRecord
    chunks_indexed: int
    skipped: bool


class DocumentService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        vector_store: VectorStore,
        *,
        parser: DocumentParser | None = None,
        splitter: StructureAwareSplitter | None = None,
    ) -> None:
        self.repository = repository
        self.vector_store = vector_store
        self.parser = parser or DocumentParser()
        self.splitter = splitter or StructureAwareSplitter()

    def ingest(self, project_id: str, filename: str, data: bytes) -> IngestResult:
        digest = hashlib.sha256(data).hexdigest()
        duplicate = self.repository.find_document_by_hash(project_id, digest)
        if duplicate is not None:
            return IngestResult(duplicate, chunks_indexed=0, skipped=True)

        parsed = self.parser.parse_bytes(filename, data)
        document_id = f"doc_{uuid.uuid5(uuid.NAMESPACE_URL, f'{project_id}:{filename}').hex[:24]}"
        existing = self.repository.get_document(project_id, document_id)
        now = datetime.now(UTC)
        version_id = f"idx_{uuid.uuid4().hex[:24]}"
        document = DocumentRecord(
            document_id=document_id,
            project_id=project_id,
            filename=filename,
            media_type=parsed.media_type,
            content_sha256=digest,
            status=DocumentStatus.INDEXED,
            index_version_id=version_id,
            size_bytes=len(data),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        chunks = self.splitter.split(
            parsed,
            project_id=project_id,
            document_id=document_id,
            index_version_id=version_id,
        )
        previous_chunks = (
            self.repository.list_chunks(project_id, document_id) if existing else []
        )
        staging_document = (
            existing.model_copy(
                update={
                    "status": DocumentStatus.INDEXING,
                    "updated_at": now,
                }
            )
            if existing
            else document.model_copy(
                update={
                    "status": DocumentStatus.INDEXING,
                    "index_version_id": None,
                }
            )
        )
        self.repository.save_document(staging_document)
        try:
            self.vector_store.replace_document(project_id, document_id, chunks)
            self.repository.commit_document_index(document, chunks)
        except Exception:
            try:
                if previous_chunks:
                    self.vector_store.replace_document(
                        project_id,
                        document_id,
                        previous_chunks,
                    )
                else:
                    self.vector_store.delete_document(project_id, document_id)
            except Exception as rollback_error:
                raise RuntimeError("INDEX_ROLLBACK_FAILED") from rollback_error
            if existing:
                self.repository.save_document(existing)
            else:
                self.repository.delete_document(project_id, document_id)
            raise
        return IngestResult(document, chunks_indexed=len(chunks), skipped=False)

    def reconcile_incomplete_indexes(self, project_id: str) -> int:
        recovered = 0
        for document in self.repository.list_documents(project_id):
            if document.status is not DocumentStatus.INDEXING:
                continue
            chunks = self.repository.list_chunks(project_id, document.document_id)
            if chunks:
                self.vector_store.replace_document(
                    project_id,
                    document.document_id,
                    chunks,
                )
                self.repository.save_document(
                    document.model_copy(
                        update={
                            "status": DocumentStatus.INDEXED,
                            "index_version_id": chunks[0].index_version_id,
                            "updated_at": datetime.now(UTC),
                        }
                    )
                )
            else:
                self.vector_store.delete_document(project_id, document.document_id)
                self.repository.delete_document(project_id, document.document_id)
            recovered += 1
        return recovered

    def delete(self, project_id: str, document_id: str) -> None:
        self.vector_store.delete_document(project_id, document_id)
        self.repository.delete_document(project_id, document_id)
