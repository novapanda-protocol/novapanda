"""P0/P1：市场 feature flag · Sink 幂等 · HTTP · Manifest 投影。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.manifest import build_agent_manifest
from novapanda.marketplace import (
    InMemoryVolumeIndex,
    MarketplaceTerminalSink,
    sync_manifest_to_registry,
)
from novapanda.marketplace.registry import InMemoryServiceRegistry
from novapanda.marketplace.types import ExchangeTerminalSnapshot
from novapanda.node import create_app


def test_marketplace_disabled_by_default():
    app = create_app(seed=True, auth=False)
    assert app.state.marketplace_enabled is False
    assert "NP-REP" not in app.state.node_profiles
    tc = TestClient(app)
    r = tc.get(
        "/marketplace/discover",
        params={"resource_type": "x", "max_amount": 100},
    )
    assert r.status_code == 503
    assert r.json()["code"] == "E_MARKETPLACE_DISABLED"


def test_marketplace_http_listing_and_discover():
    app = create_app(seed=True, auth=False, marketplace_enabled=True)
    assert app.state.marketplace_enabled is True
    assert "NP-REP" in app.state.node_profiles
    tc = TestClient(app)

    agent = Identity.generate().agent_id
    r = tc.post(
        "/marketplace/listings",
        json={
            "listing_id": "L-http-1",
            "agent_id": agent,
            "resource_type": "compute.qa",
            "capability_tags": ["fast"],
            "max_response_ms": 200,
            "price_amount": 40,
            "price_currency": "USD",
            "exchange_endpoint": "http://testserver",
            "rule_id_hint": "R1",
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    d = tc.get(
        "/marketplace/discover",
        params={
            "resource_type": "compute.qa",
            "max_amount": 100,
            "currency": "USD",
            "max_response_ms": 1000,
            "preferred_tags": "fast",
        },
    )
    assert d.status_code == 200
    body = d.json()
    assert body["winner"]["listing_id"] == "L-http-1"
    assert body["profile"] == "NP-REP"

    g = tc.get("/marketplace/listings/L-http-1")
    assert g.status_code == 200
    assert g.json()["agent_id"] == agent

    m = tc.get("/.well-known/novapanda.json")
    assert m.json()["features"]["marketplace"] is True


def test_sink_idempotent_same_exchange():
    vol = InMemoryVolumeIndex()
    sink = MarketplaceTerminalSink(volume=vol)
    snap = ExchangeTerminalSnapshot(
        exchange_id="ex-idem-1",
        state="SETTLED",
        client="c",
        provider="p",
        resource_type="x",
        quantity=1,
        vdc_id=None,
        price_amount=99,
        price_currency="USD",
        outcome_hint="settled",
    )
    sink.on_terminal(snap)
    sink.on_terminal(snap)
    assert vol.notional("ex-idem-1") == 99
    assert len(sink._seen_exchange_ids) == 1


def test_manifest_sync_to_registry_and_http():
    provider = Identity.generate()
    manifest = build_agent_manifest(
        provider,
        capabilities=[
            {
                "resource_type": "data.extraction.structured",
                "rules": ["R-extract-invoice-v1"],
                "price": {"amount": 100, "currency": "USD"},
                "tags": ["invoice"],
                "sla_ms": 300,
            }
        ],
        exchange_endpoint="http://testserver/exchanges",
    )
    reg = InMemoryServiceRegistry()
    listings = sync_manifest_to_registry(reg, manifest)
    assert len(listings) == 1
    assert listings[0].agent_id == provider.agent_id
    assert listings[0].price.amount == 100

    app = create_app(seed=True, auth=False, marketplace_enabled=True)
    tc = TestClient(app)
    r = tc.post(
        "/marketplace/listings/from-manifest",
        json={"manifest": manifest},
    )
    assert r.status_code == 200
    assert r.json()["count"] == 1

    d = tc.get(
        "/marketplace/discover",
        params={
            "resource_type": "data.extraction.structured",
            "max_amount": 200,
            "currency": "USD",
            "max_response_ms": 10_000,
        },
    )
    assert d.status_code == 200
    assert d.json()["winner"]["agent_id"] == provider.agent_id


def test_config_marketplace_env(monkeypatch):
    from novapanda.config import NodeConfig

    monkeypatch.setenv("NOVAPANDA_MARKETPLACE", "1")
    cfg = NodeConfig.from_env()
    assert cfg.marketplace is True
