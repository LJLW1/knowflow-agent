import pytest

from knowflow.document.service import DocumentService
from knowflow.persistence.database import Database
from knowflow.persistence.repositories import KnowledgeRepository
from knowflow.retrieval.embedding import HashEmbedding
from knowflow.retrieval.store import InMemoryVectorStore


def build_service(tmp_path) -> tuple[DocumentService, KnowledgeRepository, InMemoryVectorStore]:
    database = Database(f"sqlite:///{tmp_path / 'knowflow.db'}")
    database.initialize()
    repository = KnowledgeRepository(database)
    repository.create_project("p1", "Demo")
    store = InMemoryVectorStore(HashEmbedding(64))
    return DocumentService(repository, store), repository, store


def test_duplicate_upload_is_skipped(tmp_path) -> None:
    service, repository, _ = build_service(tmp_path)
    first = service.ingest("p1", "architecture.md", b"# Storage\nSQLite stores metadata.")
    second = service.ingest("p1", "copy.md", b"# Storage\nSQLite stores metadata.")

    assert first.skipped is False
    assert second.skipped is True
    assert second.document.document_id == first.document.document_id
    assert len(repository.list_documents("p1")) == 1


def test_changed_file_creates_new_index_version(tmp_path) -> None:
    service, repository, _ = build_service(tmp_path)
    first = service.ingest("p1", "architecture.md", b"# Storage\nSQLite stores metadata.")
    second = service.ingest(
        "p1",
        "architecture.md",
        b"# Storage\nSQLite and Chroma are persistent.",
    )

    assert first.document.document_id == second.document.document_id
    assert first.document.index_version_id != second.document.index_version_id
    assert len(repository.list_index_versions("p1", first.document.document_id)) == 2
    active_chunks = repository.list_chunks("p1", first.document.document_id)
    assert len(active_chunks) == 1
    assert "SQLite and Chroma" in active_chunks[0].text
    assert "SQLite stores metadata" not in active_chunks[0].text


def test_delete_removes_metadata_chunks_and_vectors(tmp_path) -> None:
    service, repository, store = build_service(tmp_path)
    result = service.ingest("p1", "runbook.txt", b"Run regression tests before release.")

    service.delete("p1", result.document.document_id)

    assert repository.get_document("p1", result.document.document_id) is None
    assert repository.list_chunks("p1", result.document.document_id) == []
    assert store.project_chunks("p1") == []


def test_vector_failure_preserves_the_previous_active_index(tmp_path) -> None:
    service, repository, store = build_service(tmp_path)
    first = service.ingest("p1", "runbook.txt", b"OLD: run regression tests.")

    original_replace = store.replace_document
    should_fail = True

    def fail_replace(project_id, document_id, chunks):
        nonlocal should_fail
        if should_fail:
            should_fail = False
            raise RuntimeError("CHROMA_UNAVAILABLE")
        original_replace(project_id, document_id, chunks)

    store.replace_document = fail_replace  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="CHROMA_UNAVAILABLE"):
            service.ingest("p1", "runbook.txt", b"NEW: skip all tests.")
    finally:
        store.replace_document = original_replace  # type: ignore[method-assign]

    active = repository.get_document("p1", first.document.document_id)
    assert active is not None
    assert active.content_sha256 == first.document.content_sha256
    assert repository.list_chunks("p1", first.document.document_id)[0].text.startswith("OLD")
    assert store.project_chunks("p1")[0].text.startswith("OLD")


def test_partial_vector_replace_is_compensated(tmp_path) -> None:
    service, repository, store = build_service(tmp_path)
    first = service.ingest("p1", "runbook.txt", b"OLD: run regression tests.")

    original_replace = store.replace_document
    should_fail = True

    def replace_then_fail(project_id, document_id, chunks):
        nonlocal should_fail
        original_replace(project_id, document_id, chunks)
        if should_fail:
            should_fail = False
            raise RuntimeError("VECTOR_DELETE_FAILED")

    store.replace_document = replace_then_fail  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="VECTOR_DELETE_FAILED"):
            service.ingest("p1", "runbook.txt", b"NEW: skip all tests.")
    finally:
        store.replace_document = original_replace  # type: ignore[method-assign]

    active = repository.get_document("p1", first.document.document_id)
    assert active is not None
    assert active.content_sha256 == first.document.content_sha256
    assert repository.list_chunks("p1", first.document.document_id)[0].text.startswith("OLD")
    assert store.project_chunks("p1")[0].text.startswith("OLD")


def test_sql_commit_failure_restores_previous_vectors(tmp_path) -> None:
    service, repository, store = build_service(tmp_path)
    first = service.ingest("p1", "runbook.txt", b"OLD: run regression tests.")

    original_commit = repository.commit_document_index

    def fail_commit(document, chunks):
        raise RuntimeError("SQL_COMMIT_FAILED")

    repository.commit_document_index = fail_commit  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="SQL_COMMIT_FAILED"):
            service.ingest("p1", "runbook.txt", b"NEW: skip all tests.")
    finally:
        repository.commit_document_index = original_commit  # type: ignore[method-assign]

    active = repository.get_document("p1", first.document.document_id)
    assert active is not None
    assert active.content_sha256 == first.document.content_sha256
    assert repository.list_chunks("p1", first.document.document_id)[0].text.startswith("OLD")
    assert store.project_chunks("p1")[0].text.startswith("OLD")


def test_startup_reconciles_a_crash_between_vector_and_sql_commit(tmp_path) -> None:
    service, repository, store = build_service(tmp_path)
    first = service.ingest("p1", "runbook.txt", b"OLD: run regression tests.")

    original_commit = repository.commit_document_index

    class ProcessAbort(BaseException):
        pass

    def abort_process(document, chunks):
        raise ProcessAbort

    repository.commit_document_index = abort_process  # type: ignore[method-assign]
    try:
        with pytest.raises(ProcessAbort):
            service.ingest("p1", "runbook.txt", b"NEW: skip all tests.")
    finally:
        repository.commit_document_index = original_commit  # type: ignore[method-assign]

    interrupted = repository.get_document("p1", first.document.document_id)
    assert interrupted is not None
    assert interrupted.status.value == "indexing"
    assert store.project_chunks("p1")[0].text.startswith("NEW")

    recovered = DocumentService(repository, store).reconcile_incomplete_indexes("p1")

    assert recovered == 1
    active = repository.get_document("p1", first.document.document_id)
    assert active is not None
    assert active.status.value == "indexed"
    assert active.content_sha256 == first.document.content_sha256
    assert store.project_chunks("p1")[0].text.startswith("OLD")


def test_startup_removes_an_incomplete_first_index(tmp_path) -> None:
    service, repository, store = build_service(tmp_path)
    original_commit = repository.commit_document_index

    class ProcessAbort(BaseException):
        pass

    def abort_process(document, chunks):
        raise ProcessAbort

    repository.commit_document_index = abort_process  # type: ignore[method-assign]
    try:
        with pytest.raises(ProcessAbort):
            service.ingest("p1", "runbook.txt", b"NEW: first upload.")
    finally:
        repository.commit_document_index = original_commit  # type: ignore[method-assign]

    interrupted = repository.list_documents("p1")
    assert len(interrupted) == 1
    assert interrupted[0].status.value == "indexing"
    assert store.project_chunks("p1")

    recovered = DocumentService(repository, store).reconcile_incomplete_indexes("p1")

    assert recovered == 1
    assert repository.list_documents("p1") == []
    assert store.project_chunks("p1") == []
