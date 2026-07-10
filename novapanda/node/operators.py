"""运营账户（Operator）— 身体层；不参与 Agent 交割鉴权。

策略 A：匿名仍可 propose；注册仅提升配额与控制台「我的」视图（后续）。
v0：内存存储 + 邮箱 OTP  stub（验证码固定可测）；生产换持久化与真邮件。
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


@dataclass
class Operator:
    operator_id: str
    email: str
    display_name: str
    status: str  # pending | active | suspended
    password_salt: str
    password_hash: str
    quota_propose_per_day: int
    created_at: str
    email_verified: bool = False
    last_login_at: Optional[str] = None
    terms_accepted_at: Optional[str] = None
    deletion_requested_at: Optional[str] = None


@dataclass
class OperatorRegistry:
    """进程内注册表；create_app 挂到 app.state.operators。

    可选 NOVAPANDA_OPERATOR_DB 经 operator_persist 落盘。
    """

    anonymous_propose_per_day: int = 20
    verified_propose_per_day: int = 200
    _by_id: dict[str, Operator] = field(default_factory=dict)
    _by_email: dict[str, str] = field(default_factory=dict)
    _otps: dict[str, str] = field(default_factory=dict)  # email -> otp
    _sessions: dict[str, str] = field(default_factory=dict)  # token -> operator_id
    _propose_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    # day_key -> { bucket_id -> count }

    def register(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        accept_terms: bool,
    ) -> tuple[Operator, str]:
        email_n = email.strip().lower()
        if not email_n or "@" not in email_n:
            raise ValueError("invalid_email")
        if not accept_terms:
            raise ValueError("terms_required")
        if email_n in self._by_email:
            raise ValueError("email_taken")
        salt = secrets.token_hex(8)
        op = Operator(
            operator_id=str(uuid.uuid4()),
            email=email_n,
            display_name=display_name.strip() or email_n.split("@")[0],
            status="pending",
            password_salt=salt,
            password_hash=_hash_password(password, salt),
            quota_propose_per_day=self.anonymous_propose_per_day,
            created_at=_now(),
            terms_accepted_at=_now() if accept_terms else None,
        )
        self._by_id[op.operator_id] = op
        self._by_email[email_n] = op.operator_id
        otp = f"{secrets.randbelow(10**6):06d}"
        self._otps[email_n] = otp
        self._maybe_persist()
        return op, otp

    def verify_email(self, *, email: str, otp: str) -> Operator:
        email_n = email.strip().lower()
        expected = self._otps.get(email_n)
        if not expected or expected != otp.strip():
            raise ValueError("invalid_otp")
        oid = self._by_email.get(email_n)
        if not oid:
            raise ValueError("not_found")
        op = self._by_id[oid]
        op.email_verified = True
        op.status = "active"
        op.quota_propose_per_day = self.verified_propose_per_day
        del self._otps[email_n]
        self._maybe_persist()
        return op

    def login(self, *, email: str, password: str) -> tuple[Operator, str]:
        email_n = email.strip().lower()
        oid = self._by_email.get(email_n)
        if not oid:
            raise ValueError("invalid_credentials")
        op = self._by_id[oid]
        if op.status == "suspended":
            raise ValueError("suspended")
        if _hash_password(password, op.password_salt) != op.password_hash:
            raise ValueError("invalid_credentials")
        if not op.email_verified:
            raise ValueError("email_unverified")
        token = secrets.token_urlsafe(24)
        self._sessions[token] = op.operator_id
        op.last_login_at = _now()
        self._maybe_persist()
        return op, token

    def resolve_session(self, token: Optional[str]) -> Optional[Operator]:
        if not token:
            return None
        oid = self._sessions.get(token)
        if not oid:
            return None
        return self._by_id.get(oid)

    def public_view(self, op: Operator) -> dict:
        return {
            "operator_id": op.operator_id,
            "email": op.email,
            "display_name": op.display_name,
            "status": op.status,
            "email_verified": op.email_verified,
            "quota_propose_per_day": op.quota_propose_per_day,
            "created_at": op.created_at,
            "last_login_at": op.last_login_at,
            "deletion_requested_at": op.deletion_requested_at,
        }

    def policy_snapshot(self) -> dict:
        return {
            "access_policy": "open_quota",
            "anonymous_propose_per_day": self.anonymous_propose_per_day,
            "verified_propose_per_day": self.verified_propose_per_day,
            "note": "Operator 登录不替代 Agent Ed25519 交割鉴权",
        }

    def _day_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def quota_remaining(self, *, operator: Optional[Operator] = None, anon_key: str = "anon") -> dict:
        day = self._day_key()
        bucket = operator.operator_id if operator else f"anon:{anon_key}"
        limit = (
            operator.quota_propose_per_day
            if operator
            else self.anonymous_propose_per_day
        )
        used = int((self._propose_counts.get(day) or {}).get(bucket, 0))
        return {
            "day": day,
            "bucket": bucket,
            "limit": limit,
            "used": used,
            "remaining": max(0, limit - used),
            "authenticated": operator is not None,
        }

    def consume_propose(self, *, operator: Optional[Operator] = None, anon_key: str = "anon") -> dict:
        """原子检查并 +1；超额抛 ValueError('quota_exceeded')。"""
        snap = self.quota_remaining(operator=operator, anon_key=anon_key)
        if snap["remaining"] <= 0:
            raise ValueError("quota_exceeded")
        day = snap["day"]
        bucket = snap["bucket"]
        self._propose_counts.setdefault(day, {})
        self._propose_counts[day][bucket] = snap["used"] + 1
        out = self.quota_remaining(operator=operator, anon_key=anon_key)
        self._maybe_persist()
        return out

    def request_deletion(self, operator_id: str) -> Operator:
        op = self._by_id.get(operator_id)
        if op is None:
            raise ValueError("not_found")
        if op.deletion_requested_at:
            return op
        op.deletion_requested_at = _now()
        self._maybe_persist()
        return op

    def cancel_deletion(self, operator_id: str) -> Operator:
        op = self._by_id.get(operator_id)
        if op is None:
            raise ValueError("not_found")
        op.deletion_requested_at = None
        self._maybe_persist()
        return op

    def invalidate_sessions(self, operator_id: str) -> None:
        drop = [t for t, oid in self._sessions.items() if oid == operator_id]
        for t in drop:
            del self._sessions[t]

    def _maybe_persist(self) -> None:
        path = getattr(self, "_persist_path", None)
        if not path:
            return
        try:
            from .operator_persist import save_operator_registry

            save_operator_registry(self)
        except Exception:
            pass
