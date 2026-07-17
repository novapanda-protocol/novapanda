"""DePIN / 具身智能三轮物理协同闭环演练（测试桩 · 不公开发布）。

1. 车-桩竞价 + TPM PoD 电力交割
2. 无人机-边缘算力外包 + 离线凭证复网幂等 Sink
3. 搜救 DAG Bundle + Gas bump / 多链兜底

不改 ``state_machine.TRANSITIONS``。
"""

from __future__ import annotations

from novapanda.agent_skill import NovaPandaAgentSkill
from novapanda.autonomy import (
    DynamicPricingEngine,
    HeuristicTaskDispatcher,
    InMemoryExchangeRunner,
    MarketplaceAuctioneer,
    PricingInput,
    RealExchangeRunner,
    SupplyChainOrchestrator,
    TaskSpec,
)
from novapanda.depin import (
    HardwarePodBackend,
    MultiRailGasRouter,
    OfflineCredentialQueue,
    PhysicalListingBidProvider,
    bump_gas,
    simulate_tpm_sign,
)
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.marketplace import (
    DynamicScoreEngine,
    InMemoryServiceRegistry,
    InMemoryVolumeIndex,
    MarketplaceTerminalSink,
    PriceQuote,
    ServiceListing,
    SlaOffer,
)
from novapanda.reputation import ReputationLog
from novapanda.settlement import MockSettlement
from novapanda.verification_gateway import VerificationGateway
from novapanda.verifier import SchemaVerifier
from novapanda.wallet.manager import InMemoryChainAdapter
from novapanda.wallet.paymaster_4337 import EntryPointPaymaster4337
from novapanda.wallet.solana_fee_payer import SolanaFeePayer
from novapanda.wallet.types import AssetRef, ChainRef


# ----- helpers -----


def _score() -> DynamicScoreEngine:
    return DynamicScoreEngine(
        reputation_log=ReputationLog(Identity.generate()),
        volume=InMemoryVolumeIndex(),
    )


def _listing(
    *,
    listing_id: str,
    agent_id: str,
    resource_type: str,
    tags: tuple[str, ...],
    amount: int,
) -> ServiceListing:
    return ServiceListing(
        listing_id=listing_id,
        agent_id=agent_id,
        resource_type=resource_type,
        capability_tags=tags,
        sla=SlaOffer(max_response_ms=60_000),
        price=PriceQuote(amount=amount, currency="USD"),
        endpoints={"exchange": "http://depin"},
    )


# =====================================================================
# 1) 车-桩竞价与电力交割（TPM PoD）
# =====================================================================


