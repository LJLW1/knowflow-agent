from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from knowflow.domain.models import (
    AnswerResult,
    Citation,
    DocumentRecord,
    DocumentStatus,
    MediaType,
    TaskRun,
    TaskStatus,
)


def test_document_rejects_unknown_media_type() -> None:
    with pytest.raises(ValidationError):
        DocumentRecord(
            document_id="doc-1",
            project_id="project-1",
            filename="malware.exe",
            media_type="exe",
            content_sha256="a" * 64,
            status=DocumentStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


def test_answer_refusal_has_no_citations() -> None:
    result = AnswerResult(
        answer="知识库中没有足够证据。",
        citations=[],
        answerable=False,
        refusal_reason="INSUFFICIENT_EVIDENCE",
        retrieval_hits=[],
        prompt_version="answer/v1",
        model=None,
        usage=None,
        latency_ms=2.5,
        trace_id="trace-1",
    )

    assert result.answerable is False
    assert result.citations == []


def test_answerable_result_requires_a_citation() -> None:
    with pytest.raises(ValidationError):
        AnswerResult(
            answer="部署前需要运行回归测试。",
            citations=[],
            answerable=True,
            refusal_reason=None,
            retrieval_hits=[],
            prompt_version="answer/v1",
            model="fake",
            usage=None,
            latency_ms=2.5,
            trace_id="trace-1",
        )


def test_citation_rejects_an_empty_quote() -> None:
    with pytest.raises(ValidationError):
        Citation(
            citation_id="c1",
            document_id="doc-1",
            chunk_id="chunk-1",
            filename="runbook.txt",
            page_start=None,
            page_end=None,
            section_path=["发布检查"],
            quote="   ",
        )


def test_task_run_uses_explicit_interrupted_state() -> None:
    task = TaskRun(
        task_id="task-1",
        project_id="project-1",
        status=TaskStatus.INTERRUPTED,
        request={"mode": "knowledge_report"},
        plan=[],
        tool_events=[],
        result=None,
        error_code="PROCESS_RESTARTED",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        trace_id="trace-1",
    )

    assert task.status.value == "interrupted"
    assert MediaType.MARKDOWN.value == "markdown"

