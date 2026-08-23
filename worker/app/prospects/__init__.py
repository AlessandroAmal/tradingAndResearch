"""Multi-horizon probabilistic outcomes — distributions, not point forecasts.

Three honest sources, each labelled and calibration-verified:
  * bl.py       — risk-neutral density from the option chain (Breeden-Litzenberger)
  * conditional.py — conditional historical frequencies with effective-n
  * valuation.py — initial valuation -> long-horizon return (indices/stocks)
Calibration (calibration_metrics.py) checks reliability + interval coverage.

NONE of this is a fabricated directional number: (a) is market risk-neutral odds,
(b)/(c) are historical frequencies WITH their sample size. The AI only interprets
these numbers, never invents them (CLAUDE.md).
"""