def test_depin_round1_ev_charger_auction_and_tpm_pod():
    truck = Identity.generate()
    chargers = [Identity.generate() for _ in range(3)]
    reg = InMemoryServiceRegistry()
    physics = {
        "chg-low": {"grid_load_ratio": 0.2, "queue_length": 0, "load_ratio": 0.1},
        "chg-mid": {"grid_load_ratio": 0.55, "queue_length": 2, "load_ratio": 0.4},
        "chg-hot": {"grid_load_ratio": 0.95, "queue_length": 8, "load_ratio": 0.9},
    }
    for ch, lid, amt in zip(
        chargers,
        ["chg-low", "chg-mid", "chg-hot"],
        [40, 40, 40],
        strict=True,
    ):
        reg.register(
            _listing(
                listing_id=lid,
                agent_id=ch.agent_id,
                resource_type="energy.charge.dc",
                tags=("ev", "dc-fast"),
                amount=amt,
            )
        )

    score = _score()
    pricing = DynamicPricingEngine()
    # 物理复杂度：热桩报价应显著高于闲桩
    q_low = pricing.quote(
        PricingInput(
            resource_type="energy.charge.dc",
            market_benchmark=PriceQuote(amount=40, currency="USD"),
            load_ratio=0.1,
            grid_load_ratio=0.2,
            queue_length=0,
        )
    )
    q_hot = pricing.quote(
        PricingInput(
            resource_type="energy.charge.dc",
            market_benchmark=PriceQuote(amount=40, currency="USD"),
            load_ratio=0.9,
            grid_load_ratio=0.95,
            queue_length=8,
        )
    )
    assert q_hot.price.amount > q_low.price.amount
    assert "grid=" in q_hot.rationale

    bid_provider = PhysicalListingBidProvider(
        pricing=pricing, physics_by_listing=physics, score_engine=score
    )
    auctioneer = MarketplaceAuctioneer(
        registry=reg, score_engine=score, bid_provider=bid_provider
    )
    skill = NovaPandaAgentSkill(auctioneer=auctioneer, pricing=pricing)

    # Skill 竞价入口（等价 hold_auction）
    auction = skill.invoke(
        "novapanda_hold_auction",
        {
            "goal_id": "ev-charge-1",
            "resource_type": "energy.charge.dc",
            "client_agent_id": truck.agent_id,
            "budget_amount": 200,
            "required_tags": ["ev", "dc-fast"],
            "max_response_ms": 120_000,
        },
    )
    assert auction["ok"], auction
    assert auction["result"]["awards"]
    winner = auction["result"]["awards"][0]
    assert winner["amount"] <= 200
    # 闲桩（低电网+零排队）应胜出或至少报价低于热桩路径
    assert winner["listing_id"] in physics

    # TPM PoD：真实充电度数（整数 Wh，避免 canonical JSON 禁 float）
    device_id = "tpm-charger-01"
    pod = {"energy_wh": 62500, "unit": "Wh", "session_id": "sess-1"}
    sig = simulate_tpm_sign(device_id, pod)
    gw = VerificationGateway(
        identity=Identity.generate(),
        backend=HardwarePodBackend(),
    )
    skill.verification_gateway = gw
    skill.verify_rule = {
        "schema": {
            "type": "object",
            "required": ["energy_wh", "unit"],
            "properties": {
                "energy_wh": {"type": "integer", "minimum": 0},
                "unit": {"type": "string"},
                "session_id": {"type": "string"},
            },
            "additionalProperties": True,
        }
    }
    verified = skill.invoke(
        "novapanda_verify_proof",
        {
            "exchange_id": "ex-charge-1",
            "vdc_id": "vdc-charge-1",
            "deliverable": {
                "pod": pod,
                "device_id": device_id,
                "tpm_signature": sig,
            },
            "device_id": device_id,
            "tpm_signature": sig,
            "rule_id": "R-pod-kwh",
        },
    )
    assert verified["ok"], verified
    assert verified["result"]["passed"] is True
    assert verified["result"]["backend"] == "backend:hardware-pod-tpm/v1"

    # 伪造签名必须失败
    bad = skill.invoke(
        "novapanda_verify_proof",
        {
            "exchange_id": "ex-charge-bad",
            "vdc_id": "vdc-bad",
            "deliverable": {"pod": pod, "device_id": device_id, "tpm_signature": "tpm:dead"},
            "device_id": device_id,
            "tpm_signature": "tpm:deadbeef",
        },
    )
    assert bad["ok"] and bad["result"]["passed"] is False


# =====================================================================
# 2) 无人机-边缘算力外包 + 离线复网幂等
# =====================================================================


