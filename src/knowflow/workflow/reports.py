"""Idempotent daily knowledge-base report generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReportResult:
    path: Path
    created: bool


class KnowledgeReportService:
    def __init__(self, report_root: Path | str) -> None:
        self.report_root = Path(report_root)

    def generate(
        self, project_id: str, report_date: date, changed_documents: list[str]
    ) -> ReportResult:
        directory = self.report_root / project_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{report_date.isoformat()}.md"
        content = (
            "# 知识库更新日报\n\n"
            f"- 项目：{project_id}\n"
            f"- 日期：{report_date.isoformat()}\n"
            f"- 更新文档数：{len(changed_documents)}\n\n"
            "## 更新清单\n\n"
            + ("\n".join(f"- {name}" for name in changed_documents) or "- 无")
            + "\n"
        )
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(content)
            return ReportResult(path, created=True)
        except FileExistsError:
            return ReportResult(path, created=False)
