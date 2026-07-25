import asyncio
import importlib.util
from pathlib import Path

import pytest
import yaml

from knowflow.integrations.github_mcp import (
    GitHubMCPPolicy,
    MCPPolicyViolation,
    run_with_timeout,
)
from knowflow.workflow.coordinator import WorkflowCoordinator


def test_github_mcp_policy_rejects_other_repository_and_write_tools() -> None:
    policy = GitHubMCPPolicy("LJLW1/knowflow-agent")
    with pytest.raises(MCPPolicyViolation, match="REPOSITORY_NOT_ALLOWED"):
        policy.validate("get_file_contents", {"owner": "other", "repo": "private"})
    with pytest.raises(MCPPolicyViolation, match="WRITE_TOOL_NOT_ALLOWED"):
        policy.validate(
            "create_issue",
            {"owner": "LJLW1", "repo": "knowflow-agent", "title": "no"},
        )


def test_github_mcp_policy_accepts_scoped_read() -> None:
    GitHubMCPPolicy("LJLW1/knowflow-agent").validate(
        "get_file_contents",
        {"owner": "LJLW1", "repo": "knowflow-agent", "path": "README.md"},
    )


def test_mcp_timeout_has_stable_error() -> None:
    async def slow() -> str:
        await asyncio.sleep(0.05)
        return "late"

    with pytest.raises(TimeoutError, match="MCP_TIMEOUT"):
        asyncio.run(run_with_timeout(slow(), timeout_seconds=0.001))


def test_workflow_has_at_most_three_children_and_degrades_partially() -> None:
    async def ok() -> dict[str, str]:
        return {"evidence": "ok"}

    async def fail() -> dict[str, str]:
        raise RuntimeError("external unavailable")

    coordinator = WorkflowCoordinator(timeout_seconds=1)
    result = asyncio.run(
        coordinator.run(
            retrieval=ok,
            github_collection=fail,
            citation_validation=ok,
        )
    )
    assert len(result.steps) == 3
    assert result.status == "partial"
    assert result.steps["github_collection"].error_code == "CHILD_FAILED"


def test_hermes_plugin_manifest_and_tool_registration() -> None:
    root = Path(__file__).parents[1] / ".hermes" / "plugins" / "knowflow"
    manifest = yaml.safe_load((root / "plugin.yaml").read_text())
    assert manifest["name"] == "knowflow"

    spec = importlib.util.spec_from_file_location(
        "knowflow_plugin",
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    registered: list[str] = []

    class Context:
        def register_tool(self, **kwargs) -> None:
            registered.append(kwargs["name"])

    module.register(Context())
    assert registered == ["knowledge_search", "knowledge_answer"]
