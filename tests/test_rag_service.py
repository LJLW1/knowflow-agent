import pytest

from knowflow.document.splitter import make_chunk
from knowflow.rag.llm import FakeLLM, LLMNotConfigured, OpenAICompatibleLLM
from knowflow.rag.service import RAGService
from knowflow.retrieval.embedding import HashEmbedding
from knowflow.retrieval.hybrid import HybridRetriever
from knowflow.retrieval.store import InMemoryVectorStore


def build_retriever() -> HybridRetriever:
    store = InMemoryVectorStore(HashEmbedding(128))
    chunks = [make_chunk("p1", "d1", "v1", 0, "发布前必须运行回归测试。", ["发布检查"])]
    store.add(chunks)
    retriever = HybridRetriever(store)
    retriever.replace_project_chunks("p1", chunks)
    return retriever


def test_no_api_key_raises_explicit_configuration_error() -> None:
    service = RAGService(build_retriever(), OpenAICompatibleLLM(api_key=None))
    with pytest.raises(LLMNotConfigured, match="LLM_NOT_CONFIGURED"):
        service.answer("p1", "发布前做什么？", trace_id="t1")


def test_fake_llm_answer_cites_only_retrieved_chunk() -> None:
    service = RAGService(build_retriever(), FakeLLM())
    result = service.answer("p1", "发布前做什么？", trace_id="t1")

    assert result.answerable is True
    assert result.citations[0].chunk_id == result.retrieval_hits[0].chunk.chunk_id
    assert result.citations[0].section_path == ["发布检查"]


def test_unknown_answer_is_a_refusal_without_citations() -> None:
    service = RAGService(build_retriever(), FakeLLM(force_refusal=True))
    result = service.answer("p1", "CEO 的生日？", trace_id="t1")

    assert result.answerable is False
    assert result.citations == []
    assert result.refusal_reason == "INSUFFICIENT_EVIDENCE"

