from troodon.v3 import iso15118_adapter as adapter


def test_adapter_uses_sim_backend_by_default():
    info = adapter.adapter_info()
    assert info["backend"] == "SimIso15118Backend"
    sess = adapter.create_session(evse_id="EVSE-TEST")
    assert "adapter" in sess
    out = adapter.build_energy_deliverable(sess["session_id"], kwh_delivered="12.500")
    assert out["kwh_delivered"] == "12.500"
    assert out["iso15118"]["adapter"] == adapter.adapter_info()["adapter"]


def test_bind_custom_backend():
    class StubBackend:
        def create_session(self, *, evse_id: str = "EVSE-001") -> dict:
            return {"session_id": "stub-1", "evse_id": evse_id, "status": "charging"}

        def complete_session(self, session_id: str, *, kwh_delivered: str) -> dict:
            return {
                "session_id": session_id,
                "status": "completed",
                "kwh_delivered": kwh_delivered,
                "meter_signature": "stub-sig",
            }

        def get_session(self, session_id: str):
            return {
                "session_id": session_id,
                "evse_id": "EVSE-X",
                "status": "completed",
                "meter_signature": "stub-sig",
            }

    adapter.bind_backend(StubBackend())
    try:
        sess = adapter.create_session()
        assert sess["session_id"] == "stub-1"
        assert adapter.adapter_info()["backend"] == "StubBackend"
    finally:
        adapter.bind_backend(adapter.SimIso15118Backend())
