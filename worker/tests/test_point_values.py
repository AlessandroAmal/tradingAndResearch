"""Point value (contract_multiplier) is real for futures — risk/P&L not treated as 1."""
from pytest import approx

from app.config import load_config
from app.risk import open_risk, position_size, unrealized_pnl


def test_config_has_real_point_values():
    cfg = load_config()
    m = cfg.multiplier_by_symbol
    assert m["GC=F"] == 100      # gold
    assert m["HG=F"] == 25000    # copper
    assert m["NG=F"] == 10000    # natural gas
    assert m["^NDX"] == 20       # nasdaq
    assert m["^GDAXI"] == 25     # dax
    assert m["NVDA"] == 1        # equities stay at 1


def test_gold_risk_uses_multiplier_not_one():
    # 1 gold contract, $10 of stop distance. With the real ×100, risk is $1000,
    # NOT the $10 you'd get treating it like a single share.
    risk_real = open_risk(entry=2000.0, stop=1990.0, size=1.0, multiplier=100)
    risk_as_one = open_risk(entry=2000.0, stop=1990.0, size=1.0, multiplier=1)
    assert risk_real == approx(1000.0)
    assert risk_as_one == approx(10.0)
    assert risk_real == 100 * risk_as_one


def test_sizing_respects_multiplier():
    # Same 1% risk on a 100k account: the multiplier shrinks the suggested size.
    size_real = position_size(100_000, 1.0, 2000.0, 1990.0, multiplier=100)
    size_as_one = position_size(100_000, 1.0, 2000.0, 1990.0, multiplier=1)
    assert size_real == approx(1.0)        # 1000 risk / (10 * 100)
    assert size_as_one == approx(100.0)    # 1000 risk / (10 * 1)


def test_pnl_uses_multiplier():
    pnl = unrealized_pnl(current_price=2010.0, entry=2000.0, size=1.0, side="long", multiplier=100)
    assert pnl == approx(1000.0)
