"""Adopter M2：车充物理单腿。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.adopter import AdopterRuntime
from novapanda.adopter.charge import (
    ENERGY_RESOURCE,
    AvChargeLoop,
    ChargeControlAdapter,
)
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import _all_ok, reverify
from novapanda.sdk import NovaPandaClient
from novapanda.v3.physical import validate_physical_deliverable


def _loop(tmp_path: Path) -> AvChargeLoop:
    ChargeControlAdapter.reset_sim()
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    car = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "car",
    )
    pile = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "pile",
    )
    return AvChargeLoop(car=car, pile=pile)


def test_charge_control_adapter_builds_valid_deliverable():
    ChargeControlAdapter.reset_sim()
    ctl = ChargeControlAdapter(evse_id="EVSE-UT")
    sess = ctl.start_session()
    d = ctl.finish_session(sess["session_id"], kwh_delivered="3.250")
    assert validate_physical_deliverable(ENERGY_RESOURCE, d) == []
    assert d["kwh_delivered"] == "3.250"
    assert d["meter_signature"].startswith("meter-sim:")


def test_av_charge_loop_settled_offline_confirm(tmp_path: Path):
    loop = _loop(tmp_path)
    opened = loop.open_charge_intent(
        target_kwh="8.000",
        idempotency_key="av-charge-ut-1",
        vehicle_label="ut-car",
    )
    assert opened["state"] == "ESCROWED"

    phys = loop.run_physical_session(kwh_delivered="8.000")
    assert phys["state"] == "DELIVERED"
    assert validate_physical_deliverable(ENERGY_RESOURCE, phys["deliverable"]) == []

    out = loop.settle(offline_confirm=True, mutual_backup=True)
    assert out["state"] == "SETTLED"
    assert V.is_valid_settled(out["vdc"])
    assert all(r["ok"] for r in out["flush"])
    assert out["car_stats"]["settled"] == 1
    assert out["pile_stats"]["settled"] == 1

    checks = reverify(out["vdc"], loop.deliverable, out.get("verify_result"))
    assert _all_ok(checks)


def test_av_charge_rejects_bad_meter_via_verify(tmp_path: Path):
    """缺 meter_signature 的交付应在 verify 被拒（不走 sim 完成路径）。"""
    loop = _loop(tmp_path)
    loop.open_charge_intent(target_kwh="1.000", idempotency_key="av-charge-bad-1")
    # 故意绕过 adapter，塞坏交付物
    assert loop.draft_id and loop.exchange_id
    bad = {
        "session_id": "sess-bad",
        "kwh_delivered": "1.000",
        # missing meter_signature
    }
    loop.pile.prepare_deliverable(loop.draft_id, bad)
    loop.pile.deliver_from_draft(loop.draft_id)
    loop.deliverable = bad
    verified = loop.car.verify(loop.exchange_id)
    assert verified["state"] == "REJECTED"
    assert verified["verify_result"]["passed"] is False
