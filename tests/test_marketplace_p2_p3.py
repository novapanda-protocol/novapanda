"""P2/P3：4337 Paymaster · Solana fee-payer · 持牌法币 · Sybil · 联邦 · 统一门闸。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.marketplace import (
    DefaultMarketplaceFacade,
    DynamicScoreEngine,
    InMemoryRiskSignalStore,
    InMemoryServiceRegistry,
    InMemoryVolumeIndex,
    MatchQuery,
    PriceQuote,
    ReputationMatchPolicy,
    ServiceListing,
    SlaOffer,
    SybilGraphDetector,
    SybilGraphPolicy,
    WeightedMatchRouter,
    build_listing_bundle,
    import_listing_bundle,
)
from novapanda.marketplace.types import ExchangeTerminalSnapshot
from novapanda.node import create_app
from novapanda.reputation import ReputationLog
from novapanda.wallet import (
    AssetRef,
    ChainRef,
    EntryPointPaymaster4337,
    FiatPaymentRequest,
    FiatSettlementRequest,
    InMemoryChainAdapter,
    LicensedFiatComplianceGateway,
    SolanaFeePayer,
    TransferRequest,
    UserOperation,
    encode_transfer_call,
    make_fiat_compliance_gateway,
)


def test_entrypoint_paymaster_4337_sponsors_with_user_op():
    chain = ChainRef.evm(11155111)
    ledger = InMemoryChainAdapter(chain=chain)
    pm = EntryPointPaymaster4337(ledger=ledger, token_per_gas_unit=3)
    usdc = AssetRef(chain=chain, symbol="USDC", decimals=6, token_address="0xusdc")
    sender = "0x" + "11" * 20
    ledger.credit(sender, usdc, 1_000_000)
    op = UserOperation(
        sender=sender,
        nonce=1,
        call_data=encode_transfer_call("0x" + "22" * 20, 10),
        call_gas_limit=50_000,
        verification_gas_limit=30_000,
        pre_verification_gas=10_000,
        max_fee_per_gas=1,
        max_priority_fee_per_gas=1,
        paymaster_and_data=pm.build_paymaster_and_data(usdc),
    )
    rx = pm.sponsor(
        chain=chain,
        payer_address=sender,
        fee_token=usdc,
        gas_native=0,
        user_op_ref="",
        user_op=op,
    )
    assert rx.raw["standard"] == "erc-4337"
    assert ledger.get_balance(sender, usdc).amount == 1_000_000 - op.total_gas() * 3


def test_solana_fee_payer_pays_from_sponsor_account():
    chain = ChainRef.solana("devnet")
    ledger = InMemoryChainAdapter(chain=chain, native_symbol="SOL")
    fee_payer = "solFeePayer"
    user = "solUser"
    sol = AssetRef(chain=chain, symbol="SOL", decimals=9)
    ledger.credit(fee_payer, sol, 100_000)
    ledger.credit(user, sol, 1_000)
    fp = SolanaFeePayer(ledger=ledger, fee_payer_address=fee_payer, lamports_per_sig=5_000)
    rx = fp.sponsor(
        chain=chain,
        payer_address=user,
        fee_token=sol,
        gas_native=5_000,
        user_op_ref="tx1",
    )
    assert rx.raw["standard"] == "solana-fee-payer"
    assert ledger.get_balance(fee_payer, sol).amount == 95_000
    assert ledger.get_balance(user, sol).amount == 1_000  # user not charged


def test_licensed_fiat_gateway_vs_stub():
    stub = make_fiat_compliance_gateway(mode="stub")
    licensed = make_fiat_compliance_gateway(mode="licensed", partner="stripe")
    chain = ChainRef.evm(1)
    usdc = AssetRef(chain=chain, symbol="USDC", decimals=6, token_address="0x1")
    req = FiatPaymentRequest(
        amount_minor=500,
        currency="USD",
        target_asset=usdc,
        agent_id="ed25519:a",
        idempotency_key="pay-1",
    )
    assert stub.pay_with_fiat(req).licensed is False
    assert licensed.pay_with_fiat(req).licensed is True
    settle = licensed.settle_to_fiat(
        FiatSettlementRequest(
            amount=10,
            asset=usdc,
            agent_id="ed25519:a",
            bank_ref="acct",
            idempotency_key="out-1",
        )
    )
    assert settle.licensed is True
    assert isinstance(licensed, LicensedFiatComplianceGateway)


def test_sybil_graph_marks_dust_clique():
    risk = InMemoryRiskSignalStore()
    det = SybilGraphDetector(
        risk=risk,
        policy=SybilGraphPolicy(
            dust_amount=10,
            min_cluster_size=3,
            min_edges_in_cluster=2.5,
            window_sec=10_000,
            half_life_sec=10_000,
        ),
    )
    agents = [f"ed25519:A{i}" for i in range(3)]
    t0 = 1_700_000_000.0
    # triangle of dust settles
    pairs = [(0, 1), (1, 2), (0, 2)]
    for i, (a, b) in enumerate(pairs):
        det.observe(
            ExchangeTerminalSnapshot(
                exchange_id=f"e{i}",
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
            now_ts=t0 + i,
        )
    sigs = det.detect_and_mark(now_ts=t0 + 10)
    assert len(sigs) >= 3
    assert risk.penalty(agents[0]) > 0


def test_reputation_match_policy_floors_min_reputation():
    log = ReputationLog(Identity.generate())
    score = DynamicScoreEngine(reputation_log=log, volume=InMemoryVolumeIndex())
    reg = InMemoryServiceRegistry()
    agent = Identity.generate().agent_id
    reg.register(
        ServiceListing(
            listing_id="L1",
            agent_id=agent,
            resource_type="compute.qa",
            capability_tags=(),
            sla=SlaOffer(max_response_ms=100),
            price=PriceQuote(amount=10, currency="USD"),
            endpoints={"exchange": "http://x"},
        )
    )
    facade = DefaultMarketplaceFacade.build_default(
        reg,
        score,
        router=WeightedMatchRouter(cold_reputation=0.4),
        policy=ReputationMatchPolicy(min_score=0.8),
    )
    # cold 0.4 < floor 0.8 → filtered out
    d = facade.find_providers(
        MatchQuery(
            resource_type="compute.qa",
            quantity=1,
            max_price=PriceQuote(amount=100, currency="USD"),
            max_response_ms=1000,
            min_reputation=0.0,
        )
    )
    assert d.winner is None


def test_listing_federation_export_import_http():
    app_a = create_app(seed=True, auth=False, marketplace_enabled=True)
    app_b = create_app(seed=True, auth=False, marketplace_enabled=True)
    tc_a, tc_b = TestClient(app_a), TestClient(app_b)
    agent = Identity.generate().agent_id
    tc_a.post(
        "/marketplace/listings",
        json={
            "listing_id": "L-fed",
            "agent_id": agent,
            "resource_type": "compute.qa",
            "price_amount": 25,
            "price_currency": "USD",
            "max_response_ms": 100,
            "exchange_endpoint": "http://a",
        },
    )
    exported = tc_a.get("/marketplace/listings/export").json()
    assert exported["kind"] == "listing_federation"
    assert len(exported["listings"]) == 1

    imp = tc_b.post("/marketplace/listings/import", json={"bundle": exported})
    assert imp.status_code == 200
    assert imp.json()["count"] == 1

    d = tc_b.get(
        "/marketplace/discover",
        params={"resource_type": "compute.qa", "max_amount": 100, "currency": "USD"},
    )
    assert d.json()["winner"]["agent_id"] == agent


def test_create_app_wires_policy_from_rep_min_score():
    app = create_app(
        seed=True,
        auth=False,
        marketplace_enabled=True,
        reputation_min_score=0.7,
    )
    assert app.state.marketplace.policy.min_score == 0.7
    assert app.state.marketplace.policy.match_min_reputation() == 0.7
