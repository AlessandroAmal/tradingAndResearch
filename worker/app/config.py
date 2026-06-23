"""Configuration loader.

Hard rule (CLAUDE.md §3): universe, holdings, account size and risk
limits are CONFIGURABLE, never hardcoded. This module loads the YAML
config and applies selected environment-variable overrides.

Nothing here treats any holding as "owned" by the app — it merely
reflects what the user put in config.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()  # pull .env into os.environ if present

# Repo root = two levels up from this file (worker/app/config.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str | None = None
    asset_class: str | None = None
    exchange: str | None = None
    currency: str = "USD"
    sleeve: str | None = None          # macro|equity|commodity|energy|gauge
    tradeable_on: str | None = None    # informational (where it can be traded)
    traded: bool = True                # False = display-only gauge (e.g. VIX)
    contract_multiplier: float = 1.0   # point value (futures/CFD/FX); default 1


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: float = 0
    avg_price: float | None = None
    name: str | None = None
    asset_class: str | None = None


@dataclass(frozen=True)
class AppConfig:
    base_currency: str
    account: dict[str, Any]
    risk: dict[str, Any]
    universe: list[Instrument]
    holdings: list[Holding]
    schedule: dict[str, Any]
    providers: dict[str, Any]
    indicators: dict[str, Any]
    ai: dict[str, Any] = field(default_factory=dict)
    news: dict[str, Any] = field(default_factory=dict)
    themes: list[str] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    # --- convenience accessors -------------------------------------
    @property
    def account_size(self) -> float:
        return float(self.account.get("size", 0))

    @property
    def symbols(self) -> list[str]:
        return [i.symbol for i in self.universe]

    @property
    def multiplier_by_symbol(self) -> dict[str, float]:
        return {i.symbol: float(i.contract_multiplier or 1.0) for i in self.universe}

    # --- risk limits (M6; configurable, env-overridable) -----------
    @property
    def max_risk_per_trade_pct(self) -> float:
        return float(os.getenv("MAX_RISK_PER_TRADE_PCT", self.risk.get("max_risk_per_trade_pct", 1.0)))

    @property
    def max_portfolio_heat_pct(self) -> float:
        return float(os.getenv("MAX_PORTFOLIO_HEAT_PCT", self.risk.get("max_portfolio_heat_pct", 6.0)))

    @property
    def max_concurrent_positions(self) -> int:
        # Accept legacy `max_open_positions` as a fallback.
        default = self.risk.get("max_concurrent_positions", self.risk.get("max_open_positions", 8))
        return int(os.getenv("MAX_CONCURRENT_POSITIONS", default))

    @property
    def max_position_deadline_days(self) -> int:
        return int(self.risk.get("max_position_deadline_days", 21))

    @property
    def deadline_warn_days(self) -> int:
        return int(self.risk.get("deadline_warn_days", 3))

    # --- options desk (M5) -----------------------------------------
    @property
    def options_cron(self) -> str:
        return os.getenv("OPTIONS_CRON", self.schedule.get("options_cron", "0 23 * * *"))

    @property
    def options_provider(self) -> str:
        return self.options.get("provider", "yfinance")

    @property
    def risk_free_rate(self) -> float:
        return float(os.getenv("RISK_FREE_RATE", self.options.get("risk_free_rate", 0.04)))

    @property
    def options_expiries_count(self) -> int:
        return int(self.options.get("expiries_count", 3))

    @property
    def options_strikes_window_pct(self) -> float:
        return float(self.options.get("strikes_window_pct", 0.15))

    @property
    def options_hedge(self) -> dict[str, Any]:
        return dict(self.options.get("hedge", {}))

    @property
    def macro_proxies(self) -> dict[str, str]:
        return {k: v for k, v in (self.options.get("macro_proxies", {}) or {}).items() if v}

    @property
    def prices_cron(self) -> str:
        return os.getenv("PRICES_CRON", self.schedule.get("prices_cron", "*/15 * * * *"))

    @property
    def calendar_cron(self) -> str:
        return os.getenv("CALENDAR_CRON", self.schedule.get("calendar_cron", "0 6 * * *"))

    @property
    def news_cron(self) -> str:
        return os.getenv("NEWS_CRON", self.schedule.get("news_cron", "*/30 * * * *"))

    @property
    def tagging_cron(self) -> str:
        return os.getenv("TAGGING_CRON", self.schedule.get("tagging_cron", "*/30 * * * *"))

    @property
    def briefing_morning_cron(self) -> str:
        return os.getenv(
            "BRIEFING_MORNING_CRON",
            self.schedule.get("briefing_morning_cron", "30 6 * * *"),
        )

    @property
    def briefing_intraday_cron(self) -> str:
        return os.getenv(
            "BRIEFING_INTRADAY_CRON",
            self.schedule.get("briefing_intraday_cron", "0 13,18 * * *"),
        )

    @property
    def figures_cron(self) -> str:
        return os.getenv("FIGURES_CRON", self.schedule.get("figures_cron", "*/45 * * * *"))

    @property
    def impact_cron(self) -> str:
        return os.getenv("IMPACT_CRON", self.schedule.get("impact_cron", "*/45 * * * *"))

    # --- AI config (models configurable via config + env) ----------
    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai.get("enabled", True))

    @property
    def briefing_model(self) -> str:
        return os.getenv(
            "ANTHROPIC_BRIEFING_MODEL",
            self.ai.get("briefing_model", "claude-sonnet-4-6"),
        )

    @property
    def tagging_model(self) -> str:
        return os.getenv(
            "ANTHROPIC_TAGGING_MODEL",
            self.ai.get("tagging_model", "claude-haiku-4-5-20251001"),
        )

    @property
    def figures_model(self) -> str:
        # Impact mapping defaults to the (cheap) tagging model unless set.
        return os.getenv(
            "ANTHROPIC_FIGURES_MODEL",
            self.ai.get("figures_model", self.tagging_model),
        )

    @property
    def journal_review_model(self) -> str:
        # Journal review is quality, not volume -> default to the briefing model.
        return os.getenv(
            "ANTHROPIC_JOURNAL_MODEL",
            self.ai.get("journal_review_model", self.briefing_model),
        )


def _resolve_config_path() -> Path:
    raw = os.getenv("APP_CONFIG_FILE", "config/config.yaml")
    p = Path(raw)
    return p if p.is_absolute() else REPO_ROOT / p


def load_config(path: str | os.PathLike[str] | None = None) -> AppConfig:
    """Load YAML config and apply env overrides."""
    cfg_path = Path(path) if path else _resolve_config_path()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    with cfg_path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh) or {}

    universe = [Instrument(**item) for item in data.get("universe", [])]
    holdings = [Holding(**item) for item in data.get("holdings", [])]

    # --- env overrides (CONFIGURABLE, not hardcoded) ---------------
    if env_uni := os.getenv("APP_UNIVERSE"):
        syms = [s.strip() for s in env_uni.split(",") if s.strip()]
        universe = [Instrument(symbol=s) for s in syms]

    account = dict(data.get("account", {}))
    if env_size := os.getenv("APP_ACCOUNT_SIZE"):
        account["size"] = float(env_size)

    return AppConfig(
        base_currency=data.get("base_currency", "USD"),
        account=account,
        risk=dict(data.get("risk", {})),
        universe=universe,
        holdings=holdings,
        schedule=dict(data.get("schedule", {})),
        providers=dict(data.get("providers", {})),
        indicators=dict(data.get("indicators", {})),
        ai=dict(data.get("ai", {})),
        news=dict(data.get("news", {})),
        themes=list(data.get("themes", [])),
        figures=list(data.get("figures", [])),
        options=dict(data.get("options", {})),
        raw=data,
    )
