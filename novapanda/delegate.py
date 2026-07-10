"""NP-DELEGATE · temporary delegation credentials (body layer)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .canonical import canonical_bytes
from .identity import verify

_PERIOD_RE = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?)?$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def delegation_signing_bytes(credential: dict[str, Any]) -> bytes:
    unsigned = {
        k: v
        for k, v in credential.items()
        if k not in ("issuer_sig", "revoked")
    }
    return canonical_bytes(unsigned)


@dataclass
class DelegationRegistry:
    """In-memory delegation store for trial / reference node."""

    max_ttl_seconds: int = 86400
    _by_id: dict[str, dict] = field(default_factory=dict)
    _revoked: set[str] = field(default_factory=set)
    _period_spent: dict[str, dict[str, int]] = field(default_factory=dict)

    def _period_key(self, period: Optional[str]) -> str:
        if not period:
            return _now().strftime("%Y-%m-%d")
        m = _PERIOD_RE.match(period.strip().upper())
        if not m:
            return _now().strftime("%Y-%m-%d")
        days = int(m.group(1) or 0)
        if days >= 1:
            return _now().strftime("%Y-%m-%d")
        return _now().strftime("%Y-%m-%dT%H")

    def register(self, credential: dict[str, Any]) -> dict:
        cred = dict(credential)
        if cred.get("delegate_version") != "0.1":
            raise ValueError("unsupported_delegate_version")
        scope = cred.get("scope") or []
        if not scope:
            raise ValueError("empty_scope")
        issuer = cred.get("issuer_agent_id")
        subject = cred.get("subject_agent_id")
        sig = cred.get("issuer_sig")
        expires_at = cred.get("expires_at")
        if not (issuer and subject and sig and expires_at):
            raise ValueError("missing_required_fields")
        if not verify(issuer, sig, delegation_signing_bytes(cred)):
            raise ValueError("invalid_issuer_sig")
        exp = _parse_ts(str(expires_at))
        if exp <= _now():
            raise ValueError("already_expired")
        nb = cred.get("not_before")
        if nb and _parse_ts(str(nb)) > _now():
            raise ValueError("not_yet_valid")
        ttl = (exp - _now()).total_seconds()
        if ttl > self.max_ttl_seconds:
            raise ValueError("ttl_exceeds_node_max")
        dlg_id = cred.get("delegation_id") or ("dlg_" + uuid.uuid4().hex[:12])
        cred["delegation_id"] = dlg_id
        cred.setdefault("issued_at", _now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        cred["revoked"] = False
        self._by_id[dlg_id] = cred
        return self.public(cred)

    def get(self, delegation_id: str) -> Optional[dict]:
        cred = self._by_id.get(delegation_id)
        if cred is None or delegation_id in self._revoked:
            return None
        if _parse_ts(str(cred["expires_at"])) <= _now():
            return None
        constraints = cred.get("constraints") or {}
        cexp = constraints.get("expires_at")
        if cexp and _parse_ts(str(cexp)) <= _now():
            return None
        return cred

    def revoke(self, delegation_id: str, *, issuer_agent_id: str) -> dict:
        cred = self._by_id.get(delegation_id)
        if cred is None:
            raise ValueError("not_found")
        if cred.get("issuer_agent_id") != issuer_agent_id:
            raise ValueError("not_issuer")
        self._revoked.add(delegation_id)
        cred = {**cred, "revoked": True}
        return self.public(cred)

    def validate_action(
        self,
        delegation_id: str,
        *,
        subject_agent_id: str,
        action: str,
        amount: Optional[int] = None,
        currency: Optional[str] = None,
        rail: Optional[str] = None,
    ) -> dict:
        cred = self.get(delegation_id)
        if cred is None:
            raise ValueError("delegation_invalid")
        if cred.get("subject_agent_id") != subject_agent_id:
            raise ValueError("subject_mismatch")
        scope = cred.get("scope") or []
        if action not in scope:
            raise ValueError("scope_denied")
        constraints = cred.get("constraints") or {}
        if amount is not None and constraints.get("max_amount") is not None:
            max_amt = int(constraints["max_amount"])
            if amount > max_amt:
                raise ValueError("amount_exceeds_max")
        if currency and constraints.get("currency"):
            if currency != constraints["currency"]:
                raise ValueError("currency_mismatch")
        allow = constraints.get("rails_allowlist")
        if rail and allow and rail not in allow:
            raise ValueError("rail_not_allowed")
        if amount is not None and constraints.get("max_amount") is not None:
            period = constraints.get("period")
            key = self._period_key(period)
            bucket = self._period_spent.setdefault(delegation_id, {})
            spent = bucket.get(key, 0) + amount
            if spent > int(constraints["max_amount"]):
                raise ValueError("period_quota_exceeded")
            bucket[key] = spent
        return cred

    def list_for_subject(self, subject_agent_id: str) -> list[dict]:
        out = []
        for cred in self._by_id.values():
            if cred.get("subject_agent_id") != subject_agent_id:
                continue
            if self.get(cred["delegation_id"]):
                out.append(self.public(cred))
        return sorted(out, key=lambda c: c.get("issued_at", ""), reverse=True)

    def public(self, cred: dict) -> dict:
        return {
            "delegate_version": cred.get("delegate_version"),
            "delegation_id": cred.get("delegation_id"),
            "issuer_agent_id": cred.get("issuer_agent_id"),
            "subject_agent_id": cred.get("subject_agent_id"),
            "scope": list(cred.get("scope") or []),
            "constraints": dict(cred.get("constraints") or {}),
            "not_before": cred.get("not_before"),
            "expires_at": cred.get("expires_at"),
            "issued_at": cred.get("issued_at"),
            "revoked": cred.get("delegation_id") in self._revoked or bool(cred.get("revoked")),
            "note": "delegation credential — not a balance account",
        }
