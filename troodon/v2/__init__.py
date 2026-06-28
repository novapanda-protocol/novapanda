"""Troodon v2 占位模块（见证网络 + 质押罚没）。

v0 参考实现仅提供 schema 校验与 API 占位；运行时默认关闭（`WITNESS_V2_ENABLED=False`）。
"""

from .witness import (
    WITNESS_V2_ENABLED,
    WitnessV2NotEnabledError,
    build_stake_lock,
    build_witness_attestation,
    validate_stake_lock,
    validate_witness_attestation,
)
from .federation import (
    FEDERATION_V2_ENABLED,
    FederationV2NotEnabledError,
    build_reputation_bundle,
    import_reputation_bundle,
    validate_reputation_bundle,
    verify_reputation_chain,
)

__all__ = [
    "WITNESS_V2_ENABLED",
    "WitnessV2NotEnabledError",
    "build_stake_lock",
    "build_witness_attestation",
    "validate_stake_lock",
    "validate_witness_attestation",
    "FEDERATION_V2_ENABLED",
    "FederationV2NotEnabledError",
    "build_reputation_bundle",
    "import_reputation_bundle",
    "validate_reputation_bundle",
    "verify_reputation_chain",
]
