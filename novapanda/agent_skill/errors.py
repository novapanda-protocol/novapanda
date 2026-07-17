"""Agent 可恢复错误：LLM 可读码 + 恢复动作（非堆栈甩锅）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class RecoveryAction(str, Enum):
    """Agent 应如何处置。"""

    RETRY_SAME = "retry_same"  # 稍后原样重试（瞬时 RPC）
    RETRY_ADJUST = "retry_adjust"  # 调参后重试（价格/路由/gas）
    SWITCH_PROVIDER = "switch_provider"  # 换投标方 / 挂牌
    SWITCH_RAIL = "switch_rail"  # 换结算轨 / 链
    ESCALATE_HUMAN = "escalate_human"  # 必须运维介入（密钥/合规/账本损坏）


@dataclass(frozen=True)
class AgentFault:
    """结构化故障，可直接塞进 Function Calling 的 tool result。

    字段均为短字符串/小数，避免 hex 堆栈污染上下文。
    """

    code: str
    message: str
    recovery: RecoveryAction
    retryable: bool
    hint: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["recovery"] = self.recovery.value
        return d


def fault_from_mapping(
    *,
    code: str,
    message: str,
    recovery: RecoveryAction,
    retryable: bool,
    hint: str,
    details: Optional[dict[str, Any]] = None,
) -> AgentFault:
    return AgentFault(
        code=code,
        message=message,
        recovery=recovery,
        retryable=retryable,
        hint=hint,
        details=dict(details or {}),
    )


def classify_exception(exc: BaseException) -> AgentFault:
    """把钱包/结算/RPC/编排异常映射为 AgentFault。

    优先读异常上的 ``code`` / ``recovery`` / ``retryable`` 属性（若调用方已标注）。
    """
    if isinstance(exc, AgentFault):
        return exc

    code = getattr(exc, "code", None)
    recovery_raw = getattr(exc, "recovery", None)
    retryable = getattr(exc, "retryable", None)
    details = dict(getattr(exc, "details", None) or {})
    msg = str(exc) or exc.__class__.__name__
    low = msg.lower()

    # 仅当调用方显式标注了非默认 code 时走结构化路径（否则落到启发式）
    _generic = {None, "", "WALLET_ERROR", "SETTLEMENT_ERROR"}
    if code not in _generic and recovery_raw is not None and retryable is not None:
        try:
            recovery = (
                recovery_raw
                if isinstance(recovery_raw, RecoveryAction)
                else RecoveryAction(str(recovery_raw))
            )
        except ValueError:
            recovery = RecoveryAction.ESCALATE_HUMAN
        return AgentFault(
            code=str(code),
            message=_short_msg(msg),
            recovery=recovery,
            retryable=bool(retryable),
            hint=str(getattr(exc, "hint", "") or _hint_for(str(code), recovery)),
            details=details,
        )

    # —— 启发式（兼容现有 WalletError / SettlementError 纯字符串）——
    if "timeout" in low or "timed out" in low:
        return fault_from_mapping(
            code="RPC_TIMEOUT",
            message="Chain RPC timed out",
            recovery=RecoveryAction.RETRY_SAME,
            retryable=True,
            hint="Wait briefly and retry the same call; if repeated, switch RPC endpoint.",
            details={"cause": _short_msg(msg)},
        )
    if "insufficient" in low and ("fee" in low or "paymaster" in low or "4337" in low):
        return fault_from_mapping(
            code="PAYMASTER_UNDERFUNDED",
            message="Paymaster or fee-token balance too low",
            recovery=RecoveryAction.RETRY_ADJUST,
            retryable=True,
            hint="Top up fee token, lower gas, or switch to a funded paymaster.",
            details={"cause": _short_msg(msg)},
        )
    if "insufficient" in low and ("balance" in low or "sol" in low or "vault" in low):
        return fault_from_mapping(
            code="INSUFFICIENT_BALANCE",
            message="Account or escrow vault underfunded",
            recovery=RecoveryAction.RETRY_ADJUST,
            retryable=True,
            hint="Reduce amount or fund the wallet/vault, then retry.",
            details={"cause": _short_msg(msg)},
        )
    if "gas" in low and ("estimate" in low or "fallback" in low):
        return fault_from_mapping(
            code="GAS_ESTIMATE_DEGRADED",
            message="Gas estimate failed; degraded fallback may apply",
            recovery=RecoveryAction.RETRY_SAME,
            retryable=True,
            hint="Retry estimate; if degraded persists, use default gas with caution.",
            details={"cause": _short_msg(msg)},
        )
    if "stripe" in low or "card" in low or "payment_intent" in low:
        return fault_from_mapping(
            code="STRIPE_ERROR",
            message="Fiat/Stripe rail rejected the request",
            recovery=RecoveryAction.ESCALATE_HUMAN
            if "sk_live" in low or "unauthorized" in low
            else RecoveryAction.RETRY_ADJUST,
            retryable="unauthorized" not in low and "sk_live" not in low,
            hint="Check payment method / amount; live key issues need human ops.",
            details={"cause": _short_msg(msg)},
        )
    if "rpc" in low or "jsonrpc" in low or "connection" in low:
        return fault_from_mapping(
            code="RPC_ERROR",
            message="Chain RPC call failed",
            recovery=RecoveryAction.RETRY_SAME,
            retryable=True,
            hint="Retry later; if persistent, switch_rail or change RPC URL (human).",
            details={"cause": _short_msg(msg)},
        )
    if "escrow" in low and ("冲突" in msg or "conflict" in low or "未知" in msg):
        return fault_from_mapping(
            code="SETTLEMENT_CONFLICT",
            message="Settlement handle state conflict",
            recovery=RecoveryAction.ESCALATE_HUMAN,
            retryable=False,
            hint="Do not retry blindly; inspect handle status or escalate to ops.",
            details={"cause": _short_msg(msg)},
        )
    if "signer_broadcast" in low or "live secret" in low or "signing backend" in low:
        return fault_from_mapping(
            code="SIGNER_NOT_WIRED",
            message="Live signing is not configured for this host",
            recovery=RecoveryAction.ESCALATE_HUMAN,
            retryable=False,
            hint="Ops must attach an L2+ signer; Agent cannot fix this alone.",
            details={"cause": _short_msg(msg)},
        )
    if "unfilled" in low or "no eligible" in low or "auction" in low:
        return fault_from_mapping(
            code="AUCTION_UNFILLED",
            message="Auction could not fill one or more subtasks",
            recovery=RecoveryAction.RETRY_ADJUST,
            retryable=True,
            hint="Raise budget, relax tags/SLA, or switch_provider listings.",
            details={"cause": _short_msg(msg)},
        )
    if "deadlock" in low or "not all legs" in low or "leg ended" in low:
        return fault_from_mapping(
            code="ORCHESTRATION_FAILED",
            message="Supply-chain DAG failed to complete",
            recovery=RecoveryAction.SWITCH_PROVIDER,
            retryable=True,
            hint="Re-auction failed legs or switch providers; check depends_on.",
            details={"cause": _short_msg(msg)},
        )
    if "mismatch" in low and "chain" in low:
        return fault_from_mapping(
            code="CHAIN_MISMATCH",
            message="Asset/chain mismatch",
            recovery=RecoveryAction.RETRY_ADJUST,
            retryable=True,
            hint="Align chain_id and asset; do not send hex blindly—use structured AssetRef fields.",
            details={"cause": _short_msg(msg)},
        )

    return fault_from_mapping(
        code="UNKNOWN_ERROR",
        message=_short_msg(msg),
        recovery=RecoveryAction.ESCALATE_HUMAN,
        retryable=False,
        hint="Unrecognized failure; escalate to human with this code and message.",
        details={"exc_type": type(exc).__name__},
    )


def _short_msg(msg: str, limit: int = 180) -> str:
    one = " ".join(msg.split())
    if len(one) <= limit:
        return one
    return one[: limit - 1] + "…"


def _hint_for(code: str, recovery: RecoveryAction) -> str:
    if recovery == RecoveryAction.RETRY_SAME:
        return f"{code}: retry the same parameters after a short backoff."
    if recovery == RecoveryAction.RETRY_ADJUST:
        return f"{code}: adjust price, amount, or route then retry."
    if recovery == RecoveryAction.SWITCH_PROVIDER:
        return f"{code}: pick another provider/listing and retry."
    if recovery == RecoveryAction.SWITCH_RAIL:
        return f"{code}: switch settlement rail or chain."
    return f"{code}: stop autonomous retries; notify human ops."
