"""Adopter M4：表计插件 · 多轨锚定 · 座舱。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from novapanda.adopter import AdopterRuntime, AvChargeLoop, ChargeControlAdapter
from novapanda.adopter.anchor_rails import BulletinBoardRail, ChainAnchorStub, MultiRailAnchor
from novapanda.adopter.meter import (
    Iso15118MeterBackend,
    MeterAdapter,
    RecordingMeterBackend,
)
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.sdk import NovaPandaClient


def test_meter_adapter_recording():
    MeterAdapter.reset_sim()
    rec = RecordingMeterBackend()
    meter = MeterAdapter(backend=rec)
    sess = meter.start_session(evse_id="EVSE-T")
    d = meter.finish_session(sess["session_id"], kwh_delivered="1.100")
    assert d["kwh_delivered"] == "1.100"
    assert [c[0] for c in rec.calls] == ["start", "finish"]


def test_bulletin_and_chain_stub(tmp_path: Path):
    from novapanda.adopter import LocalAnchorLedger

    local = LocalAnchorLedger(tmp_path)
    board = BulletinBoardRail(tmp_path / "board.jsonl")
    chain = ChainAnchorStub(chain_id="test-1")
    multi = MultiRailAnchor(local=local, rails=[board, chain])
    vdc = {
        "vdc_id": "v-m4",
        "state": "SETTLED",
        "parties": {"client": "c", "provider": "p"},
        "result_hash": "sha256:" + "b" * 64,
    }
    out = multi.anchor(vdc=vdc, exchange_id="ex-m4")
    assert len(out["fanout"]) == 2
    assert board.lookup(out["local"]["vdc_fingerprint"])
    assert chain.lookup(out["local"]["vdc_fingerprint"])
    assert multi.verify(vdc)["anchored_any"] is True


def test_cabin_confirm_after_verify(tmp_path: Path):
    MeterAdapter.reset_sim()
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    bulletin = tmp_path / "b.jsonl"
    car = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "car",
        enable_chain_stub=True,
        shared_bulletin=bulletin,
    )
    pile = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "pile",
        shared_bulletin=bulletin,
    )
    meter = MeterAdapter(backend=RecordingMeterBackend(inner=Iso15118MeterBackend()))
    loop = AvChargeLoop(
        car=car, pile=pile,
        control=ChargeControlAdapter(meter=meter),
    )
    loop.open_charge_intent(target_kwh="2.000", idempotency_key="m4-ut-1")
    loop.run_physical_session(kwh_delivered="2.000")
    assert car.verify(loop.exchange_id)["state"] == "VERIFIED"  # type: ignore[arg-type]
    car.cabin.confirm_settlement(loop.exchange_id)  # type: ignore[arg-type]
    assert car.client.get_exchange(loop.exchange_id)["state"] == "SETTLED"  # type: ignore[arg-type]
    car.remember_settled(
        loop.exchange_id, role="client", deliverable=loop.deliverable,  # type: ignore[arg-type]
    )
    multi = car.anchor_exchange(loop.exchange_id, multi=True)  # type: ignore[arg-type]
    assert isinstance(multi, dict)
    assert multi["fanout"]
