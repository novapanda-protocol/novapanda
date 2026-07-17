"""内存链适配 + Paymaster + 法币合规存根 + AgentWalletManager。"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .protocols import (
    AgentWalletManager,
    ChainAdapter,
    FiatComplianceGateway,
    Paymaster,
    SmartAccount,
)
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


class WalletError(Exception):
    """Wallet/rail failure. Optional ``code`` / ``recovery`` / ``retryable`` for Agent Skill.

    Prefer raising with structured fields so LLM tool results stay actionable:
    e.g. ``WalletError("insufficient balance", code="INSUFFICIENT_BALANCE",
    recovery="retry_adjust", retryable=True)``.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "WALLET_ERROR",
        recovery: str = "escalate_human",
        retryable: bool = False,
        hint: str = "",
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.recovery = recovery
        self.retryable = retryable
        self.hint = hint
        self.details = details or {}


# ----- 内存账本适配器 -----


@dataclass
class InMemoryChainAdapter:
    """单链内存账本：键 = (address, symbol|token)。生产替换为 RPC。"""

    chain: ChainRef
    native_symbol: str = "ETH"
    _balances: dict[tuple[str, str], int] = field(default_factory=dict)

    def _key(self, address: str, asset: AssetRef) -> tuple[str, str]:
        return (address, asset.token_address or asset.symbol)

    def credit(self, address: str, asset: AssetRef, amount: int) -> None:
        k = self._key(address, asset)
        self._balances[k] = self._balances.get(k, 0) + amount

    def get_balance(self, address: str, asset: AssetRef) -> Balance:
        if asset.chain.chain_id != self.chain.chain_id:
            raise WalletError("asset chain mismatch")
        amt = self._balances.get(self._key(address, asset), 0)
        return Balance(asset=asset, amount=amt)

    def transfer(self, from_address: str, req: TransferRequest) -> TxReceipt:
        if req.asset.chain.chain_id != self.chain.chain_id:
            raise WalletError("asset chain mismatch")
        bal = self.get_balance(from_address, req.asset).amount
        if bal < req.amount:
            raise WalletError(
                "insufficient balance",
                code="INSUFFICIENT_BALANCE",
                recovery="retry_adjust",
                retryable=True,
                hint="Fund the wallet or reduce transfer amount, then retry.",
            )
        self._balances[self._key(from_address, req.asset)] = bal - req.amount
        to_k = self._key(req.to_address, req.asset)
        self._balances[to_k] = self._balances.get(to_k, 0) + req.amount
        tx = "0x" + hashlib.sha256(f"{from_address}:{req.to_address}:{req.amount}:{uuid.uuid4().hex}".encode()).hexdigest()
        return TxReceipt(
            chain_id=self.chain.chain_id,
            tx_hash=tx,
            status="confirmed",
            raw={"family": self.chain.family.value},
        )

    def estimate_gas(self, from_address: str, req: TransferRequest) -> GasQuote:
        # 原型固定估气；Solana 用 lamports 量级不同但接口相同
        gas = 21_000 if self.chain.family == ChainFamily.EVM else 5_000
        return GasQuote(
            chain_id=self.chain.chain_id,
            native_gas_estimate=gas,
            native_symbol=self.native_symbol,
            paymaster_available=False,
        )


@dataclass
class UsdcPaymaster:
    """概念 Paymaster：按固定汇率用 USDC（或指定 fee_token）抵扣 Native Gas。

    生产应对接 ERC-4337 / 链上 Paymaster 合约；此处只演示资产扣减语义。
    """

    ledger: InMemoryChainAdapter
    # 1 unit native gas → N 最小单位 fee_token（简化线性模型）
    token_per_gas_unit: int = 2

    def quote(
        self,
        *,
        chain: ChainRef,
        payer_address: str,
        gas_native: int,
        fee_token: AssetRef,
    ) -> GasQuote:
        if chain.chain_id != self.ledger.chain.chain_id:
            raise WalletError("paymaster chain mismatch")
        fee_amt = gas_native * self.token_per_gas_unit
        return GasQuote(
            chain_id=chain.chain_id,
            native_gas_estimate=gas_native,
            native_symbol=self.ledger.native_symbol,
            token_fee=Balance(asset=fee_token, amount=fee_amt),
            paymaster_available=True,
        )

    def sponsor(
        self,
        *,
        chain: ChainRef,
        payer_address: str,
        fee_token: AssetRef,
        gas_native: int,
        user_op_ref: str,
    ) -> TxReceipt:
        q = self.quote(
            chain=chain,
            payer_address=payer_address,
            gas_native=gas_native,
            fee_token=fee_token,
        )
        assert q.token_fee is not None
        bal = self.ledger.get_balance(payer_address, fee_token).amount
        if bal < q.token_fee.amount:
            raise WalletError(
                "insufficient fee token for paymaster",
                code="PAYMASTER_UNDERFUNDED",
                recovery="retry_adjust",
                retryable=True,
                hint="Top up fee token or switch paymaster, then retry.",
            )
        # 扣代币至 paymaster 金库地址（原型）
        treasury = "paymaster:treasury"
        self.ledger.transfer(
            payer_address,
            TransferRequest(
                asset=fee_token,
                to_address=treasury,
                amount=q.token_fee.amount,
                memo=f"gas-sponsor:{user_op_ref}",
            ),
        )
        return TxReceipt(
            chain_id=chain.chain_id,
            tx_hash="pm-" + uuid.uuid4().hex[:16],
            status="confirmed",
            raw={
                "sponsored_gas": gas_native,
                "fee_token": fee_token.symbol,
                "fee_amount": q.token_fee.amount,
                "user_op_ref": user_op_ref,
            },
        )


