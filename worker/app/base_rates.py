"""Historical base-rate engine — PURE, testable, and deliberately HONEST.

The delicate piece. Given the CURRENT streak (e.g. "5 down days"), it answers
ONE question from the historical record: *when this has happened before, what
did the next day / next N days actually do* — reported as a frequency with its
sample size `n`, never as a forecast.

Hard honesty rules (CLAUDE.md §5), enforced here, not just in the UI:
  1. `n` (sample size) is ALWAYS part of the result.
  2. If `n` is below a configurable threshold, status is `insufficient`
     ("campione insufficiente — nessuna conclusione"): the numbers may be shown
     but must not be read as a conclusion.
  3. If the current streak has NEVER occurred in the lookback (`n == 0`), status
     is `never` and NO distribution is returned — "mai accaduto nel periodo:
     nessuna base statistica", explicitly NOT a probability.
  4. We do NOT compute or expose a "probability of a rebound". Rarity does not
     imply reversal (gambler's fallacy). We expose only the realised historical
     frequency (% of times up) and average move, each with its own `n`.

An occurrence is a past day on which the trailing run reached EXACTLY the
current length in the same direction — i.e. "the number of times a down-run
reached 5 days", counted once per episode at the moment it hit that length.
The forward return after such a day naturally INCLUDES cases where the streak
went on to extend; that is the honest outcome distribution.

Tested in `worker/tests/test_base_rates.py`.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from .technicals import consecutive_streak, plural_days

# Fixed honesty caveat surfaced alongside every streak base rate.
STREAK_CAVEAT = (
    "Uno streak lungo è spesso il segno di un trend forte, non di un rimbalzo "
    "garantito. Questa è la frequenza storica con la sua numerosità (n), non una "
    "previsione."
)


@dataclass(frozen=True)
class HorizonStat:
    horizon: int               # trading days ahead
    n: int                     # occurrences with this much forward data
    pct_up: float | None       # fraction (0..1) of times the forward return was > 0
    mean_return: float | None  # mean forward return, decimal (0.012 = +1.2%)
    median_return: float | None


@dataclass(frozen=True)
class BaseRateResult:
    direction: str             # 'up' | 'down' | 'flat'
    length: int                # current streak length
    sample_size: int           # n = past occurrences WITH an outcome (THE n)
    min_sample: int
    status: str                # 'ok' | 'insufficient' | 'never' | 'no_streak'
    in_progress: bool          # currently inside such a streak
    lookback_bars: int
    horizons: list[HorizonStat] = field(default_factory=list)
    message: str = ""
    caveat: str = STREAK_CAVEAT

    def to_dict(self) -> dict:
        return asdict(self)


def _run_lengths(closes: Sequence[float]) -> tuple[list[int], list[str]]:
    """Trailing run length + direction at each index (index 0 = no prior)."""
    n = len(closes)
    lengths = [0] * n
    dirs = ["flat"] * n
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        if diff == 0:
            lengths[i], dirs[i] = 0, "flat"
        else:
            d = "up" if diff > 0 else "down"
            if d == dirs[i - 1] and lengths[i - 1] > 0:
                lengths[i] = lengths[i - 1] + 1
            else:
                lengths[i] = 1
            dirs[i] = d
    return lengths, dirs


def _mean(xs: Sequence[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _median(xs: Sequence[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


def streak_base_rate(
    closes: Sequence[float],
    *,
    horizons: Sequence[int] = (1, 3, 5),
    min_sample: int = 20,
) -> BaseRateResult:
    """Base rate for the current streak. See module docstring for semantics."""
    streak = consecutive_streak(closes)
    n_bars = len(closes)

    if streak.length == 0:
        return BaseRateResult(
            direction=streak.direction, length=0, sample_size=0,
            min_sample=min_sample, status="no_streak", in_progress=False,
            lookback_bars=n_bars,
            message="Nessuno streak in corso (ultima variazione piatta o assente).",
        )

    lengths, dirs = _run_lengths(closes)
    L, D = streak.length, streak.direction
    last_idx = n_bars - 1

    # Occurrences = days where the trailing run reached exactly L in direction D.
    occurrences = [i for i in range(1, n_bars) if lengths[i] == L and dirs[i] == D]
    in_progress = last_idx in occurrences
    # Past occurrences = those with at least one following day (an outcome).
    past = [i for i in occurrences if i + 1 < n_bars]
    n = len(past)

    if n == 0:
        return BaseRateResult(
            direction=D, length=L, sample_size=0, min_sample=min_sample,
            status="never", in_progress=in_progress, lookback_bars=n_bars,
            message=(
                f"Streak di {L} {plural_days(L)} {_it_dir(D)} mai osservato in precedenza nel "
                f"periodo ({n_bars} barre): nessuna base statistica. NON una probabilità."
            ),
        )

    stats: list[HorizonStat] = []
    for h in horizons:
        rets = [
            closes[i + h] / closes[i] - 1.0
            for i in past
            if i + h < n_bars and closes[i] != 0
        ]
        if rets:
            ups = sum(1 for r in rets if r > 0)
            stats.append(
                HorizonStat(
                    horizon=h, n=len(rets), pct_up=ups / len(rets),
                    mean_return=_mean(rets), median_return=_median(rets),
                )
            )
        else:
            stats.append(HorizonStat(horizon=h, n=0, pct_up=None,
                                     mean_return=None, median_return=None))

    if n < min_sample:
        status = "insufficient"
        message = (
            f"Campione insufficiente (n={n} < {min_sample}): nessuna conclusione. "
            f"Streak di {L} {plural_days(L)} {_it_dir(D)}."
        )
    else:
        status = "ok"
        message = (
            f"Streak di {L} {plural_days(L)} {_it_dir(D)}: {n} casi storici simili nel periodo. "
            f"Sotto, cosa è successo dopo (frequenza, non previsione)."
        )

    return BaseRateResult(
        direction=D, length=L, sample_size=n, min_sample=min_sample,
        status=status, in_progress=in_progress, lookback_bars=n_bars,
        horizons=stats, message=message,
    )


def _it_dir(direction: str) -> str:
    return {"up": "su", "down": "giù", "flat": "piatti"}.get(direction, direction)
