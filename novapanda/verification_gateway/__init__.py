"""链下验证网关（Verification Gateway）原型。

职责：接收 Provider 提交的 Proof/Output → 无偏见验收 → 签发密码学凭证 →
驱动交换进入 VERIFIED，并由结算轨（mock / EVM / …）完成 settle。

设计对齐：
- CORE 状态机仍是权威生命周期（见 ``novapanda.state_machine``）
- 结算为适配器（ADR-0002），本包不托管资金
- 网关私钥只签 *验收凭证*，不替代双方 VDC 双签
"""

from .backends import (
    DockerSandboxBackend,
    LocalSchemaBackend,
    TEEAttestedBackend,
    VerificationBackend,
)
from .credential import VerificationCredential, build_and_sign_credential
from .gateway import ProofSubmission, VerificationGateway, VerifyOutcome
from .orchestrator import AutoSettleOrchestrator, LifecyclePhase

# DePIN PoD 后端从 depin 包再导出，避免循环时可用懒导入
try:
    from novapanda.depin.pod_tpm import HardwarePodBackend
except Exception:  # pragma: no cover
    HardwarePodBackend = None  # type: ignore[misc, assignment]

__all__ = [
    "AutoSettleOrchestrator",
    "DockerSandboxBackend",
    "HardwarePodBackend",
    "LifecyclePhase",
    "LocalSchemaBackend",
    "ProofSubmission",
    "TEEAttestedBackend",
    "VerificationBackend",
    "VerificationCredential",
    "VerificationGateway",
    "VerifyOutcome",
    "build_and_sign_credential",
]
