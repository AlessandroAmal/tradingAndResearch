"""Alert evaluation engine (M8).

Checks enabled rules + standing categories against current data and dispatches
via the configured Notifier. Read-only: it NOTIFIES facts/flags, never trades.

Two rule kinds:
  - user threshold rules ('price' | 'iv'): edge-triggered + cooldown via the
    rule's own last_state/last_triggered.
  - standing categories ('standing'): per-item events (breaches, deadlines,
    new key-figure statements, universe news, IV spikes) deduped via the
    alerts LOG (dedup_key) within the cooldown window.

Messages are factual (a flag/threshold/fact), not predictions.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from ..config import AppConfig
from ..logging_setup import get_logger
from ..notify import Notifier
from ..risk import evaluate_position, pct_of_account, portfolio_heat
from ..storage import Storage
from .rules import should_fire, threshold_met

log = get_logger("alerts.engine")


def _parse_dt(v) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def run_alert_evaluation(
    cfg: AppConfig, storage: Storage, notifier: Notifier, now: datetime | None = None
) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    try:
        rules = storage.list_alert_rules(enabled_only=True)
    except Exception as exc:  # noqa: BLE001
        log.error("Could not load alert rules: %s", exc)
        return {"sent": 0, "failed": 1}

    sent = 0
    for rule in rules:
        try:
            if rule.get("kind") in ("price", "iv"):
                sent += _eval_threshold_rule(cfg, storage, notifier, rule, now)
            elif rule.get("kind") == "standing":
                sent += _eval_standing(cfg, storage, notifier, rule, now)
        except Exception as exc:  # noqa: BLE001 — isolate per-rule
            log.error("Alert rule %s failed: %s", rule.get("id"), exc)

    log.info("Alert evaluation done: %d dispatched (%d rules)", sent, len(rules))
    return {"sent": sent, "rules": len(rules)}


# --- user threshold rules --------------------------------------------
def _current_value(storage: Storage, rule: dict) -> float | None:
    symbol = rule.get("symbol")
    if rule["kind"] == "price":
        iid = storage.get_instrument_id(symbol) if symbol else None
        return storage.get_latest_close(iid) if iid else None
    if rule["kind"] == "iv":
        return storage.get_atm_iv(symbol) if symbol else None
    return None


def _eval_threshold_rule(cfg, storage, notifier, rule, now) -> int:
    op = rule.get("op", "above")
    threshold = float(rule.get("threshold"))
    current = _current_value(storage, rule)
    condition = threshold_met(op, current, threshold)
    cooldown = int(rule.get("cooldown_seconds", 3600))
    fire = should_fire(condition, bool(rule.get("last_state")), _parse_dt(rule.get("last_triggered")), cooldown, now)

    # Always persist the new edge state.
    storage.update_alert_rule_state(
        rule["id"],
        now.isoformat() if fire else rule.get("last_triggered"),
        condition,
    )
    if not fire:
        return 0

    kind = rule["kind"]
    unit = "" if kind == "price" else " IV"
    shown = f"{current:.4f}" if kind == "iv" else f"{current}"
    msg = (
        f"⚠️ {rule.get('symbol')}{unit} {('sopra' if op == 'above' else 'sotto')} "
        f"{threshold}: ora {shown}"
    )
    # An alert was raised + logged (counts even if dispatch was skipped).
    _fire(storage, notifier, kind=kind, symbol=rule.get("symbol"),
          message=msg, severity="warning",
          dedup_key=f"rule:{rule['id']}", rule_id=rule["id"])
    return 1


# --- standing categories ---------------------------------------------
def _eval_standing(cfg, storage, notifier, rule, now) -> int:
    st = rule.get("standing_type")
    cooldown = int(rule.get("cooldown_seconds", 3600))
    since = (now.timestamp() - cooldown)
    since_iso = datetime.fromtimestamp(since, tz=timezone.utc).isoformat()
    rid = rule["id"]
    sent = 0

    def maybe(dedup_key, message, severity, symbol=None) -> None:
        nonlocal sent
        if storage.recent_alert_exists(dedup_key, since_iso):
            return
        if _fire(storage, notifier, kind="standing", symbol=symbol,
                 message=message, severity=severity, dedup_key=dedup_key, rule_id=rid):
            sent += 1
        else:
            sent += 1  # counted as evaluated/logged even if dispatch skipped

    if st in ("risk", "deadline"):
        sent += _standing_positions(cfg, storage, st, maybe, now)
    elif st == "key_figure":
        for s in storage.list_recent_figure_statements(hours=24, limit=30):
            maybe(f"figure:{s['id']}", f"🗣 {s.get('figure')}: {(s.get('statement') or '')[:160]}", "info", s.get("figure"))
    elif st == "universe_news":
        for n in storage.list_recent_news(hours=6, limit=40):
            if n.get("instruments"):
                maybe(f"news:{n['id']}", f"📰 {', '.join(n['instruments'])}: {(n.get('title') or '')[:160]}", "info")
    elif st == "iv_spike":
        thr = float((cfg.alerts or {}).get("iv_spike_threshold", 0.6))
        for u in storage.get_distinct_option_underlyings():
            iv = storage.get_atm_iv(u)
            if iv is not None and iv >= thr:
                maybe(f"ivspike:{u}", f"📈 {u}: IV ATM elevata {iv:.0%} (≥ {thr:.0%})", "warning", u)
    return sent


def _standing_positions(cfg, storage, st, maybe, now) -> int:
    account = cfg.account_size
    mult_by = cfg.multiplier_by_symbol
    today = now.date()
    risks: list[float | None] = []
    for p in storage.list_positions("open"):
        symbol = p.get("symbol")
        iid = p.get("instrument_id")
        current = storage.get_latest_close(iid) if iid else None
        pr = evaluate_position(
            side=p.get("side", "long"), entry=float(p.get("entry", 0) or 0),
            stop=_num(p.get("stop")), target=_num(p.get("target")),
            size=float(p.get("size", 0) or 0), current_price=current,
            account_size=account, max_risk_per_trade_pct=cfg.max_risk_per_trade_pct,
            multiplier=mult_by.get(symbol, 1.0), deadline=_parse_date(p.get("deadline")),
            today=today, deadline_warn_days=cfg.deadline_warn_days,
        )
        risks.append(pr.open_risk)
        if st == "risk":
            if pr.stop_breached:
                maybe(f"risk:stop:{p['id']}", f"🛑 {symbol}: stop bucato (prezzo {current})", "critical", symbol)
            if pr.risk_per_trade_breached:
                maybe(f"risk:trade:{p['id']}", f"⚠️ {symbol}: rischio per trade oltre il limite ({pr.open_risk_pct:.1f}%)", "warning", symbol)
        elif st == "deadline" and pr.deadline_near:
            maybe(f"deadline:{p['id']}", f"⏳ {symbol}: deadline tra {pr.days_to_deadline} giorni", "warning", symbol)

    if st == "risk":
        heat = portfolio_heat(risks)
        heat_pct = pct_of_account(heat, account)
        if heat_pct is not None and heat_pct > cfg.max_portfolio_heat_pct:
            maybe("risk:heat", f"🔥 Portfolio heat {heat_pct:.1f}% oltre il limite {cfg.max_portfolio_heat_pct}%", "warning")
    return 0  # counts handled inside maybe()


# --- dispatch + log ---------------------------------------------------
def _fire(storage, notifier, *, kind, symbol, message, severity, dedup_key, rule_id) -> bool:
    delivered = notifier.send(message)
    try:
        storage.insert_alert({
            "kind": kind, "symbol": symbol, "message": message, "severity": severity,
            "payload": {"dedup_key": dedup_key}, "dedup_key": dedup_key, "rule_id": rule_id,
            "delivered": delivered,
            "delivered_at": datetime.now(timezone.utc).isoformat() if delivered else None,
        })
    except Exception as exc:  # noqa: BLE001
        log.error("Could not log alert (%s): %s", dedup_key, exc)
    log.info("Alert %s delivered=%s: %s", dedup_key, delivered, message.split(chr(10))[0])
    return delivered


def _num(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _parse_date(v):
    if not v or not isinstance(v, str):
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        return None
