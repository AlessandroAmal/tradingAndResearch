"""Tests for AI impact-mapping JSON handling — no real API calls."""
from app.ai.impact import build_impact_schema, map_statement_impact

SYMBOLS = ["^NDX", "NVDA", "GC=F"]


class FakeAI:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def json_call(self, *, model, system, user, schema, max_tokens):
        self.calls.append({"model": model, "schema": schema})
        return self._payload


def _map(payload):
    ai = FakeAI(payload)
    result = map_statement_impact(
        ai, model="m", figure="Jensen Huang", role="NVIDIA CEO",
        text="Huang says demand is strong", symbols=SYMBOLS,
    )
    return result, ai


def test_impact_schema_constrains_instruments():
    schema = build_impact_schema(SYMBOLS)
    assert schema["properties"]["affected_instruments"]["items"]["enum"] == SYMBOLS
    assert schema["additionalProperties"] is False


def test_valid_impact_passes_through():
    result, _ = _map(
        {"affected_instruments": ["NVDA", "^NDX"], "why_it_matters": "Could lift AI names."}
    )
    assert result["affected_instruments"] == ["NVDA", "^NDX"]
    assert result["why_it_matters"] == "Could lift AI names."


def test_unknown_instruments_filtered():
    result, _ = _map(
        {"affected_instruments": ["TSLA", "NVDA"], "why_it_matters": "x"}
    )
    assert result["affected_instruments"] == ["NVDA"]


def test_no_clear_impact_yields_empty_list():
    result, _ = _map({"affected_instruments": [], "why_it_matters": "No clear impact."})
    assert result["affected_instruments"] == []
    assert result["why_it_matters"] == "No clear impact."


def test_none_response_is_safe():
    result, _ = _map(None)
    assert result == {"affected_instruments": [], "why_it_matters": ""}
