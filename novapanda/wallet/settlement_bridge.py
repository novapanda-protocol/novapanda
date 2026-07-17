"""SettlementAdapter ↔ AgentWalletManager 旁路桥（P2 · 仍不进 CORE SM）。

语义：escrow = 从 client 账户锁定到 escrow 金库；settle = 放给 provider；
refund = 退回 client。默认使用内存 ChainAdapter，生产可换真链适配器。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from novapanda.settlement import SettlementAdapter, SettlementError

from .manager import DefaultAgentWalletManager, InMemoryChainAdapter, WalletError
from .types import AssetRef, ChainRef, TransferRequest


@dataclass
class WalletBackedSettlement(SettlementAdapter):
    """可选结算轨：资金动作委托给统一钱包抽象。"""

    rail: str = "wallet-evm-memory"
    chain: ChainRef = field(default_factory=lambda: ChainRef.evm(31337))
    manager: Optional[DefaultAgentWalletManager] = None
    asset_symbol: str = "USD"
    asset_decimals: int = 2
    _holds: dict[str, dict] = field(default_factory=dict)
    _adapter: Optional[InMemoryChainAdapter] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.manager is None:
            self.manager = DefaultAgentWalletManager()
        if self._adapter is None:
            self._adapter = InMemoryChainAdapter(
                chain=self.chain, native_symbol=self.asset_symbol
            )
            self.manager.register_adapter(self._adapter)

    def _asset(self) -> AssetRef:
        return AssetRef(
            chain=self.chain,
            symbol=self.asset_symbol,
            decimals=self.asset_decimals,
        )

    def _escrow_address(self, handle: str) -> str:
        return f"escrow:{handle}"

    def seed_client(self, client_agent_id: str, amount: int) -> None:
        """测试/沙箱：给 client 注资。"""
        assert self.manager is not None and self._adapter is not None
        acct = self.manager.ensure_account(client_agent_id, self.chain)
        self._adapter.credit(acct.address, self._asset(), amount)

    def escrow(self, exchange_id: str, amount: int, currency: str) -> str:
        if amount < 0:
            raise SettlementError("escrow amount 不能为负")
        # exchange_id 仅作关联；client 身份由绑定表传入（见 bind_parties）
        meta = self._holds.get(f"pending:{exchange_id}")
        if meta is None:
            # 无 bind 时退化为协议 mock 语义：只记账不扣链上（兼容未 seed）
            handle = "wallet-escrow-" + uuid.uuid4().hex[:12]
            self._holds[handle] = {
                "exchange_id": exchange_id,
                "amount": amount,
                "currency": currency,
                "status": "held",
                "client": None,
                "provider": None,
                "ledger": False,
            }
            return handle

        client = meta["client"]
        provider = meta["provider"]
        handle = "wallet-escrow-" + uuid.uuid4().hex[:12]
        assert self.manager is not None
        client_acct = self.manager.ensure_account(client, self.chain)
        try:
            self.manager.ensure_account(provider, self.chain)
            rx = client_acct.transfer(
                TransferRequest(
                    asset=self._asset(),
                    to_address=self._escrow_address(handle),
                    amount=amount,
                    memo=f"escrow:{exchange_id}",
                )
            )
        except WalletError as exc:
            raise SettlementError(str(exc)) from exc
        self._holds[handle] = {
            "exchange_id": exchange_id,
            "amount": amount,
            "currency": currency,
            "status": "held",
            "client": client,
            "provider": provider,
            "ledger": True,
            "escrow_tx": rx.tx_hash,
        }
        del self._holds[f"pending:{exchange_id}"]
        return handle

    def bind_parties(self, exchange_id: str, *, client: str, provider: str) -> None:
        """在 escrow 前绑定当事人，以便从 client SmartAccount 扣款。"""
        self._holds[f"pending:{exchange_id}"] = {
            "client": client,
            "provider": provider,
        }

    def settle(self, handle: str) -> dict:
        return self._release(handle, to_provider=True)

    def refund(self, handle: str) -> dict:
        return self._release(handle, to_provider=False)

    def status(self, handle: str) -> str:
        return self._holds[handle]["status"]

    def _release(self, handle: str, *, to_provider: bool) -> dict:
        h = self._holds.get(handle)
        if h is None:
            raise SettlementError(f"未知 escrow handle: {handle}")
        target = "settled" if to_provider else "refunded"
        if h["status"] == target:
            return self._receipt(handle, h)
        if h["status"] != "held":
            raise SettlementError(f"escrow 状态冲突：{h['status']} -> {target}")

        if h.get("ledger") and h.get("client") and h.get("provider"):
            assert self.manager is not None and self._adapter is not None
            payee_id = h["provider"] if to_provider else h["client"]
            payee = self.manager.ensure_account(payee_id, self.chain)
            # 金库余额在 escrow 地址上：用 adapter 直接拨出
            escrow_addr = self._escrow_address(handle)
            bal = self._adapter.get_balance(escrow_addr, self._asset()).amount
            if bal < h["amount"]:
                raise SettlementError("escrow vault underfunded")
            try:
                self._adapter.transfer(
                    escrow_addr,
                    TransferRequest(
                        asset=self._asset(),
                        to_address=payee.address,
                        amount=h["amount"],
                        memo=target,
                    ),
                )
            except WalletError as exc:
                raise SettlementError(str(exc)) from exc

        h["status"] = target
        return self._receipt(handle, h)

    def _receipt(self, handle: str, h: dict) -> dict:
        return {
            "handle": handle,
            "status": h["status"],
            "amount": h["amount"],
            "currency": h["currency"],
            "rail": self.rail,
        }
