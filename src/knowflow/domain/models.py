"""Versioned, project-scoped domain contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MediaType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    TEXT = "text"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    INTERRUPTED = "interrupted"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class DocumentRecord(StrictModel):
    document_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    media_type: MediaType
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: DocumentStatus
    index_version_id: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class ChunkRecord(StrictModel):
    chunk_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    index_version_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    token_count: int = Field(ge=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_page_range(self) -> ChunkRecord:
        if self.page_start and self.page_end and self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class RetrievalHit(StrictModel):
    chunk: ChunkRecord
    score: float
    rank: int = Field(ge=1)
    retrieval_method: str = Field(min_length=1)


class Citation(StrictModel):
    citation_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(default_factory=list)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_quote(self) -> Citation:
        if not self.quote.strip():
            raise ValueError("citation quote must not be blank")
        return self


class UsageRecord(StrictModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_cny: float | None = Field(default=None, ge=0)


class AnswerResult(StrictModel):
    answer: str
    citations: list[Citation]
    answerable: bool
    refusal_reason: str | None
    retrieval_hits: list[RetrievalHit]
    prompt_version: str
    model: str | None
    usage: UsageRecord | None
    latency_ms: float = Field(ge=0)
    trace_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_citations(self) -> AnswerResult:
        if self.answerable and not self.citations:
            raise ValueError("answerable results require at least one citation")
        if not self.answerable and self.citations:
            raise ValueError("refusal results must not include citations")
        allowed_chunk_ids = {hit.chunk.chunk_id for hit in self.retrieval_hits}
        if allowed_chunk_ids and any(
            citation.chunk_id not in allowed_chunk_ids for citation in self.citations
        ):
            raise ValueError("citations must reference chunks supplied to the answer model")
        return self


class ToolEvent(StrictModel):
    name: str
    status: str
    duration_ms: float = Field(ge=0)
    error_code: str | None = None


class TaskRun(StrictModel):
    task_id: str
    project_id: str
    status: TaskStatus
    request: dict[str, Any]
    plan: list[dict[str, Any]]
    tool_events: list[dict[str, Any]]
    result: dict[str, Any] | None
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None
    trace_id: str
