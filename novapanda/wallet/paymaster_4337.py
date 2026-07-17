"""ERC-4337 形态 Paymaster 适配器（EntryPoint v0.6 语义子集）。

不连真实 EntryPoint；校验 UserOperation 形状并用链上账本扣 fee_token，
为后续替换为 RPC Paymaster 留同一 ``Paymaster`` 接口。
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from .manager import InMemoryChainAdapter, WalletError
from .types import AssetRef, Balance, ChainRef, GasQuote, TransferRequest, TxReceipt


@dataclass(frozen=True)
class UserOperation:
    """ERC-4337 UserOperation 精简字段（生产可扩 calldata）。"""

    sender: str
    nonce: int
    call_data: bytes
    call_gas_limit: int
    verification_gas_limit: int
    pre_verification_gas: int
    max_fee_per_gas: int
    max_priority_fee_per_gas: int
    paymaster_and_data: bytes = b""
    signature: bytes = b""

    def total_gas(self) -> int:
        return (
            self.call_gas_limit
            + self.verification_gas_limit
            + self.pre_verification_gas
        )

    def op_hash(self) -> str:
        raw = (
            f"{self.sender}|{self.nonce}|{self.call_data.hex()}|"
            f"{self.total_gas()}|{self.max_fee_per_gas}"
        )
        return "0x" + hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class EntryPointPaymaster4337:
    """4337 Paymaster：验证 UserOp → 用 fee_token 代付 gas。

    ``paymaster_and_data`` 布局（原型）：``paymaster_addr(20) || token_addr_hint ||``
    实际扣费以 ``fee_token`` 参数为准。
    """

    ledger: InMemoryChainAdapter
    paymaster_address: str = "0xpaymaster4337"
    token_per_gas_unit: int = 2
    entry_point: str = "0xEntryPoint000000000000000000000000000000"

    def quote(
        self,
        *,
        chain: ChainRef,
        payer_address: str,
        gas_native: int,
        fee_token: AssetRef,
    ) -> GasQuote:
        self._assert_chain(chain)
        fee_amt = max(0, gas_native) * self.token_per_gas_unit
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
        user_op: Optional[UserOperation] = None,
    ) -> TxReceipt:
        self._assert_chain(chain)
        if user_op is not None:
            if user_op.sender.lower() != payer_address.lower() and user_op.sender != payer_address:
                # 允许 checksum 差异：宽松比对
                if user_op.sender != payer_address:
                    raise WalletError("UserOperation.sender mismatch")
            gas_native = max(gas_native, user_op.total_gas())
            user_op_ref = user_op.op_hash()

        q = self.quote(
            chain=chain,
            payer_address=payer_address,
            gas_native=gas_native,
            fee_token=fee_token,
        )
        assert q.token_fee is not None
        bal = self.ledger.get_balance(payer_address, fee_token).amount
        if bal < q.token_fee.amount:
            raise WalletError("insufficient fee token for 4337 paymaster")

        rx = self.ledger.transfer(
            payer_address,
            TransferRequest(
                asset=fee_token,
                to_address=self.paymaster_address,
                amount=q.token_fee.amount,
                memo=f"4337-sponsor:{user_op_ref}",
            ),
        )
        return TxReceipt(
            chain_id=chain.chain_id,
            tx_hash=rx.tx_hash,
            status="confirmed",
            raw={
                "standard": "erc-4337",
                "entry_point": self.entry_point,
                "paymaster": self.paymaster_address,
                "sponsored_gas": gas_native,
                "fee_token": fee_token.symbol,
                "fee_amount": q.token_fee.amount,
                "user_op_ref": user_op_ref,
                "user_op_hash": user_op.op_hash() if user_op else None,
            },
        )

    def build_paymaster_and_data(self, fee_token: AssetRef) -> bytes:
        token = (fee_token.token_address or fee_token.symbol).encode()[:32]
        return self.paymaster_address.encode()[:20] + token

    def _assert_chain(self, chain: ChainRef) -> None:
        if chain.chain_id != self.ledger.chain.chain_id:
            raise WalletError("4337 paymaster chain mismatch")


def encode_transfer_call(to: str, amount: int) -> bytes:
    """原型 calldata：非 ABI，仅供 UserOperation 测试。"""
    return f"transfer|{to}|{amount}".encode()
