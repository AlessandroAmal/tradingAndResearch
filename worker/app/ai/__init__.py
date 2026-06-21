"""AI layer (Phase 2 / M3) — Claude called SERVER-SIDE ONLY.

The Anthropic API key lives in the worker .env (ANTHROPIC_API_KEY) and
never reaches the browser. Synthesis must always flag uncertainty and
never present predictions as certainties (CLAUDE.md §5).
"""
from .client import AIClient, build_ai_client

__all__ = ["AIClient", "build_ai_client"]
