"""ScoreEngine 金额衰减 / 风控惩罚 + MatchRouter 多维撮合。"""

from __future__ import annotations

from novapanda.identity import Identity
from novapanda.marketplace import (
    DynamicScoreEngine,
    InMemoryRiskSignalStore,
    InMemoryVolumeIndex,
    ListingStatus,
    MatchQuery,
    MatchWeights,
    PriceQuote,
    RiskPolicy,
    ScorePolicy,
    ServiceListing,
    SlaOffer,
    WeightedMatchRouter,
)
from novapanda.marketplace.types import ExchangeTerminalSnapshot, ReputationView
from novapanda.reputation import ReputationLog


def _log_with_entries():
    node = Identity.generate()
    log = ReputationLog(node)
    return log


def _append(log: ReputationLog, *, agent: str, peer: str, eid: str, outcome: str, qty: int = 1):
    return log.append(
        agent_id=agent,
        counterparty=peer,
        exchange_id=eid,
        vdc_id=None,
        role="provider",
        outcome=outcome,
        resource_type="compute.qa",
        quantity=qty,
    )


def test_amount_decay_prefers_large_settled_over_dust_wash():
    """一大笔成功交割应压过大量尘埃 settled（防刷单灌水）。"""
    log = _log_with_entries()
    vol = InMemoryVolumeIndex()
    agent, peer = "ed25519:AgentA", "ed25519:PeerB"
    # 99 笔尘埃 settled
    for i in range(99):
        eid = f"ex-dust-{i}"
        _append(log, agent=agent, peer=peer, eid=eid, outcome="settled")
        vol.record(eid, amount=1, currency="USD")
    # 1 笔大额 rejected —— 若等权，score≈0.99；金额衰减后大额 rejected 应显著拉低
    _append(log, agent=agent, peer=peer, eid="ex-big", outcome="rejected", qty=1)
    vol.record("ex-big", amount=10_000, currency="USD")

    engine = DynamicScoreEngine(
        reputation_log=log,
        volume=vol,
        policy=ScorePolicy(dust_amount=10, reference_amount=1000),
    )
    view = engine.view(agent)
    assert view.score is not None
    equal_weight = 99 / 100  # 若等权 ≈ 0.99
    # 金额衰减后应显著低于等权（大单 rejected 权重大）
    assert view.score < equal_weight - 0.3
    assert view.settled_count == 99
    assert view.rejected_count == 1


def test_sybil_wash_penalty_reduces_effective_score():
    log = _log_with_entries()
    agent, client = Identity.generate().agent_id, Identity.generate().agent_id
    vol = InMemoryVolumeIndex()
    for i in range(3):
        eid = f"ex-ok-{i}"
        _append(log, agent=agent, peer=client, eid=eid, outcome="settled")
        vol.record(eid, amount=500, currency="USD")

    risk = InMemoryRiskSignalStore(policy=RiskPolicy(wash_pair_threshold=5, dust_amount=10))
    # 直接标记女巫
    risk.mark_sybil_cluster([agent], severity=0.5, cluster_id="c1")

    engine = DynamicScoreEngine(reputation_log=log, volume=vol, risk=risk)
    view = engine.view(agent)
    assert view.score == 1.0
    assert view.risk_penalty == 0.5
    assert view.effective_score == 0.5


def test_wash_trade_auto_signal_from_dust_pairs():
    risk = InMemoryRiskSignalStore(
        policy=RiskPolicy(wash_pair_threshold=5, dust_amount=10, wash_dust_ratio=0.8)
    )
    a, b = Identity.generate().agent_id, Identity.generate().agent_id
    for i in range(5):
        risk.observe_terminal(
            ExchangeTerminalSnapshot(
                exchange_id=f"e{i}",
                state="SETTLED",
                client=a,
                provider=b,
                resource_type="x",
                quantity=1,
                vdc_id=None,
                price_amount=1,
                price_currency="USD",
                outcome_hint="settled",
            )
        )
    assert risk.penalty(a) > 0
    assert risk.penalty(b) > 0
    assert any(s.kind.value == "wash_trade" for s in risk.signals_for(a))


