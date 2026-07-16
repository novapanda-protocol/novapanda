"""Operator 策略 A 最小路径。"""

from fastapi.testclient import TestClient

from novapanda.node import create_app


def test_operator_register_verify_login_me():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    policy = tc.get("/operator/policy")
    assert policy.status_code == 200
    assert policy.json()["access_policy"] == "open_quota"

    reg = tc.post(
        "/operator/register",
        json={
            "email": "dev@example.com",
            "display_name": "Dev",
            "password": "secret-pass",
            "accept_terms": True,
        },
    )
    assert reg.status_code == 201
    body = reg.json()
    otp = body["otp_dev"]
    assert body["operator"]["status"] == "pending"

    bad = tc.post("/operator/verify", json={"email": "dev@example.com", "otp": "000000"})
    assert bad.status_code == 400

    ok = tc.post("/operator/verify", json={"email": "dev@example.com", "otp": otp})
    assert ok.status_code == 200
    assert ok.json()["operator"]["email_verified"] is True
    assert ok.json()["operator"]["quota_propose_per_day"] == 200

    login = tc.post(
        "/operator/login",
        json={"email": "dev@example.com", "password": "secret-pass"},
    )
    assert login.status_code == 200
    token = login.json()["session_token"]
    me = tc.get("/operator/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["operator"]["email"] == "dev@example.com"


def test_dashboard_ia_v2_and_scenarios_api():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    home = tc.get("/")
    assert home.status_code == 200
    assert "5 分钟跑通 SETTLED" in home.text
    assert "场景图" in home.text
    assert "novapanda.io/scenarios" in home.text
    assert 'data-tab="scenarios"' not in home.text
    sc = tc.get("/node/scenarios")
    assert sc.status_code == 200
    data = sc.json()
    assert data["total"] >= 1
    ids = {s["id"] for s in data["scenarios"]}
    assert "S-nested-soft-diligence" in ids
