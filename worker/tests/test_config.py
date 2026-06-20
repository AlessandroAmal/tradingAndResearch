"""Tests for the config loader and env overrides."""
import textwrap

from app.config import load_config


def _write_cfg(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        textwrap.dedent(
            """
            base_currency: EUR
            account:
              size: 50000
            risk:
              max_risk_per_trade_pct: 2.0
              max_position_deadline_days: 21
            universe:
              - symbol: AAA
                name: Alpha
                asset_class: equity
              - symbol: BBB
                asset_class: etf
            holdings:
              - symbol: AAA
                quantity: 10
                avg_price: 100
            schedule:
              prices_cron: "*/30 * * * *"
              calendar_cron: "0 7 * * *"
            providers:
              prices: yfinance
              calendar: fmp
            indicators:
              history_days: 100
            """
        ),
        encoding="utf-8",
    )
    return p


def test_load_config_basic(tmp_path):
    cfg = load_config(_write_cfg(tmp_path))
    assert cfg.base_currency == "EUR"
    assert cfg.account_size == 50000
    assert cfg.symbols == ["AAA", "BBB"]
    assert cfg.universe[0].name == "Alpha"
    assert cfg.holdings[0].quantity == 10
    assert cfg.prices_cron == "*/30 * * * *"
    assert cfg.risk["max_position_deadline_days"] == 21


def test_env_override_universe(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_UNIVERSE", "ZZZ, YYY ,XXX")
    cfg = load_config(_write_cfg(tmp_path))
    assert cfg.symbols == ["ZZZ", "YYY", "XXX"]


def test_env_override_account_size(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ACCOUNT_SIZE", "12345")
    cfg = load_config(_write_cfg(tmp_path))
    assert cfg.account_size == 12345
