"""T01–T09 console / body surface."""

from fastapi.testclient import TestClient

from novapanda.node import create_app


def test_verify_and_me_tabs_present():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    home = tc.get("/")
    assert home.status_code == 200
    assert 'data-tab="verify"' in home.text
    assert "panel-verify" in home.text
    assert 'data-tab="me"' in home.text
    assert "Trial 硬边界" in home.text
    assert "智能开放交割协议" in home.text
    assert "/static/brand/novapanda-intelligent-open-delivery-protocol-poster-zh.png" in home.text


def test_brand_static_assets():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    path = "/static/brand/novapanda-intelligent-open-delivery-protocol-poster-zh.png"
    r = tc.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_canonical_and_bundle_tools():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    c = tc.post("/node/tools/canonical", json={"value": {"b": 1, "a": 2}})
    assert c.status_code == 200
    assert c.json()["sha256"].startswith("sha256:")
    b = tc.post(
        "/node/tools/bundle/validate",
        json={
            "bundle": {
                "bundle_version": "0.1",
                "goal_id": "g",
                "correlation_id": "c",
                "exchange_ids": ["a"],
                "success_rule": "all_settled",
            }
        },
    )
    assert b.status_code == 200
    assert b.json()["ok"] is True


def test_claim_mock_requires_vdc_and_lifecycle():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    bad = tc.post("/node/claims/issue", json={"vdc_id": "", "amount": 1})
    assert bad.status_code == 400
    ok = tc.post(
        "/node/claims/issue",
        json={"vdc_id": "vdc-1", "amount": 3, "holder": "h1"},
    )
    assert ok.status_code == 201
    cid = ok.json()["claim"]["claim_id"]
    r = tc.post("/node/claims/reserve", json={"claim_id": cid, "exchange_id": "ex-1"})
    assert r.json()["claim"]["status"] == "reserved"
    cap = tc.post("/node/claims/capture", json={"claim_id": cid})
    assert cap.json()["claim"]["status"] == "spent"


def test_settle_simulate_idempotent():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    r = tc.post("/node/settle/simulate", json={"amount": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["first"]["rail"] == "mock"
    assert body["idempotent_second"]["status"] == "settled"


def test_quota_on_propose_and_notify(monkeypatch):
    app = create_app(seed=True, auth=False)
    app.state.operators.anonymous_propose_per_day = 2
    tc = TestClient(app)
    # minimal propose needs ontology — use seeded types
    types = tc.get("/registry/types").json()
    rules = tc.get("/registry/rules").json()
    assert types and rules
    rtype = types[0]["type_id"] if isinstance(types[0], dict) else types[0]
    rid = rules[0]["rule_id"] if isinstance(rules[0], dict) else rules[0]
    from novapanda.identity import Identity

    c, p = Identity.generate(), Identity.generate()
    payload = {
        "client": c.agent_id,
        "provider": p.agent_id,
        "resource_type": rtype,
        "quantity": 1,
        "rule_id": rid,
        "price": {"amount": 1, "currency": "USD"},
        "idempotency_key": "q1",
    }
    assert tc.post("/exchanges", json={**payload, "idempotency_key": "q1"}).status_code == 201
    assert tc.post("/exchanges", json={**payload, "idempotency_key": "q2"}).status_code == 201
    r3 = tc.post("/exchanges", json={**payload, "idempotency_key": "q3"})
    assert r3.status_code == 429
    n = tc.get("/node/notify")
    assert n.status_code == 200
    assert any(i["kind"] == "quota" for i in n.json()["items"])


def test_admin_audit_alerts_reset():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    assert tc.get("/admin/audit").status_code == 200
    assert tc.get("/admin/alerts").status_code == 200
    r = tc.post("/admin/baseline-reset")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_operator_me_includes_quota():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    reg = tc.post(
        "/operator/register",
        json={
            "email": "t09@example.com",
            "display_name": "T",
            "password": "secret-pass",
            "accept_terms": True,
        },
    )
    otp = reg.json()["otp_dev"]
    tc.post("/operator/verify", json={"email": "t09@example.com", "otp": otp})
    login = tc.post(
        "/operator/login",
        json={"email": "t09@example.com", "password": "secret-pass"},
    )
    token = login.json()["session_token"]
    me = tc.get("/operator/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert "quota" in me.json()


def test_console_exchange_detail_trace():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    types = tc.get("/registry/types").json()
    rules = tc.get("/registry/rules").json()
    rtype = types[0]["type_id"] if isinstance(types[0], dict) else types[0]
    rid = rules[0]["rule_id"] if isinstance(rules[0], dict) else rules[0]
    from novapanda.identity import Identity

    client, provider = Identity.generate(), Identity.generate()
    r = tc.post(
        "/exchanges",
        json={
            "client": client.agent_id,
            "provider": provider.agent_id,
            "resource_type": rtype,
            "quantity": 1,
            "rule_id": rid,
            "price": {"amount": 1, "currency": "USD"},
            "idempotency_key": "trace-console",
            "correlation_id": "corr-console-01",
        },
        headers={"traceparent": "00-a1b2c3d4e5f6789012345678abcdef01-00f067aa0ba902b7-01"},
    )
    assert r.status_code == 201
    eid = r.json()["exchange_id"]
    page = tc.get(f"/console/exchanges/{eid}")
    assert page.status_code == 200
    assert "Trace</h3>" in page.text
    assert "corr-console-01" in page.text
    assert "traceparent" in page.text
