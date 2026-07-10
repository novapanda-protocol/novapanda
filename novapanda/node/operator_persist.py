"""Operator registry persistence helpers (JSON file; body layer)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .operators import Operator, OperatorRegistry


def load_operator_registry(path: Optional[str] = None) -> OperatorRegistry:
    reg = OperatorRegistry()
    path = path or os.environ.get("NOVAPANDA_OPERATOR_DB")
    if not path:
        return reg
    p = Path(path)
    if not p.is_file():
        reg._persist_path = str(p)  # type: ignore[attr-defined]
        return reg
    raw = json.loads(p.read_text(encoding="utf-8"))
    for row in raw.get("operators", []):
        op = Operator(
            operator_id=row["operator_id"],
            email=row["email"],
            display_name=row.get("display_name", ""),
            status=row.get("status", "pending"),
            password_salt=row["password_salt"],
            password_hash=row["password_hash"],
            quota_propose_per_day=int(row.get("quota_propose_per_day", 20)),
            created_at=row.get("created_at", ""),
            email_verified=bool(row.get("email_verified", False)),
            last_login_at=row.get("last_login_at"),
            terms_accepted_at=row.get("terms_accepted_at"),
            deletion_requested_at=row.get("deletion_requested_at"),
        )
        reg._by_id[op.operator_id] = op
        reg._by_email[op.email] = op.operator_id
    reg._sessions = dict(raw.get("sessions") or {})
    # quota counters
    reg._propose_counts = dict(raw.get("propose_counts") or {})
    reg._persist_path = str(p)  # type: ignore[attr-defined]
    return reg


def save_operator_registry(reg: OperatorRegistry) -> None:
    path = getattr(reg, "_persist_path", None)
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "operators": [
            {
                "operator_id": op.operator_id,
                "email": op.email,
                "display_name": op.display_name,
                "status": op.status,
                "password_salt": op.password_salt,
                "password_hash": op.password_hash,
                "quota_propose_per_day": op.quota_propose_per_day,
                "created_at": op.created_at,
                "email_verified": op.email_verified,
                "last_login_at": op.last_login_at,
                "terms_accepted_at": op.terms_accepted_at,
                "deletion_requested_at": op.deletion_requested_at,
            }
            for op in reg._by_id.values()
        ],
        "sessions": dict(getattr(reg, "_sessions", {})),
        "propose_counts": dict(getattr(reg, "_propose_counts", {})),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