def test_match_router_ranks_by_price_sla_reputation():
    cheap_fast = ServiceListing(
        listing_id="L1",
        agent_id="p-cheap",
        resource_type="compute.qa",
        capability_tags=("ocr", "fast"),
        sla=SlaOffer(max_response_ms=100),
        price=PriceQuote(amount=50, currency="USD"),
        endpoints={"exchange": "http://a"},
    )
    expensive_slow = ServiceListing(
        listing_id="L2",
        agent_id="p-slow",
        resource_type="compute.qa",
        capability_tags=("ocr",),
        sla=SlaOffer(max_response_ms=900),
        price=PriceQuote(amount=90, currency="USD"),
        endpoints={"exchange": "http://b"},
    )
    query = MatchQuery(
        resource_type="compute.qa",
        quantity=1,
        max_price=PriceQuote(amount=100, currency="USD"),
        max_response_ms=1000,
        preferred_tags=("fast",),
        limit=5,
    )
    views = {
        "p-cheap": ReputationView(
            agent_id="p-cheap",
            score=0.9,
            entry_count=10,
            settled_count=9,
            rejected_count=1,
            effective_score=0.9,
        ),
        "p-slow": ReputationView(
            agent_id="p-slow",
            score=0.95,
            entry_count=10,
            settled_count=10,
            rejected_count=0,
            effective_score=0.95,
        ),
    }
    decision = WeightedMatchRouter(weights=MatchWeights()).route(
        query, [expensive_slow, cheap_fast], views
    )
    assert decision.winner is not None
    assert decision.winner.listing.listing_id == "L1"
    assert decision.ranked[0].breakdown.price_score > decision.ranked[1].breakdown.price_score


def test_match_router_filters_over_price_and_low_rep():
    listing = ServiceListing(
        listing_id="L3",
        agent_id="p-bad",
        resource_type="compute.qa",
        capability_tags=(),
        sla=SlaOffer(max_response_ms=100),
        price=PriceQuote(amount=200, currency="USD"),
        endpoints={"exchange": "http://c"},
        status=ListingStatus.ACTIVE,
    )
    query = MatchQuery(
        resource_type="compute.qa",
        quantity=1,
        max_price=PriceQuote(amount=100, currency="USD"),
        max_response_ms=500,
        min_reputation=0.8,
    )
    views = {
        "p-bad": ReputationView(
            agent_id="p-bad",
            score=0.2,
            entry_count=5,
            settled_count=1,
            rejected_count=4,
            effective_score=0.2,
        )
    }
    decision = WeightedMatchRouter().route(query, [listing], views)
    assert decision.winner is None
    assert "no eligible" in decision.reason


def test_risk_penalty_lowers_match_total():
    listing = ServiceListing(
        listing_id="L4",
        agent_id="p-risk",
        resource_type="compute.qa",
        capability_tags=(),
        sla=SlaOffer(max_response_ms=100),
        price=PriceQuote(amount=50, currency="USD"),
        endpoints={"exchange": "http://d"},
    )
    query = MatchQuery(
        resource_type="compute.qa",
        quantity=1,
        max_price=PriceQuote(amount=100, currency="USD"),
        max_response_ms=500,
    )
    clean = ReputationView(
        agent_id="p-risk",
        score=1.0,
        entry_count=3,
        settled_count=3,
        rejected_count=0,
        effective_score=1.0,
        risk_penalty=0.0,
    )
    dirty = ReputationView(
        agent_id="p-risk",
        score=1.0,
        entry_count=3,
        settled_count=3,
        rejected_count=0,
        effective_score=0.4,
        risk_penalty=0.6,
    )
    router = WeightedMatchRouter()
    t_clean = router.route(query, [listing], {"p-risk": clean}).winner.breakdown.total
    t_dirty = router.route(query, [listing], {"p-risk": dirty}).winner.breakdown.total
    assert t_dirty < t_clean
