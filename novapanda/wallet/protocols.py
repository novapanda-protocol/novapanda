"""多链钱包 — Protocol 契约。"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from .types import (
    AssetRef,
    Balance,
    ChainRef,
    FiatPaymentRequest,
    FiatSettlementRequest,
    FiatStubReceipt,
    GasQuote,
    TransferRequest,
    TxReceipt,
)


@runtime_checkable
class ChainAdapter(Protocol):
    """单链适配器：余额 / 转账 / 估 Gas。"""

    chain: ChainRef

    def get_balance(self, address: str, asset: AssetRef) -> Balance: ...

    def transfer(self, from_address: str, req: TransferRequest) -> TxReceipt: ...

    def estimate_gas(self, from_address: str, req: TransferRequest) -> GasQuote: ...


@runtime_checkable
class Paymaster(Protocol):
    """Gas 代付：用持有的主流代币抵扣 Native Gas。"""

    def quote(
        self,
        *,
        chain: ChainRef,
        payer_address: str,
        gas_native: int,
        fee_token: AssetRef,
    ) -> GasQuote: ...

    def sponsor(
        self,
        *,
        chain: ChainRef,
        payer_address: str,
        fee_token: AssetRef,
        gas_native: int,
        user_op_ref: str,
    ) -> TxReceipt: ...


@runtime_checkable
class FiatComplianceGateway(Protocol):
    """法币合规网关存根 — 为 Circle/Stripe 等预留边界。

    生产实现 MUST 声明 ``licensed`` 与牌照伙伴；存根永远 ``licensed=False``。
    """

    def pay_with_fiat(self, req: FiatPaymentRequest) -> FiatStubReceipt: ...

    def settle_to_fiat(self, req: FiatSettlementRequest) -> FiatStubReceipt: ...


@runtime_checkable
class SmartAccount(Protocol):
    """统一智能账户视图（业务层不区分 EVM/Solana 细节）。"""

    agent_id: str
    address: str
    chain: ChainRef

    def balance(self, asset: AssetRef) -> Balance: ...

    def transfer(self, req: TransferRequest) -> TxReceipt: ...

    def transfer_with_paymaster(
        self,
        req: TransferRequest,
        *,
        fee_token: AssetRef,
        paymaster: Paymaster,
    ) -> TxReceipt: ...


@runtime_checkable
class AgentWalletManager(Protocol):
    """按 Agent 管理多链 Smart Account。"""

    def ensure_account(self, agent_id: str, chain: ChainRef) -> SmartAccount: ...

    def get_account(self, agent_id: str, chain: ChainRef) -> Optional[SmartAccount]: ...

    def fiat(self) -> FiatComplianceGateway: ...
