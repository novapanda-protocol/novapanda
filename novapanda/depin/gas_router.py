"""极端环境 Gas：激进 bump + 多链备用路由（EVM → Solana）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from novapanda.wallet.manager import WalletError
from novapanda.wallet.types import AssetRef, ChainRef, GasQuote, TxReceipt


@dataclass
class CongestionSignal:
    """链拥堵信号（由 RPC / mempool 探针写入）。"""

    chain_id: str
    congested: bool = False
    base_fee_gwei: float = 0.0
    # 建议 bump 倍数（1.0 = 不提价）
    suggested_bump: float = 1.0


def bump_gas(gas_native: int, *, bump: float, cap_mult: float = 4.0) -> int:
    """激进提价：gas * bump，上限 cap_mult×。"""
    b = max(1.0, float(bump))
    b = min(b, float(cap_mult))
    return max(1, int(round(gas_native * b)))


@dataclass
class MultiRailGasRouter:
    """Paymaster 多轨兜底：主轨（EVM）拥堵/失败 → 备用轨（Solana）。

    不改 CORE；仅身体层赞助路径。
    """

    primary_paymaster: Any  # quote/sponsor
    primary_chain: ChainRef
    primary_fee_token: AssetRef
    fallback_paymaster: Optional[Any] = None
    fallback_chain: Optional[ChainRef] = None
    fallback_fee_token: Optional[AssetRef] = None
    congestion: CongestionSignal = field(
        default_factory=lambda: CongestionSignal(chain_id="eip155:1")
    )
    bump_on_congestion: float = 2.5
    max_bumps: int = 3
    _attempts: list[dict[str, Any]] = field(default_factory=list)

    def mark_congested(self, *, base_fee_gwei: float = 80.0, bump: float = 2.5) -> None:
        self.congestion = CongestionSignal(
            chain_id=self.primary_chain.chain_id,
            congested=True,
            base_fee_gwei=base_fee_gwei,
            suggested_bump=bump,
        )

    def clear_congestion(self) -> None:
        self.congestion = CongestionSignal(
            chain_id=self.primary_chain.chain_id, congested=False
        )

    def sponsor_resilient(
        self,
        *,
        payer_address: str,
        gas_native: int,
        user_op_ref: str,
        force_fail_primary: bool = False,
    ) -> TxReceipt:
        """主轨 bump 重试；仍失败则切 Solana（或其他 fallback）轨。"""
        self._attempts.clear()
        gas = int(gas_native)
        bump = self.congestion.suggested_bump if self.congestion.congested else 1.0

        last_exc: Optional[BaseException] = None
        for i in range(max(1, self.max_bumps)):
            gas_i = bump_gas(gas, bump=bump * (1.0 + 0.25 * i)) if bump > 1.0 or i else gas
            if self.congestion.congested:
                gas_i = bump_gas(gas, bump=self.bump_on_congestion * (1.0 + 0.5 * i))
            try:
                if force_fail_primary:
                    raise WalletError(
                        "rpc congestion: replacement transaction underpriced",
                        code="RPC_CONGESTION",
                        recovery="retry_adjust",
                        retryable=True,
                    )
                rx = self.primary_paymaster.sponsor(
                    chain=self.primary_chain,
                    payer_address=payer_address,
                    fee_token=self.primary_fee_token,
                    gas_native=gas_i,
                    user_op_ref=f"{user_op_ref}:bump{i}",
                )
                self._attempts.append(
                    {
                        "rail": "primary",
                        "chain_id": self.primary_chain.chain_id,
                        "gas": gas_i,
                        "ok": True,
                    }
                )
                return TxReceipt(
                    chain_id=rx.chain_id,
                    tx_hash=rx.tx_hash,
                    status=rx.status,
                    raw={
                        **(rx.raw or {}),
                        "rail": "primary",
                        "gas_used_estimate": gas_i,
                        "bumps": i,
                        "attempts": list(self._attempts),
                    },
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self._attempts.append(
                    {
                        "rail": "primary",
                        "chain_id": self.primary_chain.chain_id,
                        "gas": gas_i,
                        "ok": False,
                        "error": str(exc)[:120],
                    }
                )

        # —— 备用轨 ——
        if (
            self.fallback_paymaster is None
            or self.fallback_chain is None
            or self.fallback_fee_token is None
        ):
            raise WalletError(
                f"primary rail exhausted; no fallback ({last_exc})",
                code="GAS_RAIL_EXHAUSTED",
                recovery="escalate_human",
                retryable=False,
                hint="Configure Solana fallback paymaster or wait for congestion to clear.",
            ) from last_exc

        rx2 = self.fallback_paymaster.sponsor(
            chain=self.fallback_chain,
            payer_address=payer_address,
            fee_token=self.fallback_fee_token,
            gas_native=max(5_000, gas // 4),
            user_op_ref=f"{user_op_ref}:fallback",
        )
        self._attempts.append(
            {
                "rail": "fallback",
                "chain_id": self.fallback_chain.chain_id,
                "ok": True,
            }
        )
        return TxReceipt(
            chain_id=rx2.chain_id,
            tx_hash=rx2.tx_hash,
            status=rx2.status,
            raw={
                **(rx2.raw or {}),
                "rail": "fallback",
                "switched_from": self.primary_chain.chain_id,
                "attempts": list(self._attempts),
            },
        )


def enhance_entrypoint_paymaster(paymaster: Any, *, default_bump: float = 2.0) -> Any:
    """就地增强 EntryPointRpcPaymaster / 4337：sponsor 支持 gas_bump 关键字。"""
    raw_sponsor = paymaster.sponsor

    def sponsor(*, gas_bump: float = 1.0, gas_native: int, **kwargs: Any) -> TxReceipt:
        bumped = bump_gas(gas_native, bump=gas_bump or default_bump if gas_bump else 1.0)
        # 若显式 gas_bump==1 且无拥堵，保持原值
        if gas_bump <= 1.0:
            bumped = gas_native
        return raw_sponsor(gas_native=bumped, **kwargs)

    paymaster.sponsor = sponsor  # type: ignore[method-assign]
    paymaster.bump_gas = staticmethod(bump_gas)  # type: ignore[attr-defined]
    return paymaster
