"""Solana fee-payer 适配：由赞助账户支付交易费（lamports）。"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from .manager import InMemoryChainAdapter, WalletError
from .types import AssetRef, Balance, ChainFamily, ChainRef, GasQuote, TransferRequest, TxReceipt


@dataclass
class SolanaFeePayer:
    """Solana 形态：fee_payer 为另一账户代付 native SOL gas。

    实现 ``Paymaster`` 语义：``fee_token`` 必须是该链 native（SOL）。
    """

    ledger: InMemoryChainAdapter
    fee_payer_address: str
    lamports_per_sig: int = 5_000

    def __post_init__(self) -> None:
        if self.ledger.chain.family != ChainFamily.SOLANA:
            raise WalletError("SolanaFeePayer requires solana chain family")

    def quote(
        self,
        *,
        chain: ChainRef,
        payer_address: str,
        gas_native: int,
        fee_token: AssetRef,
    ) -> GasQuote:
        self._assert(chain, fee_token)
        fee = max(gas_native, self.lamports_per_sig)
        return GasQuote(
            chain_id=chain.chain_id,
            native_gas_estimate=fee,
            native_symbol="SOL",
            token_fee=Balance(asset=fee_token, amount=fee),
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
        """从 ``fee_payer_address`` 扣 SOL，而不是从 user。"""
        self._assert(chain, fee_token)
        q = self.quote(
            chain=chain,
            payer_address=payer_address,
            gas_native=gas_native,
            fee_token=fee_token,
        )
        assert q.token_fee is not None
        bal = self.ledger.get_balance(self.fee_payer_address, fee_token).amount
        if bal < q.token_fee.amount:
            raise WalletError("fee payer insufficient SOL")
        # 燃烧到系统 fee sink（原型）
        sink = "solana:fee-sink"
        rx = self.ledger.transfer(
            self.fee_payer_address,
            TransferRequest(
                asset=fee_token,
                to_address=sink,
                amount=q.token_fee.amount,
                memo=f"fee-payer:{payer_address}:{user_op_ref}",
            ),
        )
        return TxReceipt(
            chain_id=chain.chain_id,
            tx_hash="sol-" + hashlib.sha256(rx.tx_hash.encode()).hexdigest()[:32],
            status="confirmed",
            raw={
                "standard": "solana-fee-payer",
                "fee_payer": self.fee_payer_address,
                "user": payer_address,
                "lamports": q.token_fee.amount,
                "user_op_ref": user_op_ref or uuid.uuid4().hex[:12],
            },
        )

    def _assert(self, chain: ChainRef, fee_token: AssetRef) -> None:
        if chain.chain_id != self.ledger.chain.chain_id:
            raise WalletError("solana fee-payer chain mismatch")
        if not fee_token.is_native:
            raise WalletError("solana fee-payer expects native SOL fee_token")
