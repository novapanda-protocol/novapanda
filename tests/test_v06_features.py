"""v0.6 design encoding: disputes, certifications, operator portal, composer, reconcile."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from novapanda import state_machine as sm
from novapanda.canonical import canonical_bytes
from novapanda.composer import Composer, LegResult
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.node.dispute_tickets import DisputeTicketRegistry
from novapanda.node.certifications import CertificationRegistry
from novapanda.node.reconcile import build_reconcile_export, export_claim_csv
from novapanda.sdk import NovaPandaClient
from tests.helpers import dual_contract_sdk


@pytest.fixture
def app_client():
    os.environ["NOVAPANDA_STEWARD_TOKEN"] = "steward-test-token"
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    yield tc, app
    os.environ.pop("NOVAPANDA_STEWARD_TOKEN", None)


def settled_vdc_id(client: NovaPandaClient, eid: str) -> str:
    detail = client.get_exchange(eid)
    return detail["vdc"]["vdc_id"]


def _settled_exchange(tc: TestClient) -> tuple[str, str]:
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    good = {"invoice_no": "V06-1", "total": "10.00", "currency": "USD"}
    ex = client.propose(
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 10, "currency": "USD"},
        idempotency_key="v06-settle",
    )
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=10, currency="USD")
    provider.deliver(eid, good)
    client.verify(eid)
    client.confirm(eid)
    return eid, settled_vdc_id(client, eid)


def _operator_session(tc: TestClient) -> str:
    email = "dispute-op@test.local"
    reg = tc.post(
        "/operator/register",
        json={
            "email": email,
            "password": "secret123",
            "display_name": "dispute",
            "accept_terms": True,
        },
    )
    otp = reg.json()["otp_dev"]
    tc.post("/operator/verify", json={"email": email, "otp": otp})
    login = tc.post("/operator/login", json={"email": email, "password": "secret123"})
    return login.json()["session_token"]


def test_dispute_opens_ticket(app_client):
    tc, _app = app_client
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    buyer = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    good = {"invoice_no": "D-1", "total": "5.00", "currency": "USD"}
    ex2 = buyer.propose(
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 5, "currency": "USD"},
        idempotency_key="v06-dispute",
    )
    eid2 = ex2["exchange_id"]
    dual_contract_sdk(buyer, provider, eid2)
    buyer.escrow(eid2, amount=5, currency="USD")
    provider.deliver(eid2, good)
    buyer.verify(eid2)
    r = tc.post(f"/exchanges/{eid2}/dispute", json={"reason": "质疑验收"})
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == sm.DISPUTED
    assert body["dispute_ticket"]["ticket_id"].startswith("DISP-")
    token = _operator_session(tc)
    tickets = tc.get(
        "/operator/disputes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert tickets.status_code == 200
    assert len(tickets.json()["items"]) >= 1


def test_claim_get_and_reconcile_claim_rows(app_client):
    tc, app = app_client
    eid, vdc_id = _settled_exchange(tc)
    issue = tc.post(
        "/node/claims/issue",
        json={"vdc_id": vdc_id, "amount": 10, "currency": "USD", "holder": "demo"},
    )
    assert issue.status_code == 201
    cid = issue.json()["claim"]["claim_id"]
    got = tc.get(f"/node/claims/{cid}")
    assert got.status_code == 200
    package = build_reconcile_export(
        engine=app.state.engine,
        settlement=app.state.settlement,
        node_id=app.state.node_id,
        claims=app.state.claims,
    )
    assert any(r.get("claim_id") == cid for r in package.get("claim_rows", []))
    csv_text = export_claim_csv(package)
    assert "claim_id" in csv_text and cid in csv_text


def test_operator_bind_and_claims_page(app_client):
    tc, _app = app_client
    reg = tc.post(
        "/operator/register",
        json={
            "email": "v06@test.local",
            "password": "secret123",
            "display_name": "v06",
            "accept_terms": True,
        },
    )
    otp = reg.json()["otp_dev"]
    tc.post("/operator/verify", json={"email": "v06@test.local", "otp": otp})
    login = tc.post(
        "/operator/login",
        json={"email": "v06@test.local", "password": "secret123"},
    )
    token = login.json()["session_token"]
    agent = Identity.generate()
    payload_resp = tc.get(
        f"/operator/agents/claim-payload?agent_id={agent.agent_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert payload_resp.status_code == 200
    payload = payload_resp.json()["payload"]
    signature = agent.sign(canonical_bytes(payload))
    bind = tc.post(
        "/operator/agents/bind",
        json={
            "agent_id": agent.agent_id,
            "label": "primary",
            "signature": signature,
            "issued_at": payload["issued_at"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bind.status_code == 201
    page = tc.get(
        "/operator/claims",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page.status_code == 200
    assert "Claims" in page.text


def test_steward_certification_api(app_client):
    tc, _app = app_client
    headers = {"X-Steward-Token": "steward-test-token"}
    grant = tc.post(
        "/steward/certifications",
        headers=headers,
        json={
            "level": "L1",
            "applicant": {"legal_name": "Acme", "contact": "a@acme.test", "repo_url": "https://example.com"},
            "implementation": {"language": "python", "version": "0.0.1", "commit": "abc"},
            "profiles": ["NP-MIN"],
            "cases_passed": ["C1", "C2"],
        },
    )
    assert grant.status_code == 201
    cert_id = grant.json()["certification"]["cert_id"]
    assert cert_id.startswith("NP-COMP-")
    pub = tc.get(f"/public/certifications/{cert_id}")
    assert pub.status_code == 200
    assert pub.json()["certification"]["status"] == "active"
    patch = tc.patch(
        f"/steward/certifications/{cert_id}",
        headers=headers,
        json={"status": "suspended"},
    )
    assert patch.status_code == 200
    assert patch.json()["certification"]["status"] == "suspended"


def test_composer_abort_on_failure():
    bundle = {
        "bundle_version": "0.1",
        "goal_id": "g1",
        "correlation_id": "c1",
        "exchange_ids": ["leg-a", "leg-b"],
        "depends_on": {"leg-b": ["leg-a"]},
        "success_rule": "all_settled",
    }
    comp = Composer(on_leg_failure="abort_rest")

    def run_fn(leg_id: str, _bundle: dict) -> LegResult:
        if leg_id == "leg-a":
            return LegResult(leg_id=leg_id, exchange_id="ex-a", vdc_id="vdc-a", state="SETTLED")
        return LegResult(leg_id=leg_id, state="failed", error="simulated")

    run = comp.run_all(bundle, run_fn=run_fn)
    assert run.failed_legs == ["leg-b"]
    assert comp.finalize(bundle, run)["bundle_ready"] is False
    exported = comp.export(run)
    assert b"leg-b" in exported


def test_dispute_ticket_registry_idempotent():
    reg = DisputeTicketRegistry()
    t1 = reg.open_for_exchange(
        exchange_id="ex-1",
        reason="r",
        dispute_info={},
        client="ed25519:a",
        provider="ed25519:b",
    )
    t2 = reg.open_for_exchange(
        exchange_id="ex-1",
        reason="r2",
        dispute_info={},
        client="ed25519:a",
        provider="ed25519:b",
    )
    assert t1.ticket_id == t2.ticket_id


def test_certification_registry_grant():
    reg = CertificationRegistry()
    rec = reg.grant(
        level="L2",
        applicant={"legal_name": "X"},
        implementation={"language": "go"},
        profiles=["NP-BUNDLE"],
        cases_passed=["C8"],
    )
    assert rec.cert_id.startswith("NP-COMP-")
    assert reg.get(rec.cert_id) is not None
