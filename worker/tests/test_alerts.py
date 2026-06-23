"""Tests for the alert engine (M8) — notifier fully mocked, no Telegram.

Covers: threshold crossing, edge-trigger + cooldown re-fire, and per-item
dedup (standing categories). No network.
"""
from datetime import datetime, timedelta, timezone

from app.alerts.engine import run_alert_evaluation
from app.alerts.rules import should_fire, threshold_met
from app.config import AppConfig

T0 = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)


# --- pure logic -------------------------------------------------------
def test_threshold_met():
    assert threshold_met("above", 105, 100) is True
    assert threshold_met("above", 95, 100) is False
    assert threshold_met("below", 95, 100) is True
    assert threshold_met("below", 105, 100) is False
    assert threshold_met("above", None, 100) is False


def test_should_fire_edge_and_cooldown():
    # edge: became true
    assert should_fire(True, False, None, 3600, T0) is True
    # condition false -> never
    assert should_fire(False, False, None, 3600, T0) is False
    # still true, within cooldown -> suppress
    assert should_fire(True, True, T0, 3600, T0 + timedelta(seconds=60)) is False
    # still true, past cooldown -> re-fire
    assert should_fire(True, True, T0, 3600, T0 + timedelta(seconds=4000)) is True
    # true but no record -> fire
    assert should_fire(True, True, None, 3600, T0) is True


# --- fakes ------------------------------------------------------------
class FakeNotifier:
    name = "fake"

    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return True


class FakeStorage:
    def __init__(self, rules, price=None, figures=None):
        self.rules = rules
        self.price = price
        self.figures = figures or []
        self.alerts = []
        self._dedup = set()

    def list_alert_rules(self, enabled_only=True):
        return self.rules

    def get_instrument_id(self, s):
        return f"id-{s}"

    def get_latest_close(self, iid):
        return self.price

    def get_atm_iv(self, u):
        return None

    def update_alert_rule_state(self, rid, last_triggered, last_state):
        for r in self.rules:
            if r["id"] == rid:
                r["last_triggered"] = last_triggered
                r["last_state"] = last_state

    def insert_alert(self, a):
        self.alerts.append(a)
        if a.get("dedup_key"):
            self._dedup.add(a["dedup_key"])

    def recent_alert_exists(self, dedup_key, since_iso):
        return dedup_key in self._dedup

    # standing data sources (empty unless overridden)
    def list_positions(self, *a, **k):
        return []

    def list_recent_figure_statements(self, *a, **k):
        return self.figures

    def list_recent_news(self, *a, **k):
        return []

    def get_distinct_option_underlyings(self):
        return []


def _cfg():
    return AppConfig(
        base_currency="USD", account={"size": 100000}, risk={}, universe=[], holdings=[],
        schedule={}, providers={}, indicators={}, alerts={"cooldown_seconds": 3600},
    )


# --- engine: price rule edge + cooldown ------------------------------
def test_price_rule_edge_then_cooldown():
    rule = {"id": "r1", "kind": "price", "symbol": "AAA", "op": "above",
            "threshold": 100, "cooldown_seconds": 3600, "last_state": False, "last_triggered": None}
    storage = FakeStorage([rule], price=105)
    notifier = FakeNotifier()

    # 1) crosses above -> fire
    run_alert_evaluation(_cfg(), storage, notifier, now=T0)
    assert len(notifier.sent) == 1
    assert rule["last_state"] is True

    # 2) still above, within cooldown -> suppressed
    run_alert_evaluation(_cfg(), storage, notifier, now=T0 + timedelta(seconds=120))
    assert len(notifier.sent) == 1

    # 3) still above, past cooldown -> re-fire
    run_alert_evaluation(_cfg(), storage, notifier, now=T0 + timedelta(seconds=4000))
    assert len(notifier.sent) == 2


def test_price_rule_not_crossed_no_fire():
    rule = {"id": "r2", "kind": "price", "symbol": "AAA", "op": "above",
            "threshold": 100, "cooldown_seconds": 3600, "last_state": False, "last_triggered": None}
    storage = FakeStorage([rule], price=90)
    notifier = FakeNotifier()
    run_alert_evaluation(_cfg(), storage, notifier, now=T0)
    assert notifier.sent == []
    assert rule["last_state"] is False


# --- engine: standing per-item dedup ---------------------------------
def test_standing_key_figure_dedup():
    rule = {"id": "s1", "kind": "standing", "standing_type": "key_figure",
            "cooldown_seconds": 3600, "enabled": True}
    figs = [{"id": "f1", "figure": "Powell", "statement": "Rates on hold", "stated_at": T0.isoformat()}]
    storage = FakeStorage([rule], figures=figs)
    notifier = FakeNotifier()

    run_alert_evaluation(_cfg(), storage, notifier, now=T0)
    assert len(notifier.sent) == 1            # fires once for the new statement
    run_alert_evaluation(_cfg(), storage, notifier, now=T0 + timedelta(seconds=60))
    assert len(notifier.sent) == 1            # deduped — not sent again
