"""Shared domain contracts used by the API, plugins, and evaluation runner."""

from knowflow.domain.models import (
    AnswerResult,
    ChunkRecord,
    Citation,
    DocumentRecord,
    RetrievalHit,
    TaskRun,
)

__all__ = [
    "AnswerResult",
    "ChunkRecord",
    "Citation",
    "DocumentRecord",
    "RetrievalHit",
    "TaskRun",
]
