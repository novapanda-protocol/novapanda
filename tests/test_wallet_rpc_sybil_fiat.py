"""RPC 适配 · Stripe 持牌注入 · Sybil 时间窗衰减。"""

from __future__ import annotations

import json

import httpx

from novapanda.marketplace import InMemoryRiskSignalStore, SybilGraphDetector, SybilGraphPolicy
from novapanda.marketplace.types import ExchangeTerminalSnapshot
from novapanda.stripe_fake import create_stripe_fake_app
from novapanda.wallet import (
    AssetRef,
    ChainRef,
    EntryPointRpcPaymaster,
    EvmRpcChainAdapter,
    InMemoryChainAdapter,
    JsonRpcClient,
    SolanaJsonRpcClient,
    SolanaRpcChainAdapter,
    TransferRequest,
    make_fiat_compliance_gateway,
)
from novapanda.wallet.types import FiatPaymentRequest, FiatSettlementRequest


def _evm_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        method = body.get("method")
        if method == "eth_getBalance":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x64"})
        if method == "eth_estimateGas":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x5208"})
        if method == "eth_getCode":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x608060"})
        if method == "eth_call":
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": "0x" + "00" * 32}
            )
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": 1, "error": {"message": f"unknown {method}"}}
        )

    return httpx.MockTransport(handler)


def _sol_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        method = body.get("method")
        if method == "getBalance":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"context": {"slot": 1}, "value": 42}},
            )
        if method == "getLatestBlockhash":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"value": {"blockhash": "Hash111", "lastValidBlockHeight": 9}},
                },
            )
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": 1, "error": {"message": method}}
        )

    return httpx.MockTransport(handler)


def test_evm_rpc_adapter_balance_and_simulate_transfer():
    chain = ChainRef.evm(11155111)
    http = httpx.Client(transport=_evm_transport())
    rpc = JsonRpcClient(base_url="http://rpc.test", http=http)
    adapter = EvmRpcChainAdapter(chain=chain, rpc=rpc)
    eth = AssetRef(chain=chain, symbol="ETH", decimals=18)
    bal = adapter.get_balance("0xabc", eth)
    assert bal.amount == 0x64
    adapter.credit("0xfrom", eth, 1000)
    rx = adapter.transfer(
        "0xfrom",
        TransferRequest(asset=eth, to_address="0xto", amount=10),
    )
    assert rx.status == "simulated"
    assert rx.raw["estimated_gas"] == 0x5208


def test_entrypoint_rpc_paymaster_probes_code():
    chain = ChainRef.evm(1)
    ledger = InMemoryChainAdapter(chain=chain)
    http = httpx.Client(transport=_evm_transport())
    rpc = JsonRpcClient(base_url="http://rpc.test", http=http)
    pm = EntryPointRpcPaymaster(ledger=ledger, rpc=rpc)
    usdc = AssetRef(chain=chain, symbol="USDC", decimals=6, token_address="0xu")
    ledger.credit("0xsender", usdc, 500_000)
    rx = pm.sponsor(
        chain=chain,
        payer_address="0xsender",
        fee_token=usdc,
        gas_native=21_000,
        user_op_ref="op1",
    )
    assert rx.raw["transport"] == "evm-json-rpc"
    assert rx.raw["rpc_probe"]["entry_point_code_len"] > 0


def test_solana_rpc_adapter_balance_and_simulate():
    chain = ChainRef.solana("devnet")
    http = httpx.Client(transport=_sol_transport())
    rpc = SolanaJsonRpcClient(base_url="http://sol.test", http=http)
    adapter = SolanaRpcChainAdapter(chain=chain, rpc=rpc)
    sol = AssetRef(chain=chain, symbol="SOL", decimals=9)
    assert adapter.get_balance("SolAddr", sol).amount == 42
    adapter.credit("from", sol, 100)
    rx = adapter.transfer(
        "from", TransferRequest(asset=sol, to_address="to", amount=5)
    )
    assert rx.status == "simulated"
    assert rx.raw.get("blockhash") == "Hash111"


def test_stripe_licensed_gateway_uses_payment_intent():
    from fastapi.testclient import TestClient

    fake = TestClient(create_stripe_fake_app())
    gw = make_fiat_compliance_gateway(
        mode="stripe",
        environment="sandbox",
        api_key="sk_test_x",
        fiat_base_url="http://testserver/v1",
        http=fake,
    )
    chain = ChainRef.evm(1)
    usdc = AssetRef(chain=chain, symbol="USDC", decimals=6, token_address="0x1")
    pay = gw.pay_with_fiat(
        FiatPaymentRequest(
            amount_minor=1200,
            currency="USD",
            target_asset=usdc,
            agent_id="ed25519:a",
            idempotency_key="stripe-pay-1",
        )
    )
    assert pay.licensed is True
    assert pay.ref  # PaymentIntent id from fake


def test_sybil_time_window_expires_old_edges():
    risk = InMemoryRiskSignalStore()
    det = SybilGraphDetector(
        risk=risk,
        policy=SybilGraphPolicy(
            dust_amount=10,
            min_cluster_size=3,
            min_edges_in_cluster=2.5,
            window_sec=100,
            half_life_sec=50,
        ),
    )
    agents = [f"ed25519:W{i}" for i in range(3)]
    t0 = 1_000_000.0
    for i, (a, b) in enumerate([(0, 1), (1, 2), (0, 2)]):
        det.observe(
            ExchangeTerminalSnapshot(
                exchange_id=f"old-{i}",
                state="SETTLED",
                client=agents[a],
                provider=agents[b],
                resource_type="x",
                quantity=1,
                vdc_id=None,
                price_amount=1,
                price_currency="USD",
                outcome_hint="settled",
            ),
            now_ts=t0,
        )
    # 窗口外：应被剪枝，无聚类
    assert det.detect_clusters(now_ts=t0 + 500) == []
    # 窗口内重建
    for i, (a, b) in enumerate([(0, 1), (1, 2), (0, 2)]):
        det.observe(
            ExchangeTerminalSnapshot(
                exchange_id=f"new-{i}",
                state="SETTLED",
                client=agents[a],
                provider=agents[b],
                resource_type="x",
                quantity=1,
                vdc_id=None,
                price_amount=1,
                price_currency="USD",
                outcome_hint="settled",
            ),
            now_ts=t0 + 10,
        )
    clusters = det.detect_clusters(now_ts=t0 + 20)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3
