"""Agent Skill 视角：Function Calling 模拟 · 结构化错误 · 紧凑视图。"""

from __future__ import annotations

from novapanda.agent_skill import (
    NovaPandaAgentSkill,
    RecoveryAction,
    TOOL_DEFINITIONS,
    classify_exception,
    compact_orchestration,
    compact_terminal_snapshot,
    tool_names,
)
from novapanda.autonomy import (
    InMemoryExchangeRunner,
    SupplyChainOrchestrator,
    default_auctioneer,
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
from novapanda.marketplace.types import ExchangeTerminalSnapshot
from novapanda.reputation import ReputationLog
from novapanda.settlement import MockSettlement, SettlementError
from novapanda.wallet.manager import WalletError
from novapanda.wallet.rpc_resilience import with_resilient_estimate_gas
from novapanda.wallet.types import AssetRef, ChainRef, TransferRequest


def _orch_with_listing(client: Identity, provider: Identity) -> SupplyChainOrchestrator:
    reg = InMemoryServiceRegistry()
    reg.register(
        ServiceListing(
            listing_id="L-skill",
            agent_id=provider.agent_id,
            resource_type="compute.pipeline",
            capability_tags=("nlp",),
            sla=SlaOffer(max_response_ms=5_000),
            price=PriceQuote(amount=20, currency="USD"),
            endpoints={"exchange": "http://x"},
        )
    )
    score = DynamicScoreEngine(
        reputation_log=ReputationLog(Identity.generate()),
        volume=InMemoryVolumeIndex(),
    )
    return SupplyChainOrchestrator(
        auctioneer=default_auctioneer(reg, score),
        runner=InMemoryExchangeRunner(),
    )


def test_tool_definitions_are_llm_friendly():
    names = tool_names()
    assert "novapanda_quote_price" in names
    assert "novapanda_run_supply_chain" in names
    for spec in TOOL_DEFINITIONS:
        assert len(spec["description"]) > 40
        assert "hex" not in spec["description"].lower() or "never" in spec["description"].lower()
        assert spec["parameters"]["type"] == "object"


def test_quote_price_tool_returns_structured_ints():
    skill = NovaPandaAgentSkill()
    out = skill.invoke(
        "novapanda_quote_price",
        {
            "resource_type": "compute.pipeline",
            "benchmark_amount": 100,
            "load_ratio": 0.5,
            "token_estimate": 2000,
            "step_estimate": 3,
        },
    )
    assert out["ok"] is True
    assert isinstance(out["result"]["amount"], int)
    assert "rationale" in out["result"]


def test_split_task_compact_omits_payload_by_default():
    skill = NovaPandaAgentSkill()
    client = Identity.generate()
    out = skill.invoke(
        "novapanda_split_task",
        {
            "goal_id": "g1",
            "resource_type": "compute.pipeline",
            "client_agent_id": client.agent_id,
            "budget_amount": 500,
            "payload": [{"op": "a"}, {"op": "b"}],
        },
    )
    assert out["ok"]
    tasks = out["result"]["tasks"]
    assert len(tasks) == 2
    assert "payload" not in tasks[0]
    assert tasks[0]["depends_on"] == []


def test_run_supply_chain_skill_closed_loop():
    client, provider = Identity.generate(), Identity.generate()
    skill = NovaPandaAgentSkill(orchestrator=_orch_with_listing(client, provider))
    out = skill.invoke(
        "novapanda_run_supply_chain",
        {
            "goal_id": "g-skill",
            "resource_type": "compute.pipeline",
            "client_agent_id": client.agent_id,
            "budget_amount": 200,
            "payload": {"answer": "ok"},
            "required_tags": ["nlp"],
        },
    )
    assert out["ok"] is True
    assert out["result"]["phase"] == "done"
    assert out["result"]["ok"] is True
    assert len(str(out)) < 2500  # token-ish budget smoke


def test_settlement_tools_and_conflict_fault():
    skill = NovaPandaAgentSkill(settlement=MockSettlement())
    esc = skill.invoke(
        "novapanda_settlement_escrow",
        {"exchange_id": "ex-1", "amount": 10, "currency": "USD"},
    )
    assert esc["ok"]
    handle = esc["result"]["handle"]
    settled = skill.invoke("novapanda_settlement_settle", {"handle": handle})
    assert settled["ok"]
    # settle 幂等 OK；再 refund 则状态冲突 → Agent 应 escalate_human
    refund = skill.invoke("novapanda_settlement_refund", {"handle": handle})
    assert refund["ok"] is False
    assert refund["fault"]["code"] == "SETTLEMENT_CONFLICT"
    assert refund["fault"]["recovery"] == "escalate_human"
    assert refund["fault"]["retryable"] is False


def test_classify_rpc_timeout_and_paymaster():
    f1 = classify_exception(TimeoutError("estimate_gas timeout"))
    assert f1.code == "RPC_TIMEOUT"
    assert f1.retryable is True
    assert f1.recovery == RecoveryAction.RETRY_SAME

    f2 = classify_exception(
        WalletError("insufficient fee token for paymaster")
    )
    assert f2.code == "PAYMASTER_UNDERFUNDED"
    assert f2.recovery == RecoveryAction.RETRY_ADJUST

    f3 = classify_exception(SettlementError("escrow 状态冲突：settled -> refunded"))
    assert f3.code == "SETTLEMENT_CONFLICT"


def test_classify_error_tool():
    skill = NovaPandaAgentSkill()
    out = skill.invoke(
        "novapanda_classify_error",
        {"message": "stripe card_declined payment_intent"},
    )
    assert out["ok"]
    assert out["result"]["code"] == "STRIPE_ERROR"


def test_compact_terminal_shortens_agent_ids():
    long_id = "ed25519:" + ("A" * 64)
    snap = ExchangeTerminalSnapshot(
        exchange_id="ex-9",
        state="SETTLED",
        client=long_id,
        provider=long_id,
        resource_type="compute.pipeline",
        quantity=1,
        vdc_id="vdc-1",
        price_amount=42,
        price_currency="USD",
        outcome_hint="settled",
    )
    c = compact_terminal_snapshot(snap)
    assert "…" in c["client"]
    assert len(c["client"]) < len(long_id)
    assert "amount" in c and "price_amount" not in c

    skill = NovaPandaAgentSkill()
    out = skill.invoke(
        "novapanda_compact_terminal",
        {
            "exchange_id": "ex-9",
            "state": "SETTLED",
            "client": long_id,
            "provider": long_id,
            "resource_type": "compute.pipeline",
            "quantity": 1,
            "price_amount": 42,
            "outcome_hint": "settled",
        },
    )
    assert out["ok"]
    assert out["result"]["amount"] == 42


def test_gas_fallback_sets_degraded_flag():
    class Boom:
        chain = ChainRef.evm(1)
        native_symbol = "ETH"

        def estimate_gas(self, from_address, req):
            raise RuntimeError("rpc down")

    adapter = with_resilient_estimate_gas(Boom(), max_retries=2, timeout_sec=1.0, backoff_sec=0)
    eth = AssetRef(chain=ChainRef.evm(1), symbol="ETH", decimals=18)
    q = adapter.estimate_gas(
        "0x1", TransferRequest(asset=eth, to_address="0x2", amount=1)
    )
    assert q.degraded is True
    assert q.native_gas_estimate == 21_000


def test_misconfigured_orchestrator_fault():
    skill = NovaPandaAgentSkill()  # no orchestrator
    out = skill.invoke(
        "novapanda_run_supply_chain",
        {
            "goal_id": "g",
            "resource_type": "compute.pipeline",
            "client_agent_id": "ed25519:x",
            "budget_amount": 1,
        },
    )
    assert out["ok"] is False
    assert out["fault"]["code"] == "SKILL_MISCONFIGURED"


def test_compact_orchestration_helper():
    client, provider = Identity.generate(), Identity.generate()
    orch = _orch_with_listing(client, provider)
    from novapanda.autonomy import TaskSpec

    report = orch.run(
        TaskSpec(
            goal_id="g2",
            resource_type="compute.pipeline",
            payload={"x": 1},
            budget=PriceQuote(amount=100, currency="USD"),
            client_agent_id=client.agent_id,
            required_tags=("nlp",),
        )
    )
    compact = compact_orchestration(report)
    assert compact["ok"] is True
    assert "final_delivery" not in compact
