"""Placeholder for the risk/position-sizing math tests (brief Phase 3).

The sizing math (risk-per-trade, position size from entry/stop, exposure
caps) must be correct, so its test scaffold lives here now and will be
filled in when Phase 3 lands. Skipped until then so the suite stays green.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Risk/sizing math arrives in Phase 3")


def test_position_size_from_risk_per_trade():
    # Given account size, max_risk_per_trade_pct, entry and stop, the
    # computed size must risk exactly the configured fraction of equity.
    ...


def test_total_exposure_cap_enforced():
    ...
