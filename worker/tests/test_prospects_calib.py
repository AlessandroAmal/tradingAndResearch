"""Valuation layer + calibration metrics + constrained recalibration."""
import random

from pytest import approx

from app.prospects import calibration_metrics as cm
from app.prospects import valuation as val


# --- valuation layer -------------------------------------------------
def test_valuation_distribution_buckets_and_effective_n():
    # cheap starts -> higher forward return; expensive -> lower (engineered)
    closes, valuations = [], []
    price = 100.0
    for i in range(6 * val.TRADING_YEAR):
        pe = 10 if (i // val.TRADING_YEAR) % 2 == 0 else 40   # alternate cheap/expensive years
        drift = 1.0 + (0.0006 if pe == 10 else 0.0001)
        price *= drift
        closes.append(price); valuations.append(float(pe))
    d = val.valuation_return_distribution(closes, valuations, 3, current_valuation=10.0)
    assert d["available"] is True and d["bucket"] == "cheap"
    assert d["n"] > 0 and "n_effective" in d
    assert "indicativo" in d["note"].lower() or "indipendenti pochissime" in d["note"].lower()


def test_valuation_needs_current_and_history():
    assert val.valuation_return_distribution([100, 101], [None, None], 3, None)["available"] is False


# --- reliability + brier --------------------------------------------
def test_perfectly_calibrated_lands_on_diagonal():
    rng = random.Random(1)
    preds = []
    for _ in range(20000):
        p = rng.random()
        preds.append((p, rng.random() < p))     # event happens with prob p exactly
    rel = cm.reliability(preds, bins=10)
    for b in rel:
        if b["n"] > 200:
            assert b["realised"] == approx(b["declared"], abs=0.05)   # on the diagonal
    assert cm.brier_score(preds) == approx(1 / 6, abs=0.02)          # E[(p-Bern(p))²]=E[p(1-p)]


def test_brier_extremes():
    assert cm.brier_score([(1.0, True), (0.0, False)]) == 0.0        # perfect
    assert cm.brier_score([(1.0, False), (0.0, True)]) == 1.0        # worst
    assert cm.brier_score([]) is None


# --- interval coverage ----------------------------------------------
def test_coverage_report_flags_overconfident():
    # 95% band that only actually contains 60% of outcomes -> "sovra-sicuro"
    recs = []
    for i in range(50):
        outcome = 0.0 if i < 30 else 5.0     # 20/50 fall outside a tight band
        recs.append({"p16": -0.5, "p84": 0.5, "p2_5": -1.0, "p97_5": 1.0, "median": 0.0, "outcome": outcome})
    rep = cm.coverage_report(recs)
    assert rep["coverage_95"]["coverage"] == approx(0.6)
    assert rep["verdict"] and "sovra-sicuro" in rep["verdict"]


# --- constrained recalibration --------------------------------------
def test_recalibration_widens_only_if_it_helps_oos():
    rng = random.Random(7)
    # true outcomes ~ N(0,1)*3 but model states a too-tight ±1 (95 band) -> needs widening
    def mk(n):
        recs = []
        for _ in range(n):
            x = rng.gauss(0, 3)
            recs.append({"median": 0.0, "p2_5": -1.0, "p97_5": 1.0, "p16": -0.5, "p84": 0.5, "outcome": x})
        return recs
    res = cm.recalibrate_dispersion(mk(400), mk(400), band="95", target=0.95)
    assert res["applied"] is True and res["scale"] > 1.0            # widened
    assert res["test_coverage_after"] > res["test_coverage_before"]  # improved OOS
    # direction is never part of the correction
    assert "scale" in res and "shift" not in res


def test_recalibration_declines_when_no_oos_gain():
    rng = random.Random(3)
    # already well-calibrated -> scaling shouldn't help OOS -> not applied
    def mk(n):
        recs = []
        for _ in range(n):
            x = rng.gauss(0, 1)
            # ±1.96 ~ 95% for N(0,1)
            recs.append({"median": 0.0, "p2_5": -1.96, "p97_5": 1.96, "p16": -1.0, "p84": 1.0, "outcome": x})
        return recs
    res = cm.recalibrate_dispersion(mk(500), mk(500), band="95", target=0.95)
    assert res["applied"] is False and "rumore" in res["reason"].lower()


# --- retrospective coverage walk (no look-ahead) --------------------
def test_coverage_records_no_lookahead_and_well_calibrated():
    import random as _r
    from app.prospects.calibrate import coverage_records
    rng = _r.Random(11)
    # random walk -> forward-return distribution is stable -> coverage ~ nominal
    closes = [100.0]
    for _ in range(3000):
        closes.append(closes[-1] * (1 + rng.gauss(0, 0.01)))
    recs = coverage_records(closes, h=21, warmup=500)
    assert len(recs) > 30
    # each record's bands came only from data BEFORE t: outcome is separate
    assert all("outcome" in r and "p2_5" in r and "p97_5" in r for r in recs)
    from app.prospects.calibration_metrics import coverage_report
    rep = coverage_report(recs)
    # a stationary process -> 95% band should cover roughly 0.85..1.0
    assert rep["coverage_95"]["coverage"] >= 0.8
