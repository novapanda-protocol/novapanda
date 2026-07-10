"""C11 — Claim mock / NP-CLAIM-XFER production vectors."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.node import create_app, create_app_from_config
from novapanda.node.claim_mock import ClaimMockRegistry
from novapanda.node.claim_registry import ClaimRegistry, assignment_bytes
from novapanda.config import NodeConfig


def test_c11_issue_without_vdc_anchor_rejected():
    reg = ClaimMockRegistry()
    with pytest.raises(ValueError, match="vdc_anchor"):
        reg.issue(vdc_id="", amount=1, currency="USD", holder="h1")
    with pytest.raises(ValueError, match="vdc_anchor"):
        reg.issue(vdc_id="   ", amount=1, currency="USD", holder="h1")


def test_c11_double_spend_after_capture():
    reg = ClaimMockRegistry()
    c = reg.issue(vdc_id="vdc-anchored", amount=5, currency="USD", holder="h1")
    reg.reserve(c.claim_id, for_exchange_id="ex-a")
    reg.capture(c.claim_id)
    assert reg.get(c.claim_id).status == "spent"
    with pytest.raises(ValueError, match="not_open"):
        reg.reserve(c.claim_id, for_exchange_id="ex-b")


def test_c11_api_rejects_empty_vdc():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    r = tc.post("/node/claims/issue", json={"vdc_id": "", "amount": 1})
    assert r.status_code == 400


def test_c11_production_issue_requires_agent_holder():
    reg = ClaimRegistry()
    holder = Identity.generate()
    c = reg.issue(vdc_id="vdc-1", amount=10, currency="USD", holder=holder.agent_id, rail="mock")
    assert c.claim_id.startswith("claim_")
    with pytest.raises(ValueError, match="holder_must_be_agent_id"):
        reg.issue(vdc_id="vdc-2", amount=1, currency="USD", holder="demo")


def test_c11_production_assignment_signed():
    reg = ClaimRegistry()
    h1 = Identity.generate()
    h2 = Identity.generate()
    c = reg.issue(vdc_id="vdc-1", amount=10, currency="USD", holder=h1.agent_id)
    at = "2026-07-09T12:00:00Z"
    nonce = "n-1"
    sig = h1.sign(
        assignment_bytes(claim_id=c.claim_id, to_agent_id=h2.agent_id, nonce=nonce, at=at)
    )
    updated = reg.assign(c.claim_id, h2.agent_id, signature=sig, nonce=nonce, at=at)
    assert updated.holder_agent_id == h2.agent_id
    assert updated.lineage[0]["to"] == h2.agent_id


def test_c11_production_double_redeem_blocked():
    reg = ClaimRegistry()
    holder = Identity.generate()
    c = reg.issue(vdc_id="vdc-1", amount=5, currency="USD", holder=holder.agent_id)
    reg.redeem(c.claim_id)
    with pytest.raises(ValueError, match="not_open"):
        reg.redeem(c.claim_id)


def test_c11_production_api_manifest(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_AUTH", "0")
    monkeypatch.setenv("NOVAPANDA_CLAIM_MODE", "production")
    app = create_app_from_config(NodeConfig.from_env())
    tc = TestClient(app)
    holder = Identity.generate()
    r = tc.post(
        "/node/claims/issue",
        json={"vdc_id": "vdc-api", "amount": 1, "currency": "USD", "holder": holder.agent_id},
    )
    assert r.status_code == 201
    assert r.json()["claim"]["mock"] is False
    info = tc.get("/.well-known/novapanda.json").json()
    assert "NP-CLAIM-XFER" in info.get("profiles", [])
