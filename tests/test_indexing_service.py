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
    second = service.ingest("p1", "architecture.md", b"# Storage\nSQLite and Chroma are persistent.")

    assert first.document.document_id == second.document.document_id
    assert first.document.index_version_id != second.document.index_version_id
    assert len(repository.list_index_versions("p1", first.document.document_id)) == 2


def test_delete_removes_metadata_chunks_and_vectors(tmp_path) -> None:
    service, repository, store = build_service(tmp_path)
    result = service.ingest("p1", "runbook.txt", b"Run regression tests before release.")

    service.delete("p1", result.document.document_id)

    assert repository.get_document("p1", result.document.document_id) is None
    assert repository.list_chunks("p1", result.document.document_id) == []
    assert store.project_chunks("p1") == []
