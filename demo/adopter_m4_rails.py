"""Adopter M4：可插拔表计 + 多轨锚定 + 座舱指令。

运行：  python demo/adopter_m4_rails.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.adopter import AdopterRuntime, AvChargeLoop, ChargeControlAdapter
from novapanda.adopter.meter import RecordingMeterBackend
from novapanda.adopter.meter import Iso15118MeterBackend, MeterAdapter
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import _all_ok, reverify
from novapanda.sdk import NovaPandaClient

OUT = Path(__file__).parent / "out" / "adopter_m4"


def _line(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def main() -> None:
    MeterAdapter.reset_sim()
    work = Path(tempfile.mkdtemp(prefix="np-m4-"))
    OUT.mkdir(parents=True, exist_ok=True)
    bulletin = work / "shared_bulletin.jsonl"

    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    recorder = RecordingMeterBackend(inner=Iso15118MeterBackend(evse_id="EVSE-M4"))
    meter = MeterAdapter(backend=recorder)

    car = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        work / "car",
        enable_bulletin=True,
        enable_chain_stub=True,
        shared_bulletin=bulletin,
    )
    pile = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        work / "pile",
        enable_bulletin=True,
        enable_chain_stub=False,
        shared_bulletin=bulletin,
    )

    _line("0｜可插拔表计（Recording → ISO15118 sim）")
    print(f"meter backend={meter.backend_id()}")

    loop = AvChargeLoop(
        car=car,
        pile=pile,
        control=ChargeControlAdapter(evse_id="EVSE-M4", meter=meter),
    )
    loop.open_charge_intent(target_kwh="4.250", idempotency_key="adopter-m4-1")
    phys = loop.run_physical_session(kwh_delivered="4.250")
    print(f"session={phys['session_id']} calls={recorder.calls}")

    # 验收后先不 confirm，用座舱确认
    verified = car.verify(loop.exchange_id)  # type: ignore[arg-type]
    assert verified["state"] == "VERIFIED"

    _line("1｜座舱 UX：确认结算")
    cabin_out = car.cabin.confirm_settlement(loop.exchange_id)  # type: ignore[arg-type]
    print(f"cabin action={cabin_out['action']}")
    settled = car.client.get_exchange(loop.exchange_id)  # type: ignore[arg-type]
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])
    car.remember_settled(
        loop.exchange_id,  # type: ignore[arg-type]
        role="client",
        deliverable=loop.deliverable,
        peer_id=pile.agent_id,
    )
    pile.remember_settled(
        loop.exchange_id,  # type: ignore[arg-type]
        role="provider",
        deliverable=loop.deliverable,
        peer_id=car.agent_id,
    )

    _line("2｜多轨锚定：local + bulletin + chain_stub")
    multi = car.anchor_exchange(
        loop.exchange_id,  # type: ignore[arg-type]
        meta={"milestone": "M4"},
        multi=True,
    )
    assert isinstance(multi, dict)
    print(json.dumps({
        "local_rail": multi["local"]["rail"],
        "fanout_rails": [f.get("rail") for f in multi["fanout"]],
        "fanout_n": len(multi["fanout"]),
    }, ensure_ascii=False, indent=2))
    verify = car.multi_anchor.verify(settled["vdc"])
    assert verify["anchored_any"] is True
    # 桩侧读同一公告板应能 lookup
    pile_view = pile.multi_anchor.verify(settled["vdc"])
    assert any(pile_view["rails"].values())

    _line("3｜导出 + reverify")
    eid = loop.exchange_id
    assert eid
    arb = car.export_arbitration(eid)
    pdf = car.export_arbitration_pdf(eid, OUT / "arbitration.pdf")
    (OUT / "multi_anchor.json").write_text(
        json.dumps(multi, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "arbitration.json").write_text(
        json.dumps(arb, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "bulletin.jsonl").write_bytes(bulletin.read_bytes())
    checks = reverify(settled["vdc"], loop.deliverable, verified.get("verify_result"))
    assert _all_ok(checks)
    print(f"pdf={pdf} reverify_ok=True meter_calls={len(recorder.calls)}")

    _line("done｜M4 增强档通过")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
