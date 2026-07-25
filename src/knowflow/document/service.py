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
from knowflow.retrieval.store import InMemoryVectorStore


@dataclass(frozen=True, slots=True)
class IngestResult:
    document: DocumentRecord
    chunks_indexed: int
    skipped: bool


class DocumentService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        vector_store: InMemoryVectorStore,
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
        if existing is not None:
            self.vector_store.delete_document(project_id, document_id)
        self.repository.save_document(document)
        self.repository.save_index_version(project_id, document_id, version_id, digest)
        self.repository.save_chunks(chunks)
        self.vector_store.add(chunks)
        return IngestResult(document, chunks_indexed=len(chunks), skipped=False)

    def delete(self, project_id: str, document_id: str) -> None:
        self.vector_store.delete_document(project_id, document_id)
        self.repository.delete_document(project_id, document_id)
