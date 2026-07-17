"""市场 Facade + Sink 接线 + 多链钱包抽象测试。"""

from __future__ import annotations

from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.marketplace import (
    DefaultMarketplaceFacade,
    DynamicScoreEngine,
    InMemoryRiskSignalStore,
    InMemoryServiceRegistry,
    InMemoryVolumeIndex,
    MarketplaceTerminalSink,
    MatchQuery,
    PriceQuote,
    ServiceListing,
    SlaOffer,
    WeightedMatchRouter,
)
from novapanda.reputation import ReputationLog
from novapanda.settlement import MockSettlement
from novapanda.verifier import SchemaVerifier
from novapanda.wallet import (
    AssetRef,
    ChainRef,
    DefaultAgentWalletManager,
    FiatPaymentRequest,
    FiatSettlementRequest,
    InMemoryChainAdapter,
    StubFiatComplianceGateway,
    TransferRequest,
    UsdcPaymaster,
)
from tests.helpers import dual_contract_engine

RULE = {
    "schema": {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string", "minLength": 1}},
        "additionalProperties": False,
    }
}


def _listing(agent_id: str, listing_id: str, price: int, ms: int, tags=()) -> ServiceListing:
    return ServiceListing(
        listing_id=listing_id,
        agent_id=agent_id,
        resource_type="compute.qa",
        capability_tags=tuple(tags),
        sla=SlaOffer(max_response_ms=ms),
        price=PriceQuote(amount=price, currency="USD"),
        endpoints={"exchange": "http://x"},
        content_hash="sha256:" + listing_id.encode().hex(),
    )


def test_facade_discovers_and_routes():
    a = Identity.generate().agent_id
    b = Identity.generate().agent_id
    reg = InMemoryServiceRegistry()
    reg.register(_listing(a, "L-a", 40, 100, ("fast",)))
    reg.register(_listing(b, "L-b", 80, 800, ()))

    log = ReputationLog(Identity.generate())
    engine = DynamicScoreEngine(reputation_log=log, volume=InMemoryVolumeIndex())
    facade = DefaultMarketplaceFacade.build_default(reg, engine)

    decision = facade.find_providers(
        MatchQuery(
            resource_type="compute.qa",
            quantity=1,
            max_price=PriceQuote(amount=100, currency="USD"),
            max_response_ms=1000,
            preferred_tags=("fast",),
        )
    )
    assert decision.winner is not None
    assert decision.winner.listing.listing_id == "L-a"


def test_terminal_sink_records_volume_and_invalidates_score():
    node = Identity.generate()
    client, provider = Identity.generate(), Identity.generate()
    log = ReputationLog(node)
    vol = InMemoryVolumeIndex()
    risk = InMemoryRiskSignalStore()
    score = DynamicScoreEngine(reputation_log=log, volume=vol, risk=risk)
    sink = MarketplaceTerminalSink(
        volume=vol, risk=risk, score_engine=score, write_reputation=False
    )

    eng = ExchangeEngine(
        MockSettlement(),
        verifier=SchemaVerifier(),
        reputation=log,
        terminal_observers=[sink],
    )
    ex = eng.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="compute.qa",
        quantity=1,
        rule_id="R1",
        price={"amount": 250, "currency": "USD"},
        idempotency_key="sink-1",
    )
    dual_contract_engine(eng, ex.exchange_id, client, provider)
    eng.escrow(ex.exchange_id, amount=250, currency="USD")
    eng.deliver(ex.exchange_id, provider, {"answer": "ok"})
    eng.verify(ex.exchange_id, rule=RULE)
    eng.confirm(ex.exchange_id, client)

    assert vol.notional(ex.exchange_id) == 250
    view = score.view(provider.agent_id)
    assert view.settled_count >= 1
    assert view.score == 1.0


