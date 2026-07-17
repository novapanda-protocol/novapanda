"""DePIN / 具身智能物理协同旁路（不改 state_machine.TRANSITIONS）。

- 硬件 PoD（TPM 模拟签名）
- 离线凭证队列 + 复网幂等 Sink
- Gas bump + 多链结算兜底路由
"""

from .gas_router import CongestionSignal, MultiRailGasRouter, bump_gas
from .offline_sync import OfflineCredentialQueue, OfflineSignedCredential
from .physical_bid import PhysicalListingBidProvider
from .pod_tpm import HardwarePodBackend, simulate_tpm_sign, verify_tpm_pod

__all__ = [
    "CongestionSignal",
    "HardwarePodBackend",
    "MultiRailGasRouter",
    "OfflineCredentialQueue",
    "OfflineSignedCredential",
    "PhysicalListingBidProvider",
    "bump_gas",
    "simulate_tpm_sign",
    "verify_tpm_pod",
]
