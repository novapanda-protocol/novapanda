"""NP-TRACE conformance vectors — reference node traceparent passthrough."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import reverify
from novapanda.sdk import NovaPandaClient
from novapanda.trace import parse_traceparent
from tests.helpers import dual_contract_sdk

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}


@pytest.fixture
def clients():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    return client, provider, tc, app


def _propose(tc: TestClient, client: NovaPandaClient, provider: NovaPandaClient, idem: str, **headers):
    body = {
        "client": client.agent_id,
        "provider": provider.agent_id,
        "resource_type": RESOURCE,
        "quantity": 1,
        "rule_id": RULE_ID,
        "price": PRICE,
        "idempotency_key": idem,
    }
    return tc.post("/exchanges", json=body, headers=headers)


def test_t_trace_01_propose_without_header_generates_trace(clients):
    client, provider, tc, _ = clients
    r = _propose(tc, client, provider, "t-trace-01")
    assert r.status_code == 201
    trace = r.json()["extensions"]["trace"]
    assert parse_traceparent(trace["traceparent"])


def test_t_trace_02_inbound_traceparent_preserves_trace_id(clients):
    client, provider, tc, _ = clients
    inbound = "00-a1b2c3d4e5f6789012345678abcdef01-00f067aa0ba902b7-01"
    r = _propose(tc, client, provider, "t-trace-02", traceparent=inbound)
    assert r.status_code == 201
    trace = r.json()["extensions"]["trace"]
    parsed = parse_traceparent(trace["traceparent"])
    assert parsed is not None
    assert parsed[0] == "a1b2c3d4e5f6789012345678abcdef01"
    assert trace["traceparent"] != inbound


def test_t_trace_03_body_correlation_id(clients):
    client, provider, tc, _ = clients
    r = tc.post(
        "/exchanges",
        json={
            "client": client.agent_id,
            "provider": provider.agent_id,
            "resource_type": RESOURCE,
            "quantity": 1,
            "rule_id": RULE_ID,
            "price": PRICE,
            "idempotency_key": "t-trace-03",
            "correlation_id": "corr-dd-001",
        },
    )
    assert r.status_code == 201
    trace = r.json()["extensions"]["trace"]
    assert trace["correlation_id"] == "corr-dd-001"
    assert "np=corr:corr-dd-001" in (trace.get("tracestate") or "")


def test_t_trace_04_audit_records_correlation(clients):
    client, provider, tc, app = clients
    tc.post(
        "/exchanges",
        json={
            "client": client.agent_id,
            "provider": provider.agent_id,
            "resource_type": RESOURCE,
            "quantity": 1,
            "rule_id": RULE_ID,
            "price": PRICE,
            "idempotency_key": "t-trace-04",
            "correlation_id": "corr-audit",
        },
        headers={"tracestate": "np=corr:ignored-when-body"},
    )
    entry = next(i for i in app.state.audit.list() if i["action"] == "exchange.propose")
    assert entry["correlation_id"] == "corr-audit"
    assert "traceparent" in entry


def test_t_trace_05_disabled_by_env(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_TRACE", "0")
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    r = _propose(tc, client, provider, "t-trace-05")
    assert r.status_code == 201
    assert "extensions" not in r.json()


def test_t_trace_06_reverify_unaffected_by_trace(clients):
    client, provider, tc, _ = clients
    ex = client.propose(
        provider=provider.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price=PRICE,
        idempotency_key="t-trace-06",
    )
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, deliverable=GOOD)
    client.verify(eid)
    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"]) is True
    assert all(v is not False for v in reverify(settled["vdc"], GOOD).values())
