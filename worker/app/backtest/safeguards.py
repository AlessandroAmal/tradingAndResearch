"""Anti-illusion safeguards — the HEART of the bench (CLAUDE.md honesty mandate).

These exist to make overfitting VISIBLE, not to hide it:

  * IS/OOS split + the in-sample→out-of-sample DEGRADATION (the overfitting tell).
  * Multi-instrument consistency (a real edge shows on more than one asset).
  * Deflated Sharpe Ratio (Bailey & López de Prado): when you try N configs, the
    best is EXPECTED to look good by chance — DSR corrects the best-of-N Sharpe
    for the number of trials and the non-normality of returns.
  * Bootstrap significance: is the strategy distinguishable from (i) luck and
    (ii) buy-and-hold? Reported as confidence intervals, not a single number.

All pure; bootstrap is seeded for reproducible tests. Per-period (NOT annualised)
Sharpe is used for DSR so the math is internally consistent.
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

EULER_MASCHERONI = 0.5772156649015329
_Z = NormalDist().inv_cdf
_PHI = NormalDist().cdf

# Fixed honesty caveats shown with every result.
CAVEATS = [
    "Il passato non è il futuro: un backtest misura ciò che è stato, non ciò che sarà.",
    "Un buon risultato in-sample è atteso anche per puro caso: guarda l'out-of-sample e il degrado.",
    "Cercando tra molti parametri/regole, il MIGLIORE sembra buono per fortuna — vedi lo Sharpe deflazionato.",
    "Gli edge decadono: costi, regime e affollamento li erodono nel tempo.",
    "Risultati al NETTO di costi+slippage; confrontati sempre col buy-and-hold.",
]


# --- in-sample / out-of-sample split ---------------------------------
def split_index(n: int, is_fraction: float = 0.6) -> int:
    """Boundary index: [0:k) is in-sample, [k:n) is out-of-sample."""
    k = int(round(n * is_fraction))
    return max(1, min(k, n - 1))


def degradation(is_metrics: dict, oos_metrics: dict, key: str = "sharpe") -> dict:
    """The overfitting tell: how much a metric drops IS → OOS."""
    a = is_metrics.get(key)
    b = oos_metrics.get(key)
    if a is None or b is None:
        return {"in_sample": a, "out_of_sample": b, "drop": None, "retained_pct": None}
    drop = a - b
    retained = (b / a) if a not in (0, None) else None
    return {"in_sample": a, "out_of_sample": b, "drop": drop,
            "retained_pct": (retained * 100.0 if retained is not None else None)}


# --- per-period Sharpe + moments -------------------------------------
def sharpe_pp(ret: np.ndarray) -> float:
    ret = np.asarray(ret, float)
    if len(ret) < 2:
        return 0.0
    sd = float(np.std(ret, ddof=1))
    return float(np.mean(ret)) / sd if sd > 0 else 0.0


def _moments(ret: np.ndarray) -> tuple[float, float]:
    ret = np.asarray(ret, float)
    m = float(np.mean(ret))
    s = float(np.std(ret, ddof=0))
    if s == 0 or len(ret) < 2:
        return 0.0, 3.0
    z = (ret - m) / s
    skew = float(np.mean(z ** 3))
    kurt = float(np.mean(z ** 4))   # full kurtosis (normal = 3)
    return skew, kurt


# --- Probabilistic / Deflated Sharpe ---------------------------------
def probabilistic_sharpe(ret: np.ndarray, sr_benchmark_pp: float = 0.0) -> float:
    """P(true per-period Sharpe > benchmark), adjusting for skew/kurtosis."""
    ret = np.asarray(ret, float)
    n = len(ret)
    if n < 3:
        return float("nan")
    sr = sharpe_pp(ret)
    skew, kurt = _moments(ret)
    denom = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if denom <= 0:
        return float("nan")
    return _PHI((sr - sr_benchmark_pp) * math.sqrt(n - 1) / math.sqrt(denom))


def expected_max_sharpe(trial_sharpes_pp: list[float]) -> float:
    """Expected MAX per-period Sharpe under the null across N independent trials
    (Bailey & López de Prado). This is the bar the best-of-N must clear."""
    n = len(trial_sharpes_pp)
    if n < 2:
        return 0.0
    sd = float(np.std(np.asarray(trial_sharpes_pp, float), ddof=1))
    if sd == 0:
        return 0.0
    return sd * ((1 - EULER_MASCHERONI) * _Z(1 - 1.0 / n)
                 + EULER_MASCHERONI * _Z(1 - 1.0 / (n * math.e)))


def deflated_sharpe(best_ret: np.ndarray, trial_sharpes_pp: list[float]) -> dict:
    """DSR for the best strategy given the whole set of trial Sharpes.

    DSR = P(true Sharpe > expected-max-under-null). A low DSR means the winner is
    likely a fluke of multiple testing.
    """
    sr0 = expected_max_sharpe(trial_sharpes_pp)
    dsr = probabilistic_sharpe(best_ret, sr0)
    return {
        "n_trials": len(trial_sharpes_pp),
        "best_sharpe_pp": sharpe_pp(best_ret),
        "expected_max_sharpe_pp": sr0,
        "deflated_sharpe": dsr,   # probability in [0,1]
        "note": "Con N tentativi il migliore è atteso sembrare buono per caso; "
                "il DSR sconta questo. DSR alto (>0.95) = robusto al data-snooping.",
    }


# --- bootstrap significance ------------------------------------------
def _moving_block_resample(rng, x: np.ndarray, block: int) -> np.ndarray:
    n = len(x)
    if block <= 1:
        return x[rng.integers(0, n, size=n)]
    n_blocks = int(math.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=n_blocks)
    idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
    return x[idx]


def bootstrap_significance(
    strat_ret: np.ndarray,
    bh_ret: np.ndarray,
    *,
    n_iter: int = 1000,
    block: int = 5,
    seed: int = 12345,
    periods_per_year: int = 252,
) -> dict:
    """Bootstrap CIs for the strategy Sharpe, and tests vs (i) luck and (ii) B&H.

    Returns annualised Sharpe CIs + the fraction of resamples where the strategy
    fails to beat zero / buy-and-hold (a p-value-like figure). Block bootstrap
    preserves some serial dependence; seeded for reproducibility.
    """
    strat = np.asarray(strat_ret, float)
    bh = np.asarray(bh_ret, float)
    rng = np.random.default_rng(seed)
    ann = math.sqrt(periods_per_year)

    sr_samples = np.empty(n_iter)
    excess_means = np.empty(n_iter)
    diff = strat - bh
    for i in range(n_iter):
        rs = _moving_block_resample(rng, strat, block)
        sr_samples[i] = sharpe_pp(rs) * ann
        rd = _moving_block_resample(rng, diff, block)
        excess_means[i] = float(np.mean(rd))

    def ci(a):
        return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]

    return {
        "n_iter": n_iter, "block": block,
        "sharpe_ann": sharpe_pp(strat) * ann,
        "sharpe_ci95": ci(sr_samples),
        "p_not_better_than_luck": float(np.mean(sr_samples <= 0)),
        "mean_excess_vs_bh": float(np.mean(diff)),
        "mean_excess_ci95": ci(excess_means),
        "p_not_better_than_bh": float(np.mean(excess_means <= 0)),
        "note": "Intervalli al 95% e quote, non un singolo numero. "
                "Se la CI dello Sharpe include 0, non è distinguibile dalla fortuna.",
    }


# --- multi-instrument consistency ------------------------------------
def consistency(results: list[dict]) -> dict:
    """Aggregate the SAME rule across instruments: a real edge is broad."""
    oos_sharpes = [r["oos_sharpe"] for r in results if r.get("oos_sharpe") is not None]
    excess = [r["oos_excess_vs_bh"] for r in results if r.get("oos_excess_vs_bh") is not None]
    n = len(results)
    return {
        "n_instruments": n,
        "median_oos_sharpe": float(np.median(oos_sharpes)) if oos_sharpes else None,
        "share_positive_oos_sharpe": (float(np.mean(np.array(oos_sharpes) > 0)) if oos_sharpes else None),
        "share_beats_buy_hold_oos": (float(np.mean(np.array(excess) > 0)) if excess else None),
        "per_instrument": results,
        "note": "Un edge vero appare su PIÙ strumenti, non su uno solo in una finestra.",
    }
