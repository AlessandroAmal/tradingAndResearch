"""Controlled event experiment — surprise, timing, the open/close job (paper only,
separated), and aggregation. External prices/storage are faked; no network."""
from datetime import datetime, timedelta, timezone

from pytest import approx

from app.experiment.aggregate import aggregate_experiments
from app.experiment.job import run_event_experiment
from app.experiment.plan import (
    due_delays,
    exit_time,
    experiment_key,
    is_exit_due,
    is_key_event,
)
from app.experiment.surprise import parse_number, surprise_direction

UTC = timezone.utc


# --- surprise --------------------------------------------------------
def test_parse_number_units():
    assert parse_number("206K") == approx(206_000)
    assert parse_number("3.1%") == approx(3.1)
    assert parse_number("-0.2") == approx(-0.2)
    assert parse_number("1.2M") == approx(1_200_000)
    assert parse_number("n/a") is None and parse_number(None) is None


def test_surprise_direction_and_missing_consensus():
    hot = surprise_direction("3.4%", "3.1%")
    assert hot["available"] and hot["direction"] == "positive"
    cold = surprise_direction("150K", "200K")
    assert cold["direction"] == "negative"
    inline = surprise_direction("200K", "200K")
    assert inline["direction"] == "inline"
    # consensus missing -> not invented
    miss = surprise_direction("200K", None)
    assert miss["available"] is False and miss["direction"] is None
    assert "non disponibile" in miss["note"].lower()


# --- timing ----------------------------------------------------------
def test_is_key_event():
    assert is_key_event("US CPI (Jun)", ["CPI", "PCE"]) is True
    assert is_key_event("Retail sales", ["CPI", "PCE"]) is False


def test_due_delays_window():
    ev = datetime(2026, 7, 10, 12, 30, tzinfo=UTC)
    now = ev + timedelta(minutes=6)                      # 6 min after release
    due = due_delays(ev, now, [5, 30, 120, 1440], grace_min=20)
    assert due == [5]                                    # t+5 is due (within grace), t+30 not yet
    # too late for t+5 once we're past grace
    assert due_delays(ev, ev + timedelta(minutes=40), [5, 30], 20) == [30]


def test_exit_time_horizons():
    entry = datetime(2026, 7, 10, 13, 0, tzinfo=UTC)     # Friday
    assert exit_time(entry, "eod").hour == 21
    assert exit_time(entry, "eod").date() == entry.date()
    # +3 business days from Fri 10th -> Wed 15th
    assert exit_time(entry, "3d").date() == datetime(2026, 7, 15).date()
    assert exit_time(entry, "5d").date() == datetime(2026, 7, 17).date()
    assert exit_time(entry, "bogus") is None


def test_is_exit_due():
    now = datetime(2026, 7, 10, 22, 0, tzinfo=UTC)
    assert is_exit_due("2026-07-10T21:00:00+00:00", now) is True
    assert is_exit_due("2026-07-11T21:00:00+00:00", now) is False


# --- the job (fakes) -------------------------------------------------
class FakeStorage:
    def __init__(self, events):
        self._events = events
        self.positions = []
        self._id = 0

    def list_recent_events(self, days, limit):
        return self._events

    def list_positions(self, status=None):
        return [p for p in self.positions if status is None or p.get("status") == status]

    def insert_position(self, pos):
        self._id += 1
        row = {**pos, "id": str(self._id)}
        self.positions.append(row)
        return row

    def update_position(self, pid, fields):
        for p in self.positions:
            if p["id"] == pid:
                p.update(fields)

    def get_instrument_id(self, symbol):
        return f"iid-{symbol}"

    def get_decision_board(self, symbol):
        return {"synthesis": {"lean": {"direction": "bearish"}},
                "implied": {"horizons": [{"available": True, "prob_up": 0.48, "days_to_expiry": 30}]}}


class FakePrices:
    def __init__(self, price=100.0):
        self.price = price

    def latest_price(self, symbol):
        return self.price


class _Cfg:
    def __init__(self, experiment):
        self._e = experiment

    @property
    def experiment(self):
        return self._e


