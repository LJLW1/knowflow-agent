from datetime import UTC, datetime

from knowflow.domain.models import DocumentRecord, DocumentStatus, MediaType, TaskStatus
from knowflow.persistence.database import Database
from knowflow.persistence.repositories import KnowledgeRepository


def make_document(project_id: str, document_id: str, digest: str) -> DocumentRecord:
    now = datetime.now(UTC)
    return DocumentRecord(
        document_id=document_id,
        project_id=project_id,
        filename="architecture.md",
        media_type=MediaType.MARKDOWN,
        content_sha256=digest,
        status=DocumentStatus.INDEXED,
        index_version_id="index-1",
        created_at=now,
        updated_at=now,
    )


def test_repository_never_returns_another_projects_document(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'knowflow.db'}")
    database.initialize()
    repository = KnowledgeRepository(database)
    repository.create_project("project-a", "A")
    repository.create_project("project-b", "B")
    repository.save_document(make_document("project-a", "doc-a", "a" * 64))

    assert repository.get_document("project-b", "doc-a") is None
    assert [item.document_id for item in repository.list_documents("project-a")] == ["doc-a"]


def test_repository_finds_duplicate_content_only_inside_the_project(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'knowflow.db'}")
    database.initialize()
    repository = KnowledgeRepository(database)
    repository.create_project("project-a", "A")
    repository.create_project("project-b", "B")
    repository.save_document(make_document("project-a", "doc-a", "b" * 64))

    assert repository.find_document_by_hash("project-a", "b" * 64).document_id == "doc-a"
    assert repository.find_document_by_hash("project-b", "b" * 64) is None


def test_startup_marks_running_tasks_interrupted(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'knowflow.db'}")
    database.initialize()
    repository = KnowledgeRepository(database)
    repository.create_project("project-a", "A")
    repository.create_task(
        task_id="task-1",
        project_id="project-a",
        status=TaskStatus.RUNNING,
        request={"mode": "knowledge_report"},
        trace_id="trace-1",
    )

    changed = repository.interrupt_running_tasks()
    task = repository.get_task("project-a", "task-1")

    assert changed == 1
    assert task is not None
    assert task.status is TaskStatus.INTERRUPTED
    assert task.error_code == "PROCESS_RESTARTED"
