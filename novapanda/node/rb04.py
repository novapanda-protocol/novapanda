"""RB-04 — settlement intent stale / held escrow scan (T17)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    s = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def scan_settlement_health(
    *,
    engine,
    settlement,
    pending_sla_minutes: int = 15,
    held_sla_minutes: int = 30,
) -> dict[str, Any]:
    """Return stale pending intents and long-held escrows for RB-04."""
    now = datetime.now(timezone.utc)
    stale_pending: list[dict] = []
    held_escrows: list[dict] = []

    for ex in engine._store.values():
        intent = getattr(ex, "settlement_intent", None)
        if intent and intent.get("status") == "pending":
            updated = _parse_iso(getattr(ex, "updated_at", None))
            age_min = (now - updated).total_seconds() / 60 if updated else pending_sla_minutes + 1
            if age_min >= pending_sla_minutes:
                stale_pending.append(
                    {
                        "exchange_id": ex.exchange_id,
                        "state": ex.state,
                        "intent": intent,
                        "age_minutes": round(age_min, 1),
                    }
                )

    holds = getattr(settlement, "_holds", None)
    if isinstance(holds, dict):
        for handle, h in holds.items():
            if h.get("status") != "held":
                continue
            held_escrows.append(
                {
                    "handle": handle,
                    "exchange_id": h.get("exchange_id"),
                    "amount": h.get("amount"),
                    "currency": h.get("currency"),
                    "status": h.get("status"),
                    "note": f"held > {held_sla_minutes}m SLA (snapshot)",
                }
            )

    return {
        "stale_pending": stale_pending,
        "held_escrows": held_escrows,
        "stale_pending_count": len(stale_pending),
        "held_escrow_count": len(held_escrows),
        "pending_sla_minutes": pending_sla_minutes,
        "held_sla_minutes": held_sla_minutes,
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
