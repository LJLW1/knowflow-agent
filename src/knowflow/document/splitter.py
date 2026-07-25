"""Structure-aware character splitter with source location propagation."""

from __future__ import annotations

import hashlib
import re

from knowflow.document.parsers import ParsedDocument
from knowflow.domain.models import ChunkRecord


def approximate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", text)))


def make_chunk(
    project_id: str,
    document_id: str,
    index_version_id: str,
    ordinal: int,
    text: str,
    section_path: list[str],
    *,
    page_start: int | None = None,
    page_end: int | None = None,
) -> ChunkRecord:
    digest = hashlib.sha256(
        f"{project_id}:{document_id}:{index_version_id}:{ordinal}:{text}".encode()
    ).hexdigest()[:24]
    return ChunkRecord(
        chunk_id=f"chk_{digest}",
        project_id=project_id,
        document_id=document_id,
        index_version_id=index_version_id,
        ordinal=ordinal,
        text=text.strip(),
        token_count=approximate_tokens(text),
        page_start=page_start,
        page_end=page_end,
        section_path=section_path,
    )


class StructureAwareSplitter:
    def __init__(self, chunk_size: int = 800, overlap: int = 120) -> None:
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("INVALID_CHUNK_CONFIGURATION")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(
        self,
        parsed: ParsedDocument,
        *,
        project_id: str,
        document_id: str,
        index_version_id: str,
    ) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        ordinal = 0
        step = self.chunk_size - self.overlap
        for section in parsed.sections:
            text = section.text.strip()
            for start in range(0, len(text), step):
                part = text[start : start + self.chunk_size].strip()
                if not part:
                    continue
                chunks.append(
                    make_chunk(
                        project_id,
                        document_id,
                        index_version_id,
                        ordinal,
                        part,
                        section.heading_path,
                        page_start=section.page_start,
                        page_end=section.page_end,
                    )
                )
                ordinal += 1
                if start + self.chunk_size >= len(text):
                    break
        return chunks
