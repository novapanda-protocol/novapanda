"""多链钱包抽象层（AgentWalletManager）— 不进 CORE 状态机。"""

from .fiat_licensed import LicensedFiatComplianceGateway, make_fiat_compliance_gateway
from .manager import (
    DefaultAgentWalletManager,
    InMemoryChainAdapter,
    InMemorySmartAccount,
    StubFiatComplianceGateway,
    UsdcPaymaster,
    WalletError,
)
from .paymaster_4337 import EntryPointPaymaster4337, UserOperation, encode_transfer_call
from .protocols import (
    AgentWalletManager,
    ChainAdapter,
    FiatComplianceGateway,
    Paymaster,
    SmartAccount,
)
from .rpc_evm import EntryPointRpcPaymaster, EvmRpcChainAdapter, JsonRpcClient
from .rpc_solana import SolanaJsonRpcClient, SolanaRpcChainAdapter
from .settlement_bridge import WalletBackedSettlement
from .solana_fee_payer import SolanaFeePayer
from .types import (
    AssetRef,
    Balance,
    ChainFamily,
    ChainRef,
    FiatPaymentRequest,
    FiatSettlementRequest,
    FiatStubReceipt,
    GasQuote,
    TransferRequest,
    TxReceipt,
)

__all__ = [
    "AgentWalletManager",
    "AssetRef",
    "Balance",
    "ChainAdapter",
    "ChainFamily",
    "ChainRef",
    "DefaultAgentWalletManager",
    "EntryPointPaymaster4337",
    "EntryPointRpcPaymaster",
    "EvmRpcChainAdapter",
    "FiatComplianceGateway",
    "FiatPaymentRequest",
    "FiatSettlementRequest",
    "FiatStubReceipt",
    "GasQuote",
    "InMemoryChainAdapter",
    "InMemorySmartAccount",
    "JsonRpcClient",
    "LicensedFiatComplianceGateway",
    "Paymaster",
    "SmartAccount",
    "SolanaFeePayer",
    "SolanaJsonRpcClient",
    "SolanaRpcChainAdapter",
    "StubFiatComplianceGateway",
    "TransferRequest",
    "TxReceipt",
    "UsdcPaymaster",
    "UserOperation",
    "WalletBackedSettlement",
    "WalletError",
    "encode_transfer_call",
    "make_fiat_compliance_gateway",
]
