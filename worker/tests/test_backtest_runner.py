"""Runner integration — single + scan, fully mocked (load_history patched)."""
import numpy as np
import pandas as pd

from app.backtest import runner
from app.config import load_config


def _synth(n=500, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2010-01-01", periods=n, freq="B")
    ret = rng.normal(0.0003, 0.011, n)
    close = 100 * np.cumprod(1 + ret)
    op = close * (1 + rng.normal(0, 0.001, n))
    return pd.DataFrame({"open": op, "high": close * 1.01, "low": close * 0.99, "close": close}, index=idx)


def test_run_single_payload(monkeypatch):
    monkeypatch.setattr(runner, "load_history", lambda sym, prov, **k: _synth(seed=1))
    cfg = load_config()
    out = runner.run_single(cfg, object(), "streak_reversion", "GC=F", {"down_days": 5, "hold_days": 3})

    assert out["kind"] == "single" and out["instrument"] == "GC=F"
    # NET-first metrics for full / in-sample / out-of-sample, each with B&H.
    for scope in ("full", "in_sample", "out_of_sample"):
        assert "net" in out["metrics"][scope] and "bh_net" in out["metrics"][scope]
    # Overfitting tell + honest extras present.
    assert "sharpe" in out["degradation"] and "in_sample" in out["degradation"]["sharpe"]
    assert 0.0 <= out["bootstrap"]["p_not_better_than_luck"] <= 1.0
    assert len(out["equity"]["dates"]) == len(out["equity"]["strat_net"]) == len(out["equity"]["bh_net"])
    assert out["caveats"]


def test_run_scan_counts_trials_and_deflates(monkeypatch):
    monkeypatch.setattr(runner, "load_history", lambda sym, prov, **k: _synth(seed=hash(sym) % 100))
    cfg = load_config()
    out = runner.run_scan(cfg, object(), rules=["streak_reversion"], instruments=["AAA", "BBB"])

    # streak grid in config is 5 x 4 = 20 trials.
    assert out["kind"] == "scan" and out["n_trials"] == 20
    assert len(out["distribution"]["oos_sharpe_ann"]) == 20
    d = out["deflated"]
    assert d["n_trials"] == 20 and 0.0 <= d["deflated_sharpe"] <= 1.0
    # Trials sorted best-first; best carries multi-instrument consistency.
    sharpes = [t["oos_sharpe_ann_median"] for t in out["trials"]]
    assert sharpes == sorted(sharpes, reverse=True)
    assert out["best"]["consistency"]["n_instruments"] == 2
    assert out["caveats"]


def test_scan_no_single_number_sold_as_edge(monkeypatch):
    # Honesty: the scan must expose the full distribution + n_trials, not just best.
    monkeypatch.setattr(runner, "load_history", lambda sym, prov, **k: _synth(seed=2))
    cfg = load_config()
    out = runner.run_scan(cfg, object(), rules=["streak_reversion"], instruments=["AAA"])
    assert out["n_trials"] == len(out["distribution"]["oos_sharpe_ann"])
    assert "deflated_sharpe" in out["deflated"]
