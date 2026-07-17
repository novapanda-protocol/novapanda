"""生产级环境校验（启动时；默认 warn，STRICT 时阻断）。"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str  # error | warn | info
    message: str


@dataclass
class EnvironmentValidator:
    """校验生产密钥槽与持久化路径可用性。"""

    def validate(
        self,
        env: Optional[dict[str, str]] = None,
        *,
        mode: str = "auto",
    ) -> list[ValidationIssue]:
        e = {k: str(v) for k, v in (env if env is not None else os.environ).items()}
        issues: list[ValidationIssue] = []
        production = self._is_production(e, mode)

        op_db = (e.get("NOVAPANDA_OPERATOR_DB") or "").strip()
        if production and not op_db:
            issues.append(
                ValidationIssue(
                    "E_OPERATOR_DB_MISSING",
                    "error",
                    "production requires NOVAPANDA_OPERATOR_DB",
                )
            )
        elif op_db:
            issues.extend(self._check_sqlite_path(op_db, "NOVAPANDA_OPERATOR_DB"))

        db = (e.get("NOVAPANDA_DB") or "").strip()
        if production and not db:
            issues.append(
                ValidationIssue(
                    "E_DB_MISSING",
                    "warn",
                    "NOVAPANDA_DB unset — node will use in-memory store",
                )
            )
        elif db:
            issues.extend(self._check_sqlite_path(db, "NOVAPANDA_DB"))

        fiat = (e.get("NOVAPANDA_FIAT_COMPLIANCE") or "stub").lower()
        settle_env = (e.get("NOVAPANDA_SETTLEMENT_ENV") or "sandbox").lower()
        live_secret = (
            e.get("STRIPE_LIVE_SECRET") or e.get("NOVAPANDA_FIAT_API_KEY") or ""
        ).strip()
        if fiat == "stripe" and settle_env in ("live", "production"):
            if not live_secret:
                issues.append(
                    ValidationIssue(
                        "E_STRIPE_LIVE_MISSING",
                        "error",
                        "stripe + live settlement requires STRIPE_LIVE_SECRET or NOVAPANDA_FIAT_API_KEY",
                    )
                )
            elif not (
                live_secret.startswith("sk_live_") or live_secret.startswith("rk_live_")
            ):
                issues.append(
                    ValidationIssue(
                        "E_STRIPE_LIVE_FORMAT",
                        "error",
                        "STRIPE_LIVE_SECRET must start with sk_live_ (or rk_live_)",
                    )
                )
        elif live_secret.startswith("sk_test_"):
            issues.append(
                ValidationIssue(
                    "I_STRIPE_TEST_KEY",
                    "info",
                    "using Stripe test secret — OK for sandbox",
                )
            )

        rpc = (e.get("NOVAPANDA_EVM_RPC_URL") or e.get("NOVAPANDA_SOLANA_RPC_URL") or "").strip()
        signer = (e.get("SIGNER_BROADCAST_KEY") or "").strip()
        if rpc and not signer and production:
            issues.append(
                ValidationIssue(
                    "E_SIGNER_MISSING",
                    "error",
                    "RPC configured in production but SIGNER_BROADCAST_KEY missing",
                )
            )
        if signer and signer not in ("SIMULATED",) and not signer.startswith("test:"):
            if len(signer) < 16:
                issues.append(
                    ValidationIssue(
                        "E_SIGNER_WEAK",
                        "warn",
                        "SIGNER_BROADCAST_KEY looks too short",
                    )
                )

        auth = (e.get("NOVAPANDA_AUTH") or "1").strip()
        if production and auth in ("0", "false", "off"):
            issues.append(
                ValidationIssue(
                    "E_AUTH_DISABLED",
                    "error",
                    "NOVAPANDA_AUTH must be enabled in production",
                )
            )

        return issues

    def assert_or_raise(self, issues: list[ValidationIssue], *, strict: bool) -> None:
        errors = [i for i in issues if i.severity == "error"]
        if strict and errors:
            msg = "; ".join(f"{i.code}:{i.message}" for i in errors)
            raise RuntimeError(f"environment validation failed: {msg}")

    def _is_production(self, e: dict[str, str], mode: str) -> bool:
        if mode == "production":
            return True
        if mode == "development":
            return False
        # auto
        if (e.get("NOVAPANDA_ENV") or "").lower() in ("production", "prod", "live"):
            return True
        if (e.get("NOVAPANDA_SETTLEMENT_ENV") or "").lower() in ("live", "production"):
            return True
        return False

    def _check_sqlite_path(self, path: str, label: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            # touch connectivity
            cx = sqlite3.connect(str(p))
            cx.execute("SELECT 1")
            cx.close()
        except Exception as exc:  # noqa: BLE001
            issues.append(
                ValidationIssue(
                    "E_DB_UNAVAILABLE",
                    "error",
                    f"{label} not usable at {path}: {exc}",
                )
            )
        return issues


def validate_startup_environ(*, strict: Optional[bool] = None) -> list[ValidationIssue]:
    """供 create_app_from_config 调用。"""
    raw = (os.environ.get("NOVAPANDA_STRICT_ENV") or "").strip().lower()
    if strict is None:
        strict = raw in ("1", "true", "yes", "on")
    v = EnvironmentValidator()
    issues = v.validate(mode="auto")
    v.assert_or_raise(issues, strict=bool(strict))
    return issues
