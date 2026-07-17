"""自主拆解 / 拍卖 / 编排闭环测试。"""

from __future__ import annotations

from novapanda.autonomy import (
    DynamicPricingEngine,
    HeuristicTaskDispatcher,
    InMemoryExchangeRunner,
    OrchestrationPhase,
    PricingInput,
    SupplyChainOrchestrator,
    TaskSpec,
    default_auctioneer,
    on_terminal_leg_update,
)
from novapanda.identity import Identity
from novapanda.marketplace import (
    DynamicScoreEngine,
    InMemoryServiceRegistry,
    InMemoryVolumeIndex,
    PriceQuote,
    ServiceListing,
    SlaOffer,
)
from novapanda.reputation import ReputationLog


def _registry_with_providers(*agent_ids: str) -> InMemoryServiceRegistry:
    reg = InMemoryServiceRegistry()
    for i, aid in enumerate(agent_ids):
        reg.register(
            ServiceListing(
                listing_id=f"L-{i}",
                agent_id=aid,
                resource_type="compute.pipeline",
                capability_tags=("nlp",),
                sla=SlaOffer(max_response_ms=5_000),
                price=PriceQuote(amount=50, currency="USD"),
                endpoints={"exchange": "http://x"},
            )
        )
    return reg


def test_pricing_engine_increases_with_complexity_and_load():
    eng = DynamicPricingEngine()
    base = PricingInput(
        resource_type="compute.pipeline",
        market_benchmark=PriceQuote(amount=100, currency="USD"),
        load_ratio=0.0,
        token_estimate=0,
        step_estimate=1,
    )
    heavy = PricingInput(
        resource_type="compute.pipeline",
        market_benchmark=PriceQuote(amount=100, currency="USD"),
        load_ratio=0.8,
        token_estimate=8_000,
        step_estimate=10,
        effective_reputation=0.0,
    )
    q0 = eng.quote(base)
    q1 = eng.quote(heavy)
    assert q1.price.amount > q0.price.amount
    assert q1.complexity_factor > 1.0
    assert "benchmark=" in q1.rationale


def test_dispatcher_splits_steps_into_chain():
    disp = HeuristicTaskDispatcher()
    spec = TaskSpec(
        goal_id="g1",
        resource_type="compute.pipeline",
        payload={},
        budget=PriceQuote(amount=500, currency="USD"),
        client_agent_id="ed25519:client",
        steps=(
            {"payload": {"op": "extract"}},
            {"payload": {"op": "enrich"}},
            {"payload": {"op": "summarize"}},
        ),
    )
    graph = disp.split_task(spec)
    assert len(graph.tasks) == 3
    assert graph.tasks[0].depends_on == ()
    assert graph.tasks[1].depends_on == (graph.tasks[0].sub_id,)
    assert graph.tasks[2].depends_on == (graph.tasks[1].sub_id,)


def test_dispatcher_splits_list_payload_parallel():
    disp = HeuristicTaskDispatcher()
    spec = TaskSpec(
        goal_id="g2",
        resource_type="compute.pipeline",
        payload=["a", "b", "c"],
        budget=PriceQuote(amount=300, currency="USD"),
        client_agent_id="ed25519:client",
    )
    graph = disp.split_task(spec)
    assert len(graph.tasks) == 3
    assert all(t.depends_on == () for t in graph.tasks)


def test_full_orchestrator_closed_loop():
    providers = [Identity.generate().agent_id for _ in range(2)]
    reg = _registry_with_providers(*providers)
    log = ReputationLog(Identity.generate())
    score = DynamicScoreEngine(reputation_log=log, volume=InMemoryVolumeIndex())
    auctioneer = default_auctioneer(reg, score, load_ratio=0.2)
    orch = SupplyChainOrchestrator(
        auctioneer=auctioneer,
        runner=InMemoryExchangeRunner(
            results={
                # filled after split — use catch-all via empty and default echo
            }
        ),
    )
    spec = TaskSpec(
        goal_id="goal-closed",
        resource_type="compute.pipeline",
        payload={"parts": [{"text": "one"}, {"text": "two"}]},
        budget=PriceQuote(amount=200, currency="USD"),
        client_agent_id=Identity.generate().agent_id,
        required_tags=("nlp",),
        max_response_ms=30_000,
        correlation_id="corr-1",
    )
    report = orch.run(spec)
    assert report.phase == OrchestrationPhase.DONE
    assert report.auction is not None
    assert len(report.auction.awards) == 2
    assert report.final_delivery["goal_id"] == "goal-closed"
    assert len(report.final_delivery["parts"]) == 2
    assert report.bundle_view is not None
    assert report.bundle_view["success_rule"] == "all_settled"
    assert len(report.bundle_view["exchange_ids"]) == 2


def test_on_terminal_leg_update_helper():
    providers = [Identity.generate().agent_id]
    reg = _registry_with_providers(*providers)
    log = ReputationLog(Identity.generate())
    score = DynamicScoreEngine(reputation_log=log, volume=InMemoryVolumeIndex())
    orch = SupplyChainOrchestrator(auctioneer=default_auctioneer(reg, score))
    spec = TaskSpec(
        goal_id="g-term",
        resource_type="compute.pipeline",
        payload="single",
        budget=PriceQuote(amount=100, currency="USD"),
        client_agent_id="ed25519:c",
        required_tags=("nlp",),
    )
    report = orch.run(spec)
    eid = next(iter(report.legs.values())).exchange_id
    assert eid
    # 模拟 Sink 再次通知
    assert on_terminal_leg_update(report, exchange_id=eid, state="SETTLED", vdc_id="v1")
