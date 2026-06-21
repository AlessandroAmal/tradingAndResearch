"""Thin wrapper around the Anthropic SDK.

Server-side only. Centralises the client + a JSON-constrained call helper
so tagging and briefing share one safe path. Structured outputs
(`output_config.format`) guarantee the response is valid JSON, and we
still parse defensively so an API hiccup degrades to empty/None instead
of crashing the job.
"""
from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from ..logging_setup import get_logger

log = get_logger("ai.client")


class AIClient:
    def __init__(self, client: anthropic.Anthropic) -> None:
        self._client = client

    def json_call(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any] | None:
        """Make one Claude call constrained to `schema`; return parsed dict.

        Returns None on any failure (caller decides the safe default).
        """
        try:
            resp = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.APIError as exc:
            log.error("Claude API error (%s): %s", model, exc)
            return None
        except Exception as exc:  # noqa: BLE001 — never crash the job
            log.error("Claude call failed (%s): %s", model, exc)
            return None

        if resp.stop_reason == "refusal":
            log.warning("Claude refused the request (%s)", model)
            return None

        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError) as exc:
            log.error("Could not parse Claude JSON (%s): %s", model, exc)
            return None
        return data if isinstance(data, dict) else None


def build_ai_client() -> AIClient:
    """Construct the Anthropic client from ANTHROPIC_API_KEY (worker .env)."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY must be set for the AI layer (see .env.example)."
        )
    return AIClient(anthropic.Anthropic(api_key=key))
