"""Stripe PaymentIntent 网关向量。"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from novapanda.config import NodeConfig
from novapanda.exchange import ExchangeEngine
from novapanda.fiat_gateway import make_fiat_gateway
from novapanda.identity import Identity
from novapanda.rail_registry import build_rail_registry
from novapanda.settlement import S1HttpSandboxSettlement
from novapanda.stripe_fake import create_stripe_fake_app
from novapanda.stripe_gateway import StripeGateway
from tests.helpers import dual_contract_engine


def test_stripe_gateway_authorize_capture_void():
    fake = TestClient(create_stripe_fake_app())
    gw = StripeGateway("http://testserver/v1", http=fake, api_key="sk_test_fake")
    ref = gw.authorize("ex-stripe-1", 2500, "USD")
    assert ref.startswith("pi_fake_")
    cap = gw.capture(ref)
    assert cap["amount"] == 2500
    assert cap["currency"] == "USD"

    ref2 = gw.authorize("ex-stripe-2", 100, "USD")
    voided = gw.void(ref2)
    assert voided["amount"] == 100


def test_stripe_provider_full_exchange():
    fake = TestClient(create_stripe_fake_app())
    os.environ["NOVAPANDA_FIAT_PROVIDER"] = "stripe"
    os.environ["NOVAPANDA_SANDBOX_PARTNER"] = "stripe-sandbox"
    try:
        gw = make_fiat_gateway(
            base_url="http://testserver/v1",
            api_key="sk_test_fake",
            http=fake,
            provider="stripe",
        )
        cfg = NodeConfig(
            settlement="sandbox",
            settlement_rails=["sandbox", "mock"],
            default_rail="sandbox",
            fiat_gateway_url="http://testserver/v1",
            fiat_api_key="sk_test_fake",
        )
        reg = build_rail_registry(cfg)
        adapter = reg.get("sandbox")
        assert isinstance(adapter, S1HttpSandboxSettlement)
        adapter.gateway = gw  # type: ignore[attr-defined]

        engine = ExchangeEngine(reg.active_adapter, rail_registry=reg)
        client, provider = Identity.generate(), Identity.generate()
        ex = engine.propose(
            client=client.agent_id,
            provider=provider.agent_id,
            resource_type="data.extraction.structured",
            quantity=1,
            rule_id="R-extract-invoice-v1",
            price={"amount": 100, "currency": "USD"},
            idempotency_key="stripe-s1",
            settlement_terms={"preferred_rails": ["fiat-s1-sandbox"], "currency": "USD"},
        )
        dual_contract_engine(engine, ex.exchange_id, client, provider)
        engine.escrow(ex.exchange_id, amount=100, currency="USD")
        engine.deliver(
            ex.exchange_id, provider, {"invoice_no": "ST", "total": "1.00", "currency": "USD"}
        )
        engine.verify(ex.exchange_id)
        settled = engine.confirm(ex.exchange_id, client)
        assert settled.state == "SETTLED"
        assert settled.settlement_receipt["partner"] == "stripe-sandbox"
        assert settled.settlement_receipt["environment"] == "sandbox"
    finally:
        os.environ.pop("NOVAPANDA_FIAT_PROVIDER", None)
        os.environ.pop("NOVAPANDA_SANDBOX_PARTNER", None)
