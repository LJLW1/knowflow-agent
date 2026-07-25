"""Project-scoped repository operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update

from knowflow.domain.models import (
    DocumentRecord,
    DocumentStatus,
    ChunkRecord,
    MediaType,
    TaskRun,
    TaskStatus,
)
from knowflow.persistence.database import Database
from knowflow.persistence.tables import (
    ChunkRow,
    DocumentRow,
    IndexVersionRow,
    ProjectRow,
    TaskRunRow,
)


class KnowledgeRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_project(self, project_id: str, name: str) -> None:
        with self.database.session() as session:
            existing = session.get(ProjectRow, project_id)
            if existing is None:
                session.add(ProjectRow(project_id=project_id, name=name))

    def save_document(self, document: DocumentRecord) -> None:
        values = document.model_dump(mode="python")
        values["media_type"] = document.media_type.value
        values["status"] = document.status.value
        with self.database.session() as session:
            row = session.scalar(
                select(DocumentRow).where(
                    DocumentRow.project_id == document.project_id,
                    DocumentRow.document_id == document.document_id,
                )
            )
            if row is None:
                session.add(DocumentRow(**values))
                return
            for key, value in values.items():
                setattr(row, key, value)

    def get_document(self, project_id: str, document_id: str) -> DocumentRecord | None:
        with self.database.session() as session:
            row = session.scalar(
                select(DocumentRow).where(
                    DocumentRow.project_id == project_id,
                    DocumentRow.document_id == document_id,
                )
            )
            return self._document(row) if row else None

    def list_documents(self, project_id: str) -> list[DocumentRecord]:
        with self.database.session() as session:
            rows = session.scalars(
                select(DocumentRow)
                .where(DocumentRow.project_id == project_id)
                .order_by(DocumentRow.created_at, DocumentRow.document_id)
            ).all()
            return [self._document(row) for row in rows]

    def find_document_by_hash(
        self, project_id: str, content_sha256: str
    ) -> DocumentRecord | None:
        with self.database.session() as session:
            row = session.scalar(
                select(DocumentRow).where(
                    DocumentRow.project_id == project_id,
                    DocumentRow.content_sha256 == content_sha256,
                    DocumentRow.status != DocumentStatus.DELETED.value,
                )
            )
            return self._document(row) if row else None

    def create_task(
        self,
        *,
        task_id: str,
        project_id: str,
        status: TaskStatus,
        request: dict[str, Any],
        trace_id: str,
    ) -> TaskRun:
        now = datetime.now(UTC)
        row = TaskRunRow(
            task_id=task_id,
            project_id=project_id,
            status=status.value,
            request=request,
            plan=[],
            tool_events=[],
            result=None,
            error_code=None,
            started_at=now if status is TaskStatus.RUNNING else None,
            finished_at=None,
            trace_id=trace_id,
        )
        with self.database.session() as session:
            session.add(row)
            session.flush()
            return self._task(row)

    def get_task(self, project_id: str, task_id: str) -> TaskRun | None:
        with self.database.session() as session:
            row = session.scalar(
                select(TaskRunRow).where(
                    TaskRunRow.project_id == project_id,
                    TaskRunRow.task_id == task_id,
                )
            )
            return self._task(row) if row else None

    def interrupt_running_tasks(self) -> int:
        with self.database.session() as session:
            result = session.execute(
                update(TaskRunRow)
                .where(TaskRunRow.status == TaskStatus.RUNNING.value)
                .values(
                    status=TaskStatus.INTERRUPTED.value,
                    error_code="PROCESS_RESTARTED",
                    finished_at=datetime.now(UTC),
                )
            )
            return int(result.rowcount or 0)

    def save_index_version(
        self,
        project_id: str,
        document_id: str,
        index_version_id: str,
        content_sha256: str,
    ) -> None:
        with self.database.session() as session:
            session.add(
                IndexVersionRow(
                    project_id=project_id,
                    document_id=document_id,
                    index_version_id=index_version_id,
                    content_sha256=content_sha256,
                )
            )

    def list_index_versions(self, project_id: str, document_id: str) -> list[str]:
        with self.database.session() as session:
            return list(
                session.scalars(
                    select(IndexVersionRow.index_version_id)
                    .where(
                        IndexVersionRow.project_id == project_id,
                        IndexVersionRow.document_id == document_id,
                    )
                    .order_by(IndexVersionRow.created_at)
                ).all()
            )

    def save_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        with self.database.session() as session:
            session.add_all(
                [
                    ChunkRow(
                        **chunk.model_dump(mode="python"),
                    )
                    for chunk in chunks
                ]
            )

    def list_chunks(self, project_id: str, document_id: str | None = None) -> list[ChunkRecord]:
        query = select(ChunkRow).where(ChunkRow.project_id == project_id)
        if document_id is not None:
            query = query.where(ChunkRow.document_id == document_id)
        query = query.order_by(ChunkRow.document_id, ChunkRow.ordinal)
        with self.database.session() as session:
            rows = session.scalars(query).all()
            return [
                ChunkRecord(
                    chunk_id=row.chunk_id,
                    project_id=row.project_id,
                    document_id=row.document_id,
                    index_version_id=row.index_version_id,
                    ordinal=row.ordinal,
                    text=row.text,
                    token_count=row.token_count,
                    page_start=row.page_start,
                    page_end=row.page_end,
                    section_path=row.section_path,
                )
                for row in rows
            ]

    def delete_document(self, project_id: str, document_id: str) -> None:
        with self.database.session() as session:
            session.execute(
                delete(ChunkRow).where(
                    ChunkRow.project_id == project_id,
                    ChunkRow.document_id == document_id,
                )
            )
            session.execute(
                delete(IndexVersionRow).where(
                    IndexVersionRow.project_id == project_id,
                    IndexVersionRow.document_id == document_id,
                )
            )
            session.execute(
                delete(DocumentRow).where(
                    DocumentRow.project_id == project_id,
                    DocumentRow.document_id == document_id,
                )
            )

    @staticmethod
    def _document(row: DocumentRow) -> DocumentRecord:
        return DocumentRecord(
            document_id=row.document_id,
            project_id=row.project_id,
            filename=row.filename,
            media_type=MediaType(row.media_type),
            content_sha256=row.content_sha256,
            status=DocumentStatus(row.status),
            index_version_id=row.index_version_id,
            size_bytes=row.size_bytes,
            error_code=row.error_code,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _task(row: TaskRunRow) -> TaskRun:
        return TaskRun(
            task_id=row.task_id,
            project_id=row.project_id,
            status=TaskStatus(row.status),
            request=row.request,
            plan=row.plan,
            tool_events=row.tool_events,
            result=row.result,
            error_code=row.error_code,
            started_at=row.started_at,
            finished_at=row.finished_at,
            trace_id=row.trace_id,
        )
