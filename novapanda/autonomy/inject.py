"""从环境变量组装真实链适配 + RealExchangeRunner（不改拍卖/定价算法）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.wallet.rpc_evm import EvmRpcChainAdapter, JsonRpcClient
from novapanda.wallet.rpc_resilience import with_resilient_estimate_gas
from novapanda.wallet.rpc_solana import SolanaJsonRpcClient, SolanaRpcChainAdapter
from novapanda.wallet.types import ChainRef, TransferRequest

from .orchestrator import InMemoryExchangeRunner, SupplyChainOrchestrator
from .real_runner import RealExchangeRunner


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def env_wants_real_rails() -> bool:
    """检测是否应按「真实/测试网」注入（非纯内存）。"""
    if _env("NOVAPANDA_FORCE_REAL_RUNNER") in ("1", "true", "yes"):
        return True
    if _env("NOVAPANDA_EVM_RPC_URL") or _env("NOVAPANDA_SOLANA_RPC_URL"):
        return True
    if _env("SIGNER_BROADCAST_KEY"):
        return True
    settle = _env("NOVAPANDA_SETTLEMENT", "mock").lower()
    if settle and settle not in ("mock",):
        return True
    return False


def make_signer_broadcast(key: str) -> Callable[..., str]:
    """身体层签名广播回调。

    - ``SIMULATED`` / ``test:*``：返回伪 raw tx，供 RPC 适配器联调
    - 其他：占位——生产须替换为真实钱包签名（不在此实现私钥算法细节）
    """
    key = (key or "").strip()

    def _broadcast(from_address: str, req: TransferRequest, *args: Any, **kwargs: Any) -> str:
        if key in ("", "SIMULATED") or key.startswith("test:"):
            # 确定性伪 raw，便于测试网模拟
            body = f"{from_address}|{req.to_address}|{req.amount}|{key}"
            import hashlib

            return "0x" + hashlib.sha256(body.encode()).hexdigest()
        raise RuntimeError(
            "SIGNER_BROADCAST_KEY set to a live secret; "
            "wire a real signing backend before broadcast "
            "(refusing to embed raw key handling in protocol package)"
        )

    return _broadcast


@dataclass
class ChainInjection:
    evm: Optional[EvmRpcChainAdapter] = None
    solana: Optional[SolanaRpcChainAdapter] = None
    signer_configured: bool = False


def build_chain_injection_from_env(*, http_evm=None, http_sol=None) -> ChainInjection:
    """组装带 signer_broadcast 与 Gas 韧性的链适配。"""
    out = ChainInjection()
    signer_key = _env("SIGNER_BROADCAST_KEY")
    broadcast = make_signer_broadcast(signer_key) if signer_key else None
    out.signer_configured = broadcast is not None

    evm_url = _env("NOVAPANDA_EVM_RPC_URL")
    if evm_url:
        chain_id = _env("NOVAPANDA_EVM_CHAIN_ID", "eip155:11155111")
        if chain_id.startswith("eip155:"):
            num = int(chain_id.split(":", 1)[1])
            cref = ChainRef.evm(num)
        else:
            cref = ChainRef.evm(11155111)
        rpc = JsonRpcClient(base_url=evm_url, http=http_evm)
        adapter = EvmRpcChainAdapter(
            chain=cref, rpc=rpc, signer_broadcast=broadcast
        )
        out.evm = with_resilient_estimate_gas(adapter)

    sol_url = _env("NOVAPANDA_SOLANA_RPC_URL")
    if sol_url:
        cluster = _env("NOVAPANDA_SOLANA_CLUSTER", "solana:devnet")
        network = cluster.split(":", 1)[1] if ":" in cluster else "devnet"
        cref = ChainRef.solana(network)
        rpc = SolanaJsonRpcClient(base_url=sol_url, http=http_sol)
        adapter = SolanaRpcChainAdapter(
            chain=cref, rpc=rpc, signer_broadcast=broadcast
        )
        out.solana = with_resilient_estimate_gas(
            adapter, fallback_gas=5_000
        )

    return out


def build_exchange_runner(
    *,
    engine: Optional[ExchangeEngine] = None,
    client: Optional[Identity] = None,
    providers: Optional[dict[str, Identity]] = None,
    force_memory: bool = False,
) -> Any:
    """按环境选择 InMemory 或 RealExchangeRunner。"""
    if force_memory or not env_wants_real_rails() or engine is None or client is None:
        return InMemoryExchangeRunner()
    return RealExchangeRunner(
        engine=engine,
        client=client,
        providers=dict(providers or {}),
        auto_complete=bool(providers),
    )


def build_orchestrator_from_env(
    *,
    auctioneer,
    engine: Optional[ExchangeEngine] = None,
    client: Optional[Identity] = None,
    providers: Optional[dict[str, Identity]] = None,
    force_memory: bool = False,
) -> tuple[SupplyChainOrchestrator, ChainInjection]:
    """工厂：Orchestrator + 链注入上下文。"""
    chains = build_chain_injection_from_env()
    runner = build_exchange_runner(
        engine=engine,
        client=client,
        providers=providers,
        force_memory=force_memory,
    )

    def _on_started(info: dict) -> None:
        # 预留：真实链旁路记账；估气探测防死锁
        if chains.evm is not None and info.get("exchange_id"):
            try:
                from novapanda.wallet.types import AssetRef, TransferRequest

                eth = AssetRef(chain=chains.evm.chain, symbol="ETH", decimals=18)
                # dry estimate only
                chains.evm.estimate_gas(
                    "0x" + "00" * 20,
                    TransferRequest(asset=eth, to_address="0x" + "11" * 20, amount=0),
                )
            except Exception:
                pass

    if isinstance(runner, RealExchangeRunner) and runner.on_leg_started is None:
        runner.on_leg_started = _on_started

    orch = SupplyChainOrchestrator(auctioneer=auctioneer, runner=runner)
    return orch, chains