def test_wallet_evm_and_solana_unified_transfer():
    mgr = DefaultAgentWalletManager()
    evm = InMemoryChainAdapter(chain=ChainRef.evm(1), native_symbol="ETH")
    sol = InMemoryChainAdapter(chain=ChainRef.solana("mainnet"), native_symbol="SOL")
    mgr.register_adapter(evm)
    mgr.register_adapter(sol)

    agent = Identity.generate().agent_id
    acct_e = mgr.ensure_account(agent, ChainRef.evm(1))
    acct_s = mgr.ensure_account(agent, ChainRef.solana("mainnet"))

    eth = AssetRef(chain=ChainRef.evm(1), symbol="ETH", decimals=18)
    sol_native = AssetRef(chain=ChainRef.solana("mainnet"), symbol="SOL", decimals=9)
    evm.credit(acct_e.address, eth, 1_000_000)
    sol.credit(acct_s.address, sol_native, 5_000)

    rx = acct_e.transfer(
        TransferRequest(asset=eth, to_address="0x" + "ab" * 20, amount=100)
    )
    assert rx.status == "confirmed"
    assert acct_e.balance(eth).amount == 999_900

    rx2 = acct_s.transfer(
        TransferRequest(asset=sol_native, to_address="solRecipient", amount=50)
    )
    assert rx2.status == "confirmed"
    assert acct_s.balance(sol_native).amount == 4_950


def test_paymaster_sponsors_gas_with_usdc():
    chain = ChainRef.evm(11155111)
    ledger = InMemoryChainAdapter(chain=chain, native_symbol="ETH")
    mgr = DefaultAgentWalletManager()
    mgr.register_adapter(ledger)
    agent = Identity.generate().agent_id
    acct = mgr.ensure_account(agent, chain)

    usdc = AssetRef(
        chain=chain, symbol="USDC", decimals=6, token_address="0xusdc"
    )
    eth = AssetRef(chain=chain, symbol="ETH", decimals=18)
    ledger.credit(acct.address, usdc, 1_000_000)
    ledger.credit(acct.address, eth, 500)

    pm = UsdcPaymaster(ledger=ledger, token_per_gas_unit=2)
    rx = acct.transfer_with_paymaster(
        TransferRequest(asset=eth, to_address="0x" + "cd" * 20, amount=10),
        fee_token=usdc,
        paymaster=pm,
    )
    assert "paymaster" in rx.raw
    # gas 21000 * 2 = 42000 USDC units deducted
    assert acct.balance(usdc).amount == 1_000_000 - 42_000
    assert acct.balance(eth).amount == 490


def test_fiat_compliance_stubs_are_unlicensed():
    gw = StubFiatComplianceGateway()
    chain = ChainRef.evm(1)
    usdc = AssetRef(chain=chain, symbol="USDC", decimals=6, token_address="0x1")
    pay = gw.pay_with_fiat(
        FiatPaymentRequest(
            amount_minor=1000,
            currency="USD",
            target_asset=usdc,
            agent_id="ed25519:x",
            idempotency_key="k1",
        )
    )
    settle = gw.settle_to_fiat(
        FiatSettlementRequest(
            amount=100,
            asset=usdc,
            agent_id="ed25519:x",
            bank_ref="bank-1",
            idempotency_key="k2",
        )
    )
    assert pay.licensed is False
    assert settle.licensed is False
    assert pay.operation == "pay_with_fiat"
    assert settle.operation == "settle_to_fiat"


def test_wallet_backed_settlement_escrow_settle():
    from novapanda.wallet import AssetRef, WalletBackedSettlement

    client, provider = Identity.generate(), Identity.generate()
    settle = WalletBackedSettlement()
    settle.seed_client(client.agent_id, 500)
    settle.bind_parties("ex-w1", client=client.agent_id, provider=provider.agent_id)
    handle = settle.escrow("ex-w1", amount=100, currency="USD")
    assert settle.status(handle) == "held"
    rx = settle.settle(handle)
    assert rx["status"] == "settled"
    assert settle.settle(handle)["status"] == "settled"
    acct_p = settle.manager.get_account(provider.agent_id, settle.chain)
    assert acct_p is not None
    bal = acct_p.balance(AssetRef(chain=settle.chain, symbol="USD", decimals=2))
    assert bal.amount == 100
