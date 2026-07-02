from fastapi.testclient import TestClient

from novapanda.node import create_app
from novapanda.v3.iso15118_sim import create_session, reset_sessions_for_tests
from novapanda.v3.physical import validate_physical_deliverable


def setup_function():
    reset_sessions_for_tests()


def test_iso15118_sim_session_to_deliverable():
    sess = create_session(evse_id="EVSE-TEST")
    sid = sess["session_id"]
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    r = tc.post(f"/v3/iso15118/sessions/{sid}/complete", json={"kwh_delivered": "12.500"})
    assert r.status_code == 200
    deliverable = r.json()
    assert deliverable["meter_signature"].startswith("meter-sim:")
    assert validate_physical_deliverable("energy.electric.dc", deliverable) == []


def test_incomplete_session_rejected_when_in_sim():
    sess = create_session()
    sid = sess["session_id"]
    deliverable = {
        "session_id": sid,
        "kwh_delivered": "1.0",
        "meter_signature": "bad",
    }
    errs = validate_physical_deliverable("energy.electric.dc", deliverable)
    assert any("session 未完成" in e for e in errs)
