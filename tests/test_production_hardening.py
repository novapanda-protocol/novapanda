"""生产注入加固：RealExchangeRunner · EnvValidator · Gas fallback（模拟环境）。"""

from __future__ import annotations

import json

import httpx
import pytest

from novapanda import state_machine as sm
from novapanda.autonomy import (
    OrchestrationPhase,
    RealExchangeRunner,
    SupplyChainOrchestrator,
    TaskSpec,
    build_chain_injection_from_env,
    build_exchange_runner,
    default_auctioneer,
    env_wants_real_rails,
    make_signer_broadcast,
)
from novapanda.exchange import ExchangeEngine
from novapanda.hardening import EnvironmentValidator
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
from novapanda.settlement import MockSettlement
from novapanda.verifier import SchemaVerifier
from novapanda.wallet.rpc_resilience import with_resilient_estimate_gas
from novapanda.wallet.types import AssetRef, ChainRef, TransferRequest


def test_env_validator_stripe_live_format():
    v = EnvironmentValidator()
    issues = v.validate(
        {
            "NOVAPANDA_ENV": "production",
            "NOVAPANDA_OPERATOR_DB": "",  # will error
            "NOVAPANDA_FIAT_COMPLIANCE": "stripe",
            "NOVAPANDA_SETTLEMENT_ENV": "live",
            "STRIPE_LIVE_SECRET": "sk_test_wrong",
            "NOVAPANDA_AUTH": "1",
        },
        mode="production",
    )
    codes = {i.code for i in issues}
    assert "E_OPERATOR_DB_MISSING" in codes
    assert "E_STRIPE_LIVE_FORMAT" in codes


def test_env_validator_operator_db_ok(tmp_path):
    db = tmp_path / "op.sqlite"
    v = EnvironmentValidator()
    issues = v.validate(
        {
            "NOVAPANDA_ENV": "production",
            "NOVAPANDA_OPERATOR_DB": str(db),
            "NOVAPANDA_AUTH": "1",
            "NOVAPANDA_FIAT_COMPLIANCE": "stub",
        },
        mode="production",
    )
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []


def test_env_validator_strict_raises(tmp_path):
    v = EnvironmentValidator()
    issues = v.validate(
        {"NOVAPANDA_ENV": "production", "NOVAPANDA_AUTH": "0"},
        mode="production",
    )
    with pytest.raises(RuntimeError, match="E_AUTH_DISABLED|E_OPERATOR"):
        v.assert_or_raise(issues, strict=True)


def test_real_exchange_runner_full_path():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    runner = RealExchangeRunner(
        engine=engine,
        client=client,
        providers={provider.agent_id: provider},
        auto_complete=True,
        verify_rule={"schema": {"type": "object", "additionalProperties": True}},
    )

    class _Sub:
        sub_id = "sub-1"
        resource_type = "compute.pipeline"
        payload = {"answer": "ok"}
        rule_id_hint = "R1"

    out = runner.start_leg(
        sub=_Sub(),
        provider_agent_id=provider.agent_id,
        client_agent_id=client.agent_id,
        price={"amount": 10, "currency": "USD"},
        correlation_id="corr-1",
    )
    assert out["state"] == sm.SETTLED
    assert out["vdc_id"]
    polled = runner.poll_leg(out["exchange_id"])
    assert polled["state"] == sm.SETTLED


def test_orchestrator_with_real_runner_closed_loop():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    reg = InMemoryServiceRegistry()
    reg.register(
        ServiceListing(
            listing_id="L1",
            agent_id=provider.agent_id,
            resource_type="compute.pipeline",
            capability_tags=("nlp",),
            sla=SlaOffer(max_response_ms=5000),
            price=PriceQuote(amount=20, currency="USD"),
            endpoints={"exchange": "http://x"},
        )
    )
    score = DynamicScoreEngine(
        reputation_log=ReputationLog(Identity.generate()),
        volume=InMemoryVolumeIndex(),
    )
    auctioneer = default_auctioneer(reg, score)
    runner = RealExchangeRunner(
        engine=engine,
        client=client,
        providers={provider.agent_id: provider},
        verify_rule={"schema": {"type": "object", "additionalProperties": True}},
    )
    orch = SupplyChainOrchestrator(auctioneer=auctioneer, runner=runner)
    report = orch.run(
        TaskSpec(
            goal_id="g-real",
            resource_type="compute.pipeline",
            payload="hello",
            budget=PriceQuote(amount=100, currency="USD"),
            client_agent_id=client.agent_id,
            required_tags=("nlp",),
        )
    )
    assert report.phase == OrchestrationPhase.DONE
    assert all(leg.state == sm.SETTLED for leg in report.legs.values())


def test_build_exchange_runner_switches_on_env(monkeypatch):
    monkeypatch.delenv("NOVAPANDA_FORCE_REAL_RUNNER", raising=False)
    monkeypatch.delenv("NOVAPANDA_EVM_RPC_URL", raising=False)
    monkeypatch.delenv("SIGNER_BROADCAST_KEY", raising=False)
    monkeypatch.setenv("NOVAPANDA_SETTLEMENT", "mock")
    assert env_wants_real_rails() is False
    r = build_exchange_runner(force_memory=False)
    assert r.__class__.__name__ == "InMemoryExchangeRunner"

    monkeypatch.setenv("NOVAPANDA_FORCE_REAL_RUNNER", "1")
    client = Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    r2 = build_exchange_runner(engine=engine, client=client)
    assert isinstance(r2, RealExchangeRunner)


def test_chain_injection_with_simulated_signer(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        method = body.get("method")
        if method == "eth_estimateGas":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x5208"})
        if method == "eth_getBalance":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x0"})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x"})

    monkeypatch.setenv("NOVAPANDA_EVM_RPC_URL", "http://rpc.test")
    monkeypatch.setenv("SIGNER_BROADCAST_KEY", "SIMULATED")
    monkeypatch.setenv("NOVAPANDA_EVM_CHAIN_ID", "eip155:11155111")
    http = httpx.Client(transport=httpx.MockTransport(handler))
    inj = build_chain_injection_from_env(http_evm=http)
    assert inj.evm is not None
    assert inj.signer_configured is True
    eth = AssetRef(chain=inj.evm.chain, symbol="ETH", decimals=18)
    q = inj.evm.estimate_gas(
        "0xabc", TransferRequest(asset=eth, to_address="0xdef", amount=1)
    )
    assert q.native_gas_estimate == 0x5208


def test_gas_estimate_fallback_on_failure():
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
    assert q.native_gas_estimate == 21_000


def test_signer_broadcast_simulated():
    fn = make_signer_broadcast("test:abc")
    eth = AssetRef(chain=ChainRef.evm(1), symbol="ETH", decimals=18)
    raw = fn("0xfrom", TransferRequest(asset=eth, to_address="0xto", amount=3))
    assert raw.startswith("0x")
    assert len(raw) == 66
