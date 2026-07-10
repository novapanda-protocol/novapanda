"""A-group encoding: DELEGATE, PRIV, LITE, S1 sandbox, reconcile, profile gate, polish."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from novapanda.delegate import DelegationRegistry, delegation_signing_bytes
from novapanda.identity import Identity
from novapanda.lite import roundtrip as lite_roundtrip
from novapanda.node import create_app
from novapanda.node.profile_gate import check_profile_honesty
from novapanda.privacy import hash_only_wrap, validate_privacy_tags
from novapanda.settlement import SandboxSettlement


def _signed_delegation(
    issuer: Identity,
    subject: Identity,
    *,
    scope: list[str],
    max_amount: int = 100,
    rails: list[str] | None = None,
    hours: int = 24,
) -> dict:
    exp = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cred = {
        "delegate_version": "0.1",
        "issuer_agent_id": issuer.agent_id,
        "subject_agent_id": subject.agent_id,
        "scope": scope,
        "constraints": {
            "max_amount": max_amount,
            "currency": "USD",
            "period": "P1D",
            "rails_allowlist": rails or ["mock"],
        },
        "expires_at": exp,
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    cred["issuer_sig"] = issuer.sign(delegation_signing_bytes(cred))
    return cred


def test_a1_delegation_register_and_revoke():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    issuer, subject = Identity.generate(), Identity.generate()
    cred = _signed_delegation(issuer, subject, scope=["propose", "escrow"])
    r = tc.post("/node/delegations", json={"credential": cred})
    assert r.status_code == 201
    dlg_id = r.json()["delegation"]["delegation_id"]
    g = tc.get(f"/node/delegations/{dlg_id}")
    assert g.status_code == 200
    lst = tc.get("/node/delegations", params={"subject": subject.agent_id})
    assert len(lst.json()["items"]) == 1
    # revoke without auth_enabled uses issuer mismatch path — use registry directly
    rev = app.state.delegations.revoke(dlg_id, issuer_agent_id=issuer.agent_id)
    assert rev["revoked"] is True
    assert app.state.delegations.get(dlg_id) is None


def test_a1_delegation_amount_limit():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    cred = _signed_delegation(issuer, subject, scope=["escrow"], max_amount=5)
    dlg = reg.register(cred)
    with pytest.raises(ValueError, match="amount_exceeds_max"):
        reg.validate_action(
            dlg["delegation_id"],
            subject_agent_id=subject.agent_id,
            action="escrow",
            amount=10,
            currency="USD",
            rail="mock",
        )


def test_a1_delegation_rail_not_allowed():
    reg = DelegationRegistry()
    issuer, subject = Identity.generate(), Identity.generate()
    cred = _signed_delegation(issuer, subject, scope=["escrow"], rails=["mock"])
    dlg = reg.register(cred)
    with pytest.raises(ValueError, match="rail_not_allowed"):
        reg.validate_action(
            dlg["delegation_id"],
            subject_agent_id=subject.agent_id,
            action="escrow",
            amount=1,
            currency="USD",
            rail="x402",
        )


def test_a2_privacy_hash_only_and_tags():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    r = tc.post("/node/tools/privacy/hash-only", json={"deliverable": {"secret": "x"}})
    assert r.status_code == 200
    assert r.json()["wrapped"]["delivery_exposure"] == "hash_only"
    v = tc.post(
        "/node/tools/privacy/validate-tags",
        json={"tags": {"delivery_exposure": "hash_only", "geo_precision": "region"}},
    )
    assert v.json()["ok"] is True
    pol = tc.get("/node/privacy/policy")
    assert pol.json()["privacy"]["supported"] is True


def test_a3_lite_roundtrip():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    r = tc.post("/node/tools/lite/roundtrip", json={"value": {"z": 1, "a": 2}})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert lite_roundtrip({"k": 1})["equal"] is True


def test_a4_sandbox_settlement_rail():
    s = SandboxSettlement(partner="test-partner")
    h = s.escrow("ex-sb", 3, "USD")
    receipt = s.settle(h)
    assert receipt["rail"] == "fiat-s1-sandbox"
    assert receipt["environment"] == "sandbox"
    assert receipt["licensed"] is False


def test_a4_manifest_sandbox_via_create_app():
    app = create_app(seed=True, auth=False, settlement=SandboxSettlement())
    tc = TestClient(app)
    rails = tc.get("/node/settlement/rails")
    assert rails.json()["rails"][0]["id"] == "fiat-s1-sandbox"
    assert rails.json()["rails"][0]["environment"] == "sandbox"


def test_a5_reconcile_export_json_and_csv():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    tc.post("/node/settle/simulate", json={"amount": 1})
    j = tc.get("/admin/reconcile/export")
    assert j.status_code == 200
    assert "meta" in j.json()
    c = tc.get("/admin/reconcile/export", params={"format": "csv"})
    assert c.status_code == 200
    assert "exchange_id" in c.text


def test_a6_profile_gate_claim_xfer_blocked():
    errs = check_profile_honesty(["NP-MIN", "NP-CLAIM-XFER"], claim_mock_only=True)
    assert errs
    ok = check_profile_honesty(["NP-MIN", "NP-DELEGATE"], claim_mock_only=True)
    assert not ok


def test_a6_profile_gate_endpoint():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    r = tc.get("/node/profile-gate")
    assert r.status_code == 200
    assert "NP-DELEGATE" in r.json()["profiles"]
    assert not r.json()["warnings"]


def test_a7_manifest_profiles_and_polish():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    m = tc.get("/.well-known/novapanda.json")
    assert m.status_code == 200
    body = m.json()
    assert "NP-DELEGATE" in body["profiles"]
    assert "NP-PRIV" in body["profiles"]
    assert body.get("delegation", {}).get("supported") is True
    home = tc.get("/")
    assert "NP-DELEGATE" in home.text
    assert "Claim=mock only" in home.text


def test_settle_simulate_still_works_mock():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    r = tc.post("/node/settle/simulate", json={"amount": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mock"] is True
