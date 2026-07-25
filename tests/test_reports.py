from datetime import date

from knowflow.workflow.reports import KnowledgeReportService


def test_daily_report_generation_is_idempotent(tmp_path) -> None:
    service = KnowledgeReportService(tmp_path)
    first = service.generate("p1", date(2026, 7, 25), ["architecture.md"])
    second = service.generate("p1", date(2026, 7, 25), ["architecture.md"])

    assert first.created is True
    assert second.created is False
    assert first.path == second.path
    assert first.path.read_text().count("# 知识库更新日报") == 1
