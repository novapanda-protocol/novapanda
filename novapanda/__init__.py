"""NovaPanda — verifiable delivery exchange protocol (reference implementation).

哲学底线（凌驾于一切实现）：普适通用 · 降低接入难度 · 要标准 · 要开放。
Litmus test：陌生 Agent 能否不依赖我方专有组件、不经许可，照规范完成交割并被任何人独立复验？答案必须永远是「能」。
"""

__version__ = "0.0.1"

from .identity import Identity, verify
from .canonical import canonical_bytes, canonical_str
from .hashing import sha256_hex, result_hash
from . import vdc
from . import state_machine
from .settlement import (
    AP2Settlement,
    FakeGateway,
    FiatSettlement,
    GatewaySettlement,
    MockSettlement,
    SettlementAdapter,
    SettlementError,
    X402Settlement,
)
from .verifier import AcceptAllVerifier, SchemaVerifier, Verifier
from .exchange import Exchange, ExchangeEngine, ExchangeError, NotFoundError
from .reputation import (
    InMemoryReputationStore,
    ReputationLog,
    SQLiteReputationStore,
)
from .store import ConcurrencyError, InMemoryStore, SQLiteStore
from .terms import sign_contract_ack, terms_hash_from_exchange, verify_contract_ack
from .manifest import build_agent_manifest, verify_agent_manifest

__all__ = [
    "Identity",
    "verify",
    "canonical_bytes",
    "canonical_str",
    "sha256_hex",
    "result_hash",
    "vdc",
    "state_machine",
    "MockSettlement",
    "SettlementAdapter",
    "SettlementError",
    "GatewaySettlement",
    "X402Settlement",
    "AP2Settlement",
    "FiatSettlement",
    "FakeGateway",
    "AcceptAllVerifier",
    "SchemaVerifier",
    "Verifier",
    "Exchange",
    "ExchangeEngine",
    "ExchangeError",
    "NotFoundError",
    "ReputationLog",
    "InMemoryReputationStore",
    "SQLiteReputationStore",
    "ConcurrencyError",
    "InMemoryStore",
    "SQLiteStore",
    "sign_contract_ack",
    "terms_hash_from_exchange",
    "verify_contract_ack",
    "build_agent_manifest",
    "verify_agent_manifest",
]
