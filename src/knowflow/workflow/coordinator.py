"""Three-child workflow with timeout and partial-failure semantics.

Hermes owns delegate_task and subagent lifecycle. This module owns only the
bounded plan, result normalization, and degradation policy used by KnowFlow.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(slots=True)
class StepResult:
    status: str
    output: dict[str, str] | None = None
    error_code: str | None = None


@dataclass(slots=True)
class WorkflowResult:
    status: str
    steps: dict[str, StepResult]


class WorkflowCoordinator:
    def __init__(self, *, timeout_seconds: float = 45) -> None:
        self.timeout_seconds = timeout_seconds

    async def run(
        self,
        *,
        retrieval: Callable[[], Awaitable[dict[str, str]]],
        github_collection: Callable[[], Awaitable[dict[str, str]]],
        citation_validation: Callable[[], Awaitable[dict[str, str]]],
    ) -> WorkflowResult:
        operations = {
            "knowledge_retrieval": retrieval,
            "github_collection": github_collection,
            "citation_validation": citation_validation,
        }

        async def execute(operation: Callable[[], Awaitable[dict[str, str]]]) -> StepResult:
            try:
                output = await asyncio.wait_for(operation(), timeout=self.timeout_seconds)
                return StepResult(status="succeeded", output=output)
            except TimeoutError:
                return StepResult(status="failed", error_code="CHILD_TIMEOUT")
            except Exception:
                return StepResult(status="failed", error_code="CHILD_FAILED")

        results = await asyncio.gather(*(execute(operation) for operation in operations.values()))
        steps = dict(zip(operations, results, strict=True))
        failures = sum(result.status == "failed" for result in results)
        status = "succeeded" if failures == 0 else ("failed" if failures == 3 else "partial")
        return WorkflowResult(status=status, steps=steps)
