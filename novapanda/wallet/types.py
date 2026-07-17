"""多链钱包抽象 — 数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ChainFamily(str, Enum):
    EVM = "evm"
    SOLANA = "solana"


@dataclass(frozen=True)
class ChainRef:
    """CAIP-2 风格链标识，例如 ``eip155:1`` / ``solana:mainnet``。"""

    chain_id: str
    family: ChainFamily

    @staticmethod
    def evm(numeric_id: int) -> "ChainRef":
        return ChainRef(chain_id=f"eip155:{numeric_id}", family=ChainFamily.EVM)

    @staticmethod
    def solana(network: str = "mainnet") -> "ChainRef":
        return ChainRef(chain_id=f"solana:{network}", family=ChainFamily.SOLANA)


@dataclass(frozen=True)
class AssetRef:
    """资产引用：Native 时 ``token_address=None``。"""

    chain: ChainRef
    symbol: str
    decimals: int = 18
    token_address: Optional[str] = None  # EVM 合约 / SPL mint

    @property
    def is_native(self) -> bool:
        return self.token_address is None


@dataclass(frozen=True)
class Balance:
    asset: AssetRef
    amount: int  # 最小单位整数


@dataclass(frozen=True)
class TransferRequest:
    asset: AssetRef
    to_address: str
    amount: int
    memo: Optional[str] = None


@dataclass(frozen=True)
class TxReceipt:
    chain_id: str
    tx_hash: str
    status: str  # submitted | confirmed | failed | stub
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GasQuote:
    """Gas quote for Agents — integers only; no raw tx hex.

    ``degraded=True`` means estimate used a resilience fallback (RPC timeout/error);
    Agents may retry later or proceed cautiously with the fallback gas.
    """

    chain_id: str
    native_gas_estimate: int
    native_symbol: str
    token_fee: Optional[Balance] = None  # Paymaster 折算后的代币费用
    paymaster_available: bool = False
    degraded: bool = False


@dataclass(frozen=True)
class FiatPaymentRequest:
    """法币入金（Agent 用卡/银行买链上资产）— 合规网关输入。"""

    amount_minor: int  # 分
    currency: str  # USD
    target_asset: AssetRef
    agent_id: str
    idempotency_key: str


@dataclass(frozen=True)
class FiatSettlementRequest:
    """法币出金（链上资产兑法币到银行）— 合规网关输入。"""

    amount: int  # 链上最小单位
    asset: AssetRef
    agent_id: str
    bank_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class FiatStubReceipt:
    """合规存根回执：标明未持牌、不可当真到账。"""

    operation: str  # pay_with_fiat | settle_to_fiat
    status: str  # stub_accepted | stub_rejected
    licensed: bool
    partner: str
    detail: str
    ref: str
