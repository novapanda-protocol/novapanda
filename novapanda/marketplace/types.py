"""服务发现市场与动态声誉 — 数据结构（无业务逻辑）。

命名对齐现有约定：
- ``agent_id`` = ``ed25519:<base58>``
- ``resource_type`` / ``rule_id`` 与 Exchange / VDC 字段同形
- 声誉 outcome ∈ {settled, rejected, expired, cancelled}（见 reputation-entry schema）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional, TypedDict


# ----- 挂牌 / 发现 -----

OutcomeName = Literal["settled", "rejected", "expired", "cancelled"]
PartyRole = Literal["client", "provider"]


class ListingStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True)
class SlaOffer:
    """结构化 SLA 承诺（非自然语言）。"""

    max_response_ms: int
    min_throughput_qps: int = 0
    availability_bips: int = 9900  # 99.00% → 9900 bips
    verify_backend_hint: Optional[str] = None  # e.g. backend:local-schema/v1


@dataclass(frozen=True)
class PriceQuote:
    """基准价；币种与 Exchange.price 对齐。"""

    amount: int
    currency: str
    unit: str = "per_exchange"  # per_exchange | per_quantity


@dataclass(frozen=True)
class ServiceListing:
    """Agent 挂牌：能力 + SLA + 基准价。

    与 Manifest 关系：``agent_id`` / ``capabilities`` 可从 Manifest 投影；
    市场字段（price/sla/listing_id）是 Manifest 之上的交易扩展，不替代自签 Manifest。
    """

    listing_id: str
    agent_id: str
    resource_type: str
    capability_tags: tuple[str, ...]
    sla: SlaOffer
    price: PriceQuote
    endpoints: dict[str, Any]  # 至少含 exchange
    status: ListingStatus = ListingStatus.ACTIVE
    rule_id_hint: Optional[str] = None
    content_hash: Optional[str] = None  # sha256:… 供链上锚定
    ttl_sec: int = 3600
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ListingCommitment:
    """链上索引条目：仅 commitment，不含完整挂牌正文。"""

    listing_id: str
    agent_id: str
    content_hash: str
    expires_at_ts: float


# ----- 参数化需求 / 撮合 -----


@dataclass(frozen=True)
class MatchQuery:
    """Client 侧结构化需求（替代 NL 谈判）。"""

    resource_type: str
    quantity: int
    max_price: PriceQuote
    max_response_ms: int
    min_reputation: float = 0.0
    required_tags: tuple[str, ...] = ()
    preferred_tags: tuple[str, ...] = ()
    client_agent_id: Optional[str] = None
    limit: int = 10


@dataclass(frozen=True)
class MatchScoreBreakdown:
    """撮合解释性拆解（实现阶段填权重；本步仅形状）。"""

    total: float
    price_score: float
    sla_score: float
    reputation_score: float
    tag_score: float
    risk_penalty: float


@dataclass(frozen=True)
class ProviderCandidate:
    listing: ServiceListing
    reputation: "ReputationView"
    breakdown: MatchScoreBreakdown


@dataclass(frozen=True)
class MatchDecision:
    """撮合输出：有序列表；winner 供 ``ExchangeEngine.propose(provider=…)``。"""

    query: MatchQuery
    ranked: tuple[ProviderCandidate, ...]
    winner: Optional[ProviderCandidate]
    reason: str = ""


# ----- 声誉视图 / 风险（派生，非 SM 状态） -----


@dataclass(frozen=True)
class ReputationView:
    """ScoreEngine 对外只读视图（可缓存）。"""

    agent_id: str
    score: Optional[float]  # [0,1]；None = 无历史
    entry_count: int
    settled_count: int
    rejected_count: int
    volume_score: float = 0.0  # 金额加权分量占位
    risk_penalty: float = 0.0
    effective_score: Optional[float] = None  # 含 witness / 惩罚后
    score_version: str = "0.0-design"


class RiskKind(str, Enum):
    SYBIL_CLUSTER = "sybil_cluster"
    WASH_TRADE = "wash_trade"
    BURST_SELF_DEAL = "burst_self_deal"
    NEW_IDENTITY = "new_identity"


@dataclass(frozen=True)
class RiskSignal:
    kind: RiskKind
    subject_agent_id: str
    severity: float  # [0,1]
    evidence_ref: str  # 可复验引用（entry_hash / cluster_id）
    observed_at: str


@dataclass(frozen=True)
class ExchangeTerminalSnapshot:
    """Read-only terminal projection for Sink / reputation (no SM mutations).

    Fields are small scalars (ids, state, integer amount). For LLM context,
    prefer ``novapanda.agent_skill.compact_terminal_snapshot`` which shortens
    agent ids and drops anything not needed for decisions.
    """

    exchange_id: str
    state: str  # SETTLED | REJECTED | EXPIRED_REFUNDED | CANCELLED | …
    client: str
    provider: str
    resource_type: str
    quantity: int
    vdc_id: Optional[str]
    price_amount: int
    price_currency: str
    outcome_hint: Optional[OutcomeName] = None


# ----- TypedDict：与现有 gate / HTTP JSON 对齐 -----


class GateResultDict(TypedDict, total=False):
    allowed: bool
    score: Optional[float]
    effective_score: Optional[float]
    witness_bonus: float
    entry_count: int
    reason: str


class ProposeHints(TypedDict, total=False):
    """MatchDecision → propose 的可选提示（不进签名、不进 CORE）。"""

    listing_id: str
    match_total: float
    rule_id_hint: str
    settlement_rail_hint: str
