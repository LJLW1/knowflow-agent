from knowflow.domain.models import ChunkRecord
from knowflow.retrieval.chroma import ChromaVectorStore
from knowflow.retrieval.embedding import HashEmbedding


def chunk(
    *,
    chunk_id: str,
    project_id: str,
    document_id: str,
    index_version_id: str,
    text: str,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        project_id=project_id,
        document_id=document_id,
        index_version_id=index_version_id,
        ordinal=0,
        text=text,
        token_count=len(text),
        section_path=["Test"],
    )


def test_chroma_replaces_document_and_filters_by_project(tmp_path) -> None:
    store = ChromaVectorStore(str(tmp_path / "chroma"), HashEmbedding(64))
    old = chunk(
        chunk_id="old",
        project_id="p1",
        document_id="doc",
        index_version_id="v1",
        text="old release procedure",
    )
    other_project = chunk(
        chunk_id="other",
        project_id="p2",
        document_id="doc",
        index_version_id="v1",
        text="secret release procedure",
    )
    store.replace_document("p1", "doc", [old])
    store.replace_document("p2", "doc", [other_project])

    new = chunk(
        chunk_id="new",
        project_id="p1",
        document_id="doc",
        index_version_id="v2",
        text="new release procedure",
    )
    store.replace_document("p1", "doc", [new])

    assert [item.chunk_id for item in store.project_chunks("p1")] == ["new"]
    assert [item.chunk_id for item in store.project_chunks("p2")] == ["other"]
    assert {hit.chunk.project_id for hit in store.search(
        project_id="p1",
        query="release procedure",
        top_k=6,
    )} == {"p1"}