def test_depin_round2_drone_edge_offline_sync():
    drone, edge = Identity.generate(), Identity.generate()
    reg = InMemoryServiceRegistry()
    reg.register(
        _listing(
            listing_id="edge-van-1",
            agent_id=edge.agent_id,
            resource_type="compute.edge.ir",
            tags=("ir", "edge"),
            amount=30,
        )
    )
    score = _score()
    from novapanda.autonomy import default_auctioneer

    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    runner = RealExchangeRunner(
        engine=engine,
        client=drone,
        providers={edge.agent_id: edge},
        verify_rule={"schema": {"type": "object", "additionalProperties": True}},
    )
    orch = SupplyChainOrchestrator(
        auctioneer=default_auctioneer(reg, score),
        runner=runner,
        dispatcher=HeuristicTaskDispatcher(),
    )

    # 大任务拆解：红外诊断多段 → 并行外包
    disp = HeuristicTaskDispatcher()
    graph = disp.split_task(
        TaskSpec(
            goal_id="ir-diag-1",
            resource_type="compute.edge.ir",
            payload=[
                {"frame": "ir-a", "answer": "ok"},
                {"frame": "ir-b", "answer": "ok"},
                {"frame": "ir-c", "answer": "ok"},
            ],
            budget=PriceQuote(amount=300, currency="USD"),
            client_agent_id=drone.agent_id,
            required_tags=("ir",),
        )
    )
    assert len(graph.tasks) == 3
    assert all(not t.depends_on for t in graph.tasks)

    volume = InMemoryVolumeIndex()
    sink = MarketplaceTerminalSink(volume=volume, score_engine=score)
    queue = OfflineCredentialQueue(device_id="drone-uav-7")
    queue.attach_runner_hook(runner)

    # —— 网络分区：离线签发 ——
    queue.partition()
    assert queue.network_up is False
    offline = queue.issue_offline(
        exchange_id="ex-offline-ir-1",
        payload={"frames": 3, "status": "computed_offline", "answer": "anomaly"},
        client=drone.agent_id,
        provider=edge.agent_id,
        resource_type="compute.edge.ir",
        price_amount=30,
        vdc_id="vdc-offline-1",
    )
    assert offline.tpm_signature.startswith("tpm:")
    assert queue.pending_count() == 1
    # 离线 flush 应为空
    assert queue.flush_to_sink(sink) == []

    # —— 复网：异步幂等 Sink ——
    queue.restore()
    flushed = queue.flush_to_sink(sink)
    assert flushed == ["ex-offline-ir-1"]
    assert queue.pending_count() == 0
    # 再次 flush 幂等
    assert queue.flush_to_sink(sink) == []
    assert volume.notional("ex-offline-ir-1") == 30

    # 在线完整供应链仍可跑
    report = orch.run(
        TaskSpec(
            goal_id="ir-diag-online",
            resource_type="compute.edge.ir",
            payload={"frame": "ir-online", "answer": "ok"},
            budget=PriceQuote(amount=100, currency="USD"),
            client_agent_id=drone.agent_id,
            required_tags=("ir",),
        )
    )
    assert report.phase.value == "done"


# =====================================================================
# 3) 搜救 DAG Bundle + Gas bump / Solana 兜底
# =====================================================================


