"""Tests for AI tagging JSON handling — no real API calls.

A fake AIClient returns canned dicts so we exercise the schema build,
the safe parsing, the empty-on-uncertainty contract, and the defensive
filtering to known themes/instruments.
"""
from app.ai.tagging import build_tagging_schema, tag_news_item

THEMES = ["Fed", "China", "NVDA"]
SYMBOLS = ["^NDX", "NVDA", "GC=F"]


class FakeAI:
    """Stand-in for AIClient.json_call returning a fixed payload."""

    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def json_call(self, *, model, system, user, schema, max_tokens):
        self.calls.append({"model": model, "schema": schema, "user": user})
        return self._payload


def _tag(payload):
    ai = FakeAI(payload)
    result = tag_news_item(
        ai, model="m", title="t", source="s", summary=None,
        themes=THEMES, symbols=SYMBOLS,
    )
    return result, ai


def test_schema_constrains_to_known_values():
    schema = build_tagging_schema(THEMES, SYMBOLS)
    assert schema["properties"]["themes"]["items"]["enum"] == THEMES
    assert schema["properties"]["instruments"]["items"]["enum"] == SYMBOLS
    assert schema["additionalProperties"] is False


def test_valid_tags_pass_through():
    result, _ = _tag({"themes": ["Fed", "NVDA"], "instruments": ["NVDA"]})
    assert result == {"themes": ["Fed", "NVDA"], "instruments": ["NVDA"]}


def test_unknown_values_are_filtered_out():
    # Model somehow returns a theme/ticker outside the universe -> dropped.
    result, _ = _tag({"themes": ["Fed", "Aliens"], "instruments": ["TSLA", "NVDA"]})
    assert result == {"themes": ["Fed"], "instruments": ["NVDA"]}


def test_none_response_yields_empty_lists():
    # API failure / refusal -> json_call returns None -> safe empty tags.
    result, _ = _tag(None)
    assert result == {"themes": [], "instruments": []}


def test_empty_uncertain_response():
    result, ai = _tag({"themes": [], "instruments": []})
    assert result == {"themes": [], "instruments": []}
    # tagging used the (cheaper) model id passed in
    assert ai.calls[0]["model"] == "m"
