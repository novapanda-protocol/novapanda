"""Solana JSON-RPC 适配（getBalance / getLatestBlockhash 探测）。

转账默认镜像本地账本；注入 ``signer_broadcast`` 后可 ``sendTransaction``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .manager import InMemoryChainAdapter, WalletError
from .types import AssetRef, Balance, ChainFamily, ChainRef, GasQuote, TransferRequest, TxReceipt


@dataclass
class SolanaJsonRpcClient:
    base_url: str
    http: Optional[httpx.Client] = None
    _owns_http: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.http is None:
            self.http = httpx.Client(base_url=self.base_url.rstrip("/"), timeout=30.0)
            self._owns_http = True

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        assert self.http is not None
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        url = self.base_url.rstrip("/") + "/"
        r = self.http.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise WalletError(f"solana rpc error: {data['error']}")
        return data.get("result")

    def close(self) -> None:
        if self._owns_http and self.http is not None:
            self.http.close()


@dataclass
class SolanaRpcChainAdapter:
    chain: ChainRef
    rpc: SolanaJsonRpcClient
    native_symbol: str = "SOL"
    mirror: Optional[InMemoryChainAdapter] = None
    signer_broadcast: Any = None

    def __post_init__(self) -> None:
        if self.chain.family != ChainFamily.SOLANA:
            raise WalletError("SolanaRpcChainAdapter requires solana family")
        if self.mirror is None:
            self.mirror = InMemoryChainAdapter(chain=self.chain, native_symbol=self.native_symbol)

    def get_balance(self, address: str, asset: AssetRef) -> Balance:
        if not asset.is_native:
            raise WalletError("prototype Solana adapter: native SOL only")
        result = self.rpc.call("getBalance", [address])
        # {"context":..., "value": lamports}
        if isinstance(result, dict):
            amt = int(result.get("value") or 0)
        else:
            amt = int(result or 0)
        return Balance(asset=asset, amount=amt)

    def transfer(self, from_address: str, req: TransferRequest) -> TxReceipt:
        # 探测 blockhash（证明 RPC）
        try:
            bh = self.rpc.call("getLatestBlockhash", [{"commitment": "processed"}])
            blockhash = (bh or {}).get("value", {}).get("blockhash") if isinstance(bh, dict) else None
        except Exception:  # noqa: BLE001
            blockhash = None

        if self.signer_broadcast is not None:
            raw = self.signer_broadcast(from_address, req, blockhash)
            sig = self.rpc.call("sendTransaction", [raw, {"encoding": "base64"}])
            return TxReceipt(
                chain_id=self.chain.chain_id,
                tx_hash=str(sig),
                status="submitted",
                raw={"mode": "solana-rpc", "blockhash": blockhash},
            )

        assert self.mirror is not None
        rx = self.mirror.transfer(from_address, req)
        return TxReceipt(
            chain_id=self.chain.chain_id,
            tx_hash=rx.tx_hash,
            status="simulated",
            raw={
                "mode": "solana-rpc-simulate",
                "blockhash": blockhash,
                "note": "set signer_broadcast to sendTransaction",
            },
        )

    def estimate_gas(self, from_address: str, req: TransferRequest) -> GasQuote:
        return GasQuote(
            chain_id=self.chain.chain_id,
            native_gas_estimate=5_000,
            native_symbol=self.native_symbol,
            paymaster_available=False,
        )

    def credit(self, address: str, asset: AssetRef, amount: int) -> None:
        assert self.mirror is not None
        self.mirror.credit(address, asset, amount)
