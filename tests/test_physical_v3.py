from fastapi.testclient import TestClient

from troodon.node import create_app
from troodon.v3.physical import iso15118_session_stub, validate_physical_deliverable


def test_energy_deliverable_validation():
    d = {
        "session_id": "sess-1",
        "kwh_delivered": "12.500",
        "meter_signature": "sig-demo",
    }
    assert validate_physical_deliverable("energy.electric.dc", d) == []


def test_actuation_missing_field():
    errs = validate_physical_deliverable("actuation.robot.task", {"task_id": "t1"})
    assert any("completion_proof" in e for e in errs)


def test_physical_validate_api():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    stub = iso15118_session_stub("sess-99")
    body = {
        "resource_type": "energy.electric.dc",
        "deliverable": {
            "session_id": stub["session_id"],
            "kwh_delivered": "5",
            "meter_signature": "meter-sig",
        },
    }
    r = tc.post("/v3/physical/validate", json=body)
    assert r.status_code == 200
    assert r.json()["valid"] is True
