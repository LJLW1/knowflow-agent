"""Defense-in-depth policy for the read-only GitHub MCP integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


class MCPPolicyViolation(PermissionError):
    pass


class GitHubMCPPolicy:
    read_tools = {
        "get_file_contents",
        "list_issues",
        "issue_read",
        "list_pull_requests",
        "pull_request_read",
        "search_code",
        "search_issues",
        "get_commit",
        "list_commits",
    }

    def __init__(self, allowed_repository: str) -> None:
        owner, repository = allowed_repository.split("/", maxsplit=1)
        self.owner = owner
        self.repository = repository

    def validate(self, tool_name: str, arguments: dict[str, object]) -> None:
        normalized = tool_name.removeprefix("mcp_github_")
        if normalized not in self.read_tools:
            raise MCPPolicyViolation("WRITE_TOOL_NOT_ALLOWED")
        owner = str(arguments.get("owner", ""))
        repository = str(arguments.get("repo", arguments.get("repository", "")))
        if owner != self.owner or repository != self.repository:
            raise MCPPolicyViolation("REPOSITORY_NOT_ALLOWED")


async def run_with_timeout(awaitable: Awaitable[T], *, timeout_seconds: float) -> T:
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    except TimeoutError as exc:
        raise TimeoutError("MCP_TIMEOUT") from exc
