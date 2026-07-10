"""T14 reconcile export · build rows from exchanges + settlement holds + claims."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Optional

CSV_HEADER = (
    "exchange_id,handle,provider_ref,rail,currency,amount,intent_status,"
    "partner_status,match,vdc_id,captured_at,refunded_at,environment,notes"
)

CLAIM_CSV_HEADER = (
    "claim_id,vdc_id,rail,currency,amount,claim_status,holder,captured_at,environment,notes"
)


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _in_window(ts: str, *, from_ts: Optional[str], to_ts: Optional[str]) -> bool:
    dt = _parse_iso(ts)
    if dt is None:
        return True
    if from_ts:
        start = _parse_iso(from_ts)
        if start and dt < start:
            return False
    if to_ts:
        end = _parse_iso(to_ts)
        if end and dt > end:
            return False
    return True


def _env_for_settlement(settlement) -> str:
    rail = getattr(settlement, "rail", None)
    if rail == "mock" or type(settlement).__name__ == "MockSettlement":
        return "mock"
    env = getattr(settlement, "environment", None)
    return env or "production"


def _rail_for_settlement(settlement) -> str:
    return getattr(settlement, "rail", None) or (
        type(settlement).__name__.replace("Settlement", "").lower() or "unknown"
    )


def collect_reconcile_rows(*, engine, settlement) -> list[dict]:
    rows: list[dict] = []
    environment = _env_for_settlement(settlement)
    default_rail = _rail_for_settlement(settlement)

    for ex in engine._store.values():
        receipt = getattr(ex, "settlement_receipt", None)
        if not receipt:
            continue
        status = str(receipt.get("status", "unknown"))
        captured = getattr(ex, "updated_at", None) or datetime.now(timezone.utc).isoformat()
        refunded_at = captured if status == "refunded" else ""
        rows.append(
            {
                "exchange_id": ex.exchange_id,
                "handle": receipt.get("handle") or getattr(ex, "escrow_handle", "") or "",
                "provider_ref": receipt.get("provider_ref", ""),
                "rail": receipt.get("rail", default_rail),
                "currency": receipt.get("currency", ex.price.get("currency", "")),
                "amount": str(receipt.get("amount", ex.price.get("amount", ""))),
                "intent_status": status,
                "partner_status": "",
                "match": "node_only",
                "vdc_id": getattr(ex, "vdc_id", None) or "",
                "captured_at": captured,
                "refunded_at": refunded_at,
                "environment": receipt.get("environment", environment),
                "notes": "",
            }
        )

    holds = getattr(settlement, "_holds", None)
    if isinstance(holds, dict):
        seen = {r["handle"] for r in rows if r.get("handle")}
        for handle, h in holds.items():
            if handle in seen:
                continue
            status = str(h.get("status", "held"))
            if status not in ("held", "settled", "refunded"):
                continue
            rows.append(
                {
                    "exchange_id": h.get("exchange_id", ""),
                    "handle": handle,
                    "provider_ref": "",
                    "rail": default_rail,
                    "currency": h.get("currency", ""),
                    "amount": str(h.get("amount", "")),
                    "intent_status": status,
                    "partner_status": "",
                    "match": "unknown" if status == "held" else "node_only",
                    "vdc_id": "",
                    "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "refunded_at": "",
                    "environment": environment,
                    "notes": "settlement hold",
                }
            )
    return rows


def collect_claim_rows(*, claims, environment: str, default_rail: str = "mock") -> list[dict]:
    """Claim capture/spent 行（T14 扩展）。"""
    rows: list[dict] = []
    list_fn = getattr(claims, "list_for_holder", None)
    if list_fn is None:
        return rows
    for rec in list_fn(None):
        status = getattr(rec, "status", "")
        if status not in ("spent", "reserved", "open", "released"):
            continue
        issued = getattr(rec, "issued_at", None) or getattr(rec, "created_at", "")
        rows.append(
            {
                "claim_id": getattr(rec, "claim_id", ""),
                "vdc_id": getattr(rec, "vdc_id", ""),
                "rail": getattr(rec, "rail", default_rail),
                "currency": getattr(rec, "currency", "USD"),
                "amount": str(getattr(rec, "amount", "")),
                "claim_status": status,
                "holder": getattr(rec, "holder_agent_id", None) or getattr(rec, "holder", ""),
                "captured_at": issued,
                "environment": environment,
                "notes": "claim_row",
            }
        )
    return rows


def build_reconcile_export(
    *,
    engine,
    settlement,
    node_id: str,
    rail: Optional[str] = None,
    window: str = "T+1",
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    claims=None,
) -> dict:
    rows = collect_reconcile_rows(engine=engine, settlement=settlement)
    if from_ts or to_ts:
        rows = [r for r in rows if _in_window(r.get("captured_at", ""), from_ts=from_ts, to_ts=to_ts)]
    if rail:
        rows = [r for r in rows if r.get("rail") == rail]
    env = _env_for_settlement(settlement)
    claim_rows = collect_claim_rows(
        claims=claims,
        environment=env,
        default_rail=_rail_for_settlement(settlement),
    )
    if from_ts or to_ts:
        claim_rows = [
            r for r in claim_rows
            if _in_window(r.get("captured_at", ""), from_ts=from_ts, to_ts=to_ts)
        ]
    if rail:
        claim_rows = [r for r in claim_rows if r.get("rail") == rail]
    return {
        "meta": {
            "template_version": "0.1",
            "rail": rail or _rail_for_settlement(settlement),
            "window": window,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "node_id": node_id,
            "environment": env,
            "from": from_ts,
            "to": to_ts,
        },
        "rows": rows,
        "claim_rows": claim_rows,
    }


def export_claim_csv(package: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CLAIM_CSV_HEADER.split(","))
    writer.writeheader()
    for row in package.get("claim_rows", []):
        writer.writerow({k: row.get(k, "") for k in CLAIM_CSV_HEADER.split(",")})
    return buf.getvalue()


def export_csv(package: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_HEADER.split(","))
    writer.writeheader()
    for row in package.get("rows", []):
        writer.writerow({k: row.get(k, "") for k in CSV_HEADER.split(",")})
    return buf.getvalue()
