"""零号节点 Operator / Steward 门户路由冒烟。"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from novapanda.canonical import canonical_bytes
from novapanda.identity import Identity
from novapanda.node import create_app


@pytest.fixture
def portal_client():
    os.environ["NOVAPANDA_STEWARD_TOKEN"] = "steward-test-token"
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    yield tc, app
    os.environ.pop("NOVAPANDA_STEWARD_TOKEN", None)


def _operator_session(tc: TestClient) -> tuple[str, Identity]:
    reg = tc.post(
        "/operator/register",
        json={
            "email": "portal@test.local",
            "password": "secret123",
            "display_name": "portal",
            "accept_terms": True,
        },
    )
    otp = reg.json()["otp_dev"]
    tc.post("/operator/verify", json={"email": "portal@test.local", "otp": otp})
    login = tc.post(
        "/operator/login",
        json={"email": "portal@test.local", "password": "secret123"},
    )
    token = login.json()["session_token"]
    agent = Identity.generate()
    payload = tc.get(
        f"/operator/agents/claim-payload?agent_id={agent.agent_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["payload"]
    sig = agent.sign(canonical_bytes(payload))
    tc.post(
        "/operator/agents/bind",
        json={
            "agent_id": agent.agent_id,
            "signature": sig,
            "issued_at": payload["issued_at"],
            "label": "p",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, agent


def test_operator_portal_pages(portal_client):
    tc, _app = portal_client
    token, _agent = _operator_session(tc)
    headers = {"Authorization": f"Bearer {token}"}
    for path, needle in [
        ("/operator/dashboard", "Operator 概览"),
        ("/operator/agents-ui", "绑定 Agent"),
        ("/operator/exchanges", "我的交换"),
        ("/operator/settings", "账户设置"),
        ("/operator/help", "Litmus"),
        ("/operator/bundles", "Bundle"),
        ("/operator/reconcile", "对账"),
        ("/operator/disputes-ui", "争议"),
    ]:
        r = tc.get(path, headers=headers)
        assert r.status_code == 200, path
        assert needle in r.text, path

    del_req = tc.post("/operator/settings/deletion-request", headers=headers)
    assert del_req.status_code == 200
    assert del_req.json()["operator"]["deletion_requested_at"]
    del_cancel = tc.post("/operator/settings/deletion-cancel", headers=headers)
    assert del_cancel.status_code == 200
    assert del_cancel.json()["operator"]["deletion_requested_at"] is None


def test_steward_page(portal_client):
    tc, _app = portal_client
    r = tc.get("/steward")
    assert r.status_code == 200
    assert "Steward" in r.text


def test_operator_unbind(portal_client):
    tc, _app = portal_client
    token, agent = _operator_session(tc)
    headers = {"Authorization": f"Bearer {token}"}
    unbind = tc.post(
        "/operator/agents/unbind",
        json={"agent_id": agent.agent_id},
        headers=headers,
    )
    assert unbind.status_code == 200
    listed = tc.get("/operator/agents", headers=headers)
    assert listed.json()["items"] == []
