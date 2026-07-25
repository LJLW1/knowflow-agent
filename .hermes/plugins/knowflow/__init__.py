"""KnowFlow project plugin for Hermes Agent 0.18.2."""

from knowflow.integrations.hermes_plugin import register_tools


def register(ctx) -> None:
    register_tools(ctx)
