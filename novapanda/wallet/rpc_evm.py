"""EVM JSON-RPC 链适配 + EntryPoint 模拟（可注入 httpx Client）。

无真实节点时测试用 FakeTransport；生产设 ``NOVAPANDA_EVM_RPC_URL``。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .manager import InMemoryChainAdapter, WalletError
from .paymaster_4337 import EntryPointPaymaster4337, UserOperation
from .types import AssetRef, Balance, ChainFamily, ChainRef, GasQuote, TransferRequest, TxReceipt


@dataclass
class JsonRpcClient:
    """最小 JSON-RPC 2.0 客户端。"""

    base_url: str
    http: Optional[httpx.Client] = None
    _owns_http: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.http is None:
            self.http = httpx.Client(base_url=self.base_url.rstrip("/"), timeout=30.0)
            self._owns_http = True

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        assert self.http is not None
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        # 用绝对 URL，避免 MockTransport 下 post("") 变成 "/"
        url = self.base_url.rstrip("/") + "/"
        r = self.http.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data and data["error"]:
            raise WalletError(f"rpc error: {data['error']}")
        return data.get("result")

    def close(self) -> None:
        if self._owns_http and self.http is not None:
            self.http.close()


@dataclass
class EvmRpcChainAdapter:
    """EVM RPC 适配：余额读链；转账默认仍走本地仿真（无私钥广播职责）。

    设计：节点持钥广播属身体层；协议适配器只提供估气/读余额/模拟。
    若提供 ``signer_broadcast`` 回调，则可提交 raw tx。
    """

    chain: ChainRef
    rpc: JsonRpcClient
    native_symbol: str = "ETH"
    # 可选：本地镜像用于无 RPC 时的单测 / 离线
    mirror: Optional[InMemoryChainAdapter] = None
    signer_broadcast: Any = None  # (raw_tx_hex) -> tx_hash

    def __post_init__(self) -> None:
        if self.chain.family != ChainFamily.EVM:
            raise WalletError("EvmRpcChainAdapter requires EVM chain")
        if self.mirror is None:
            self.mirror = InMemoryChainAdapter(chain=self.chain, native_symbol=self.native_symbol)

    def get_balance(self, address: str, asset: AssetRef) -> Balance:
        if asset.chain.chain_id != self.chain.chain_id:
            raise WalletError("asset chain mismatch")
        if asset.is_native:
            raw = self.rpc.call("eth_getBalance", [address, "latest"])
            amt = int(raw, 16) if isinstance(raw, str) else int(raw)
            return Balance(asset=asset, amount=amt)
        # ERC-20 balanceOf(address) selector 0x70a08231
        data = "0x70a08231" + address.lower().replace("0x", "").rjust(64, "0")
        raw = self.rpc.call(
            "eth_call",
            [{"to": asset.token_address, "data": data}, "latest"],
        )
        amt = int(raw, 16) if isinstance(raw, str) and raw.startswith("0x") else int(raw or 0)
        return Balance(asset=asset, amount=amt)

    def transfer(self, from_address: str, req: TransferRequest) -> TxReceipt:
        if self.signer_broadcast is None:
            # 无私钥广播：镜像本地账本（与内存轨一致），并附带 eth_estimateGas 证明 RPC 可达
            gas = self.estimate_gas(from_address, req)
            assert self.mirror is not None
            rx = self.mirror.transfer(from_address, req)
            return TxReceipt(
                chain_id=self.chain.chain_id,
                tx_hash=rx.tx_hash,
                status="simulated",
                raw={
                    "mode": "rpc-simulate",
                    "estimated_gas": gas.native_gas_estimate,
                    "note": "set signer_broadcast to submit raw tx",
                },
            )
        raw_tx = self.signer_broadcast(from_address, req)
        tx_hash = self.rpc.call("eth_sendRawTransaction", [raw_tx])
        return TxReceipt(
            chain_id=self.chain.chain_id,
            tx_hash=str(tx_hash),
            status="submitted",
            raw={"mode": "rpc-broadcast"},
        )

    def estimate_gas(self, from_address: str, req: TransferRequest) -> GasQuote:
        tx: dict[str, Any] = {"from": from_address, "to": req.to_address}
        if req.asset.is_native:
            tx["value"] = hex(req.amount)
        try:
            raw = self.rpc.call("eth_estimateGas", [tx])
            gas = int(raw, 16) if isinstance(raw, str) else int(raw)
        except Exception:  # noqa: BLE001
            gas = 21_000
        return GasQuote(
            chain_id=self.chain.chain_id,
            native_gas_estimate=gas,
            native_symbol=self.native_symbol,
            paymaster_available=False,
        )

    def credit(self, address: str, asset: AssetRef, amount: int) -> None:
        """仅镜像账本注资（测试 / 模拟广播前）。"""
        assert self.mirror is not None
        self.mirror.credit(address, asset, amount)


@dataclass
class EntryPointRpcPaymaster:
    """通过 eth_call 模拟 EntryPoint.handleOps；扣费委托本地 4337 Paymaster 账本。"""

    ledger: InMemoryChainAdapter
    rpc: JsonRpcClient
    entry_point: str = "0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789"
    inner: Optional[EntryPointPaymaster4337] = None

    def __post_init__(self) -> None:
        if self.inner is None:
            self.inner = EntryPointPaymaster4337(
                ledger=self.ledger, entry_point=self.entry_point
            )

    def quote(self, **kwargs):
        assert self.inner is not None
        return self.inner.quote(**kwargs)

    def sponsor(
        self,
        *,
        chain: ChainRef,
        payer_address: str,
        fee_token: AssetRef,
        gas_native: int,
        user_op_ref: str,
        user_op: Optional[UserOperation] = None,
        gas_bump: float = 1.0,
    ) -> TxReceipt:
        assert self.inner is not None
        # 激进提价（拥堵时由调用方传入 gas_bump>1）
        from novapanda.depin.gas_router import bump_gas

        effective_gas = (
            bump_gas(gas_native, bump=gas_bump) if gas_bump and gas_bump > 1.0 else gas_native
        )
        # 可选：对 EntryPoint 做 eth_call 探测（失败不阻断本地扣费，记 raw）
        probe: dict[str, Any] = {
            "entry_point": self.entry_point,
            "gas_bump": gas_bump,
            "effective_gas": effective_gas,
        }
        try:
            code = self.rpc.call("eth_getCode", [self.entry_point, "latest"])
            probe["entry_point_code_len"] = len(str(code or ""))
        except Exception as exc:  # noqa: BLE001
            probe["rpc_probe_error"] = str(exc)

        rx = self.inner.sponsor(
            chain=chain,
            payer_address=payer_address,
            fee_token=fee_token,
            gas_native=effective_gas,
            user_op_ref=user_op_ref,
            user_op=user_op,
        )
        return TxReceipt(
            chain_id=rx.chain_id,
            tx_hash=rx.tx_hash,
            status=rx.status,
            raw={**rx.raw, "rpc_probe": probe, "transport": "evm-json-rpc"},
        )
