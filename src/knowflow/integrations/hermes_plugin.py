"""Thin HTTP adapter exposed through Hermes Tool Registry."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from knowflow.integrations.github_mcp import GitHubMCPPolicy, MCPPolicyViolation

SEARCH_SCHEMA = {
    "name": "knowledge_search",
    "description": "Search project-scoped enterprise documents and return ranked source chunks.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 6},
        },
        "required": ["project_id", "query"],
    },
}

ANSWER_SCHEMA = {
    "name": "knowledge_answer",
    "description": "Answer from project documents with source-constrained citations.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "question": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 6},
        },
        "required": ["project_id", "question"],
    },
}


def _base_url() -> str:
    return os.getenv("KNOWFLOW_API_URL", "http://127.0.0.1:8000")


def knowledge_search(args: dict[str, Any], **_: Any) -> str:
    response = httpx.post(
        f"{_base_url()}/internal/v1/search",
        json=args,
        timeout=30,
    )
    response.raise_for_status()
    return json.dumps(response.json(), ensure_ascii=False)


def knowledge_answer(args: dict[str, Any], **_: Any) -> str:
    response = httpx.post(
        f"{_base_url()}/api/v1/query",
        json=args,
        timeout=120,
    )
    response.raise_for_status()
    return json.dumps(response.json(), ensure_ascii=False)


def github_readonly_guard(
    tool_name: str = "", args: dict[str, object] | None = None, **_: Any
) -> dict[str, str] | None:
    if not tool_name.startswith("mcp_github_"):
        return None
    repository = os.getenv("KNOWFLOW_GITHUB_REPOSITORY", "LJLW1/knowflow-agent")
    try:
        GitHubMCPPolicy(repository).validate(tool_name, args or {})
    except MCPPolicyViolation as exc:
        return {"action": "block", "message": str(exc)}
    return None


def register_tools(ctx: Any) -> None:
    ctx.register_tool(
        name="knowledge_search",
        toolset="knowflow",
        schema=SEARCH_SCHEMA,
        handler=knowledge_search,
        emoji="🔎",
    )
    ctx.register_tool(
        name="knowledge_answer",
        toolset="knowflow",
        schema=ANSWER_SCHEMA,
        handler=knowledge_answer,
        emoji="📚",
    )
    if hasattr(ctx, "register_hook"):
        ctx.register_hook("pre_tool_call", github_readonly_guard)