@dataclass
class StubFiatComplianceGateway:
    """法币合规存根：接受请求形状，永不宣称持牌到账。

    后续替换为 Circle/Stripe 持牌伙伴实现；业务层应检查 ``licensed``。
    """

    partner: str = "stub-compliance"

    def pay_with_fiat(self, req: FiatPaymentRequest) -> FiatStubReceipt:
        return FiatStubReceipt(
            operation="pay_with_fiat",
            status="stub_accepted",
            licensed=False,
            partner=self.partner,
            detail=(
                f"stub: would buy {req.target_asset.symbol} on {req.target_asset.chain.chain_id} "
                f"for {req.amount_minor} {req.currency} minor units; not settled"
            ),
            ref="fiat-pay-" + req.idempotency_key,
        )

    def settle_to_fiat(self, req: FiatSettlementRequest) -> FiatStubReceipt:
        return FiatStubReceipt(
            operation="settle_to_fiat",
            status="stub_accepted",
            licensed=False,
            partner=self.partner,
            detail=(
                f"stub: would off-ramp {req.amount} {req.asset.symbol} to bank_ref={req.bank_ref}; "
                "not settled"
            ),
            ref="fiat-settle-" + req.idempotency_key,
        )


@dataclass
class InMemorySmartAccount:
    agent_id: str
    address: str
    chain: ChainRef
    adapter: ChainAdapter

    def balance(self, asset: AssetRef) -> Balance:
        return self.adapter.get_balance(self.address, asset)

    def transfer(self, req: TransferRequest) -> TxReceipt:
        return self.adapter.transfer(self.address, req)

    def transfer_with_paymaster(
        self,
        req: TransferRequest,
        *,
        fee_token: AssetRef,
        paymaster: Paymaster,
    ) -> TxReceipt:
        gas = self.adapter.estimate_gas(self.address, req)
        sponsor_rx = paymaster.sponsor(
            chain=self.chain,
            payer_address=self.address,
            fee_token=fee_token,
            gas_native=gas.native_gas_estimate,
            user_op_ref=uuid.uuid4().hex[:12],
        )
        tx = self.transfer(req)
        return TxReceipt(
            chain_id=tx.chain_id,
            tx_hash=tx.tx_hash,
            status=tx.status,
            raw={**tx.raw, "paymaster": sponsor_rx.raw, "paymaster_tx": sponsor_rx.tx_hash},
        )


@dataclass
class DefaultAgentWalletManager:
    """多链账户管理器：每 (agent_id, chain_id) 一个 SmartAccount。"""

    adapters: dict[str, ChainAdapter] = field(default_factory=dict)
    fiat_gateway: FiatComplianceGateway = field(default_factory=StubFiatComplianceGateway)
    _accounts: dict[tuple[str, str], InMemorySmartAccount] = field(default_factory=dict)

    def register_adapter(self, adapter: ChainAdapter) -> None:
        self.adapters[adapter.chain.chain_id] = adapter

    def ensure_account(self, agent_id: str, chain: ChainRef) -> SmartAccount:
        key = (agent_id, chain.chain_id)
        existing = self._accounts.get(key)
        if existing is not None:
            return existing
        adapter = self.adapters.get(chain.chain_id)
        if adapter is None:
            raise WalletError(f"no adapter for chain {chain.chain_id}")
        # 确定性派生演示地址（非密码学校验；生产用 AA factory / PDA）
        digest = hashlib.sha256(f"{agent_id}:{chain.chain_id}".encode()).hexdigest()
        if chain.family == ChainFamily.EVM:
            address = "0x" + digest[:40]
        else:
            address = "sol" + digest[:40]
        acct = InMemorySmartAccount(
            agent_id=agent_id, address=address, chain=chain, adapter=adapter
        )
        self._accounts[key] = acct
        return acct

    def get_account(self, agent_id: str, chain: ChainRef) -> Optional[SmartAccount]:
        return self._accounts.get((agent_id, chain.chain_id))

    def fiat(self) -> FiatComplianceGateway:
        return self.fiat_gateway


def _check_manager(m: DefaultAgentWalletManager) -> AgentWalletManager:
    return m