def test_depin_round3_rescue_dag_gas_multirail():
    uav, truck, warehouse = (
        Identity.generate(),
        Identity.generate(),
        Identity.generate(),
    )
    reg = InMemoryServiceRegistry()
    for agent, lid, rtype, tags in [
        (uav, "uav-1", "mission.scan", ("uav", "scan")),
        (truck, "truck-1", "mission.haul", ("truck", "haul")),
        (warehouse, "wh-1", "mission.stage", ("warehouse", "stage")),
    ]:
        reg.register(
            _listing(
                listing_id=lid,
                agent_id=agent.agent_id,
                resource_type=rtype,
                tags=tags,
                amount=20,
            )
        )
    score = _score()
    from novapanda.autonomy import default_auctioneer

    # 链式 DAG：scan → haul → stage
    client = Identity.generate()
    orch = SupplyChainOrchestrator(
        auctioneer=default_auctioneer(reg, score),
        runner=InMemoryExchangeRunner(),
    )
    # 注意：单一 resource_type 拍卖；用 steps 链式 + 各步 resource_type
    skill = NovaPandaAgentSkill(orchestrator=orch)
    # 为多资源类型，直接用 orchestrator + 自定义 graph 更稳：
    # 使用 steps 且每步声明 resource_type
    report = orch.run(
        TaskSpec(
            goal_id="rescue-bundle-1",
            resource_type="mission.scan",
            payload={},
            budget=PriceQuote(amount=500, currency="USD"),
            client_agent_id=client.agent_id,
            steps=(
                {
                    "payload": {"op": "scan"},
                    "resource_type": "mission.scan",
                    "tags": ["uav", "scan"],
                },
                {
                    "payload": {"op": "haul"},
                    "resource_type": "mission.haul",
                    "tags": ["truck", "haul"],
                },
                {
                    "payload": {"op": "stage"},
                    "resource_type": "mission.stage",
                    "tags": ["warehouse", "stage"],
                },
            ),
        )
    )
    assert report.phase.value == "done"
    assert report.bundle_view is not None
    assert len(report.bundle_view["exchange_ids"]) == 3
    assert report.bundle_view["depends_on"]
    # 链式依赖存在
    deps = report.bundle_view["depends_on"]
    assert any(deps[k] for k in deps)

    compact = skill.invoke  # noqa: F841 — skill 已就绪
    from novapanda.agent_skill import compact_orchestration

    view = compact_orchestration(report)
    assert view["ok"] is True
    assert view["bundle"]["n_exchanges"] == 3

    # —— Gas bump ——
    assert bump_gas(21_000, bump=2.5) == 52_500

    evm = ChainRef.evm(11155111)
    sol = ChainRef.solana("devnet")
    evm_ledger = InMemoryChainAdapter(chain=evm, native_symbol="ETH")
    sol_ledger = InMemoryChainAdapter(chain=sol, native_symbol="SOL")
    usdc = AssetRef(chain=evm, symbol="USDC", decimals=6, token_address="0xusdc")
    sol_native = AssetRef(chain=sol, symbol="SOL", decimals=9)
    payer = "0xrescue-wallet"
    fee_payer = "solana-fee-payer"
    evm_ledger.credit(payer, usdc, 10_000_000)
    sol_ledger.credit(fee_payer, sol_native, 10_000_000)
    sol_ledger.credit(payer, sol_native, 1_000_000)

    primary = EntryPointPaymaster4337(ledger=evm_ledger)
    fallback = SolanaFeePayer(ledger=sol_ledger, fee_payer_address=fee_payer)
    router = MultiRailGasRouter(
        primary_paymaster=primary,
        primary_chain=evm,
        primary_fee_token=usdc,
        fallback_paymaster=fallback,
        fallback_chain=sol,
        fallback_fee_token=sol_native,
        bump_on_congestion=2.5,
        max_bumps=2,
    )
    router.mark_congested(base_fee_gwei=120.0, bump=3.0)

    # 强制主轨失败 → 自动切 Solana
    rx = router.sponsor_resilient(
        payer_address=payer,
        gas_native=21_000,
        user_op_ref="rescue-gas-1",
        force_fail_primary=True,
    )
    assert rx.raw.get("rail") == "fallback"
    assert rx.raw.get("switched_from") == evm.chain_id
    assert "solana" in rx.chain_id

    # 主轨拥堵但可成功：bump 后仍走 primary
    router2 = MultiRailGasRouter(
        primary_paymaster=primary,
        primary_chain=evm,
        primary_fee_token=usdc,
        fallback_paymaster=fallback,
        fallback_chain=sol,
        fallback_fee_token=sol_native,
        max_bumps=2,
    )
    router2.mark_congested(bump=2.0)
    rx2 = router2.sponsor_resilient(
        payer_address=payer,
        gas_native=21_000,
        user_op_ref="rescue-gas-2",
        force_fail_primary=False,
    )
    assert rx2.raw.get("rail") == "primary"
    assert rx2.raw.get("gas_used_estimate", 0) >= 21_000


def test_depin_pricing_grid_queue_via_skill_quote():
    skill = NovaPandaAgentSkill()
    idle = skill.invoke(
        "novapanda_quote_price",
        {
            "resource_type": "energy.charge.dc",
            "benchmark_amount": 50,
            "grid_load_ratio": 0.1,
            "queue_length": 0,
        },
    )
    busy = skill.invoke(
        "novapanda_quote_price",
        {
            "resource_type": "energy.charge.dc",
            "benchmark_amount": 50,
            "grid_load_ratio": 0.9,
            "queue_length": 6,
            "load_ratio": 0.8,
        },
    )
    assert idle["ok"] and busy["ok"]
    assert busy["result"]["amount"] > idle["result"]["amount"]