def _cfg(**over):
    base = dict(enabled=True, event_keywords=["CPI"], instruments=["GC=F"],
                delays_min=[5, 30], horizons=["eod"], directions=["long", "short"],
                entry_grace_min=20, lookback_days=3, spread_bps=5)
    base.update(over)
    return _Cfg(base)


def test_job_opens_paper_both_directions_and_is_idempotent():
    ev_time = datetime(2026, 7, 10, 12, 30, tzinfo=UTC)
    now = ev_time + timedelta(minutes=6)
    st = FakeStorage([{"title": "US CPI", "event_time": ev_time.isoformat(),
                       "actual": "3.4%", "forecast": "3.1%"}])
    res = run_event_experiment(_cfg(), st, FakePrices(100.0), now=now)
    # 1 instrument × 1 due delay (t+5) × 1 horizon × 2 directions = 2 paper rows
    assert res["opened"] == 2
    assert all(p["paper"] and p["experiment"] and p["broker"] == "EXPERIMENT" for p in st.positions)
    assert {p["side"] for p in st.positions} == {"long", "short"}
    # conditions captured: surprise direction + entry price + lean snapshot
    c = st.positions[0]["entry_conditions"]
    assert c["surprise"]["direction"] == "positive" and c["entry_price"] == 100.0
    assert c["lean_direction"] == "bearish" and c["implied_prob_up"] == 0.48
    # idempotent: a second run at the same time opens nothing new
    res2 = run_event_experiment(_cfg(), st, FakePrices(100.0), now=now)
    assert res2["opened"] == 0


def test_job_closes_at_horizon_with_return():
    ev_time = datetime(2026, 7, 10, 12, 30, tzinfo=UTC)
    now = ev_time + timedelta(minutes=6)
    st = FakeStorage([{"title": "US CPI", "event_time": ev_time.isoformat(),
                       "actual": "3.4%", "forecast": "3.1%"}])
    run_event_experiment(_cfg(), st, FakePrices(100.0), now=now)
    # later, price at exit = 102 -> long +2%, short -2%
    later = exit_from(st) + timedelta(minutes=1)
    res = run_event_experiment(_cfg(), st, FakePrices(102.0), now=later)
    assert res["closed"] == 2
    closed = {p["side"]: p for p in st.positions if p["status"] == "closed"}
    assert closed["long"]["entry_conditions"]["return_pct"] == approx(0.02)
    assert closed["short"]["entry_conditions"]["return_pct"] == approx(-0.02)
    assert closed["long"]["realized_pnl"] == approx(2.0)


def test_job_disabled_is_noop():
    st = FakeStorage([])
    assert run_event_experiment(_cfg(enabled=False), st, FakePrices(), now=datetime(2026, 7, 10, tzinfo=UTC))["opened"] == 0


def exit_from(st):
    xt = st.positions[0]["entry_conditions"]["exit_time"]
    return datetime.fromisoformat(xt)


# --- aggregation -----------------------------------------------------
def _closed(symbol, delay, horizon, direction, ret, surprise="positive"):
    return {"status": "closed", "symbol": symbol, "entry": 100.0,
            "entry_conditions": {"event": "US CPI", "delay_min": delay, "horizon": horizon,
                                 "direction": direction, "return_pct": ret,
                                 "surprise": {"direction": surprise}}}


def test_aggregate_by_delay_with_threshold():
    pos = [_closed("GC=F", 5, "eod", "long", r) for r in (0.01, 0.02, -0.01)]
    pos += [_closed("GC=F", 30, "eod", "long", r) for r in (0.005, -0.002)]
    agg = aggregate_experiments(pos, ["symbol", "delay_min", "horizon"], min_sample=3)
    by_delay = {c["group"]["delay_min"]: c for c in agg}
    assert by_delay[5]["n"] == 3 and by_delay[5]["sufficient"] is True
    assert by_delay[5]["pct_positive"] == approx(2 / 3)
    assert by_delay[5]["mean_return"] == approx((0.01 + 0.02 - 0.01) / 3)
    assert by_delay[30]["n"] == 2 and by_delay[30]["sufficient"] is False   # below min_sample
    # open positions are ignored
    assert aggregate_experiments([{"status": "open", "symbol": "GC=F"}], ["symbol"]) == []
