"""Adopter M2 竖切：智能车 ↔ 充电桩（energy.electric.dc · NP-PHYS）。

控制回路 = ISO15118 sim；交割回路 = Exchange + AdopterRuntime。
运行：  python demo/adopter_av_charge.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.adopter import AdopterRuntime
from novapanda.adopter.charge import AvChargeLoop, ChargeControlAdapter
from novapanda.identity import Identity
from novapanda.manifest import verify_agent_manifest
from novapanda.node import create_app
from novapanda.reverify import _all_ok, reverify
from novapanda.sdk import NovaPandaClient
from novapanda.v3.physical import validate_physical_deliverable

OUT = Path(__file__).parent / "out" / "adopter_av_charge"


def _line(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def main() -> None:
    ChargeControlAdapter.reset_sim()
    work = Path(tempfile.mkdtemp(prefix="np-av-charge-"))
    OUT.mkdir(parents=True, exist_ok=True)

    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    car = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        work / "car",
    )
    pile = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        work / "pile",
    )
    loop = AvChargeLoop(car=car, pile=pile)

    _line("0｜主体：车=client · 桩=provider")
    print(f"car  = {car.agent_id}")
    print(f"pile = {pile.agent_id}")
    manifest = loop.pile_manifest()
    assert verify_agent_manifest(manifest)
    print(f"pile manifest ok, capability={manifest['capabilities'][0]['resource_type']}")

    _line("1｜车开充电意图 → propose/contract/escrow (mock)")
    opened = loop.open_charge_intent(
        target_kwh="12.500",
        idempotency_key="adopter-av-charge-1",
        vehicle_label="demo-av-01",
    )
    print(json.dumps(opened, ensure_ascii=False, indent=2))

    _line("2｜控制回路：ISO15118 会话 → 物理 deliverable → 桩 deliver")
    phys = loop.run_physical_session(kwh_delivered="12.500")
    print(f"session_id={phys['session_id']}")
    print(f"result_hash={phys['result_hash']}")
    print(f"phys_validate={validate_physical_deliverable('energy.electric.dc', phys['deliverable'])}")
    assert phys["state"] == "DELIVERED"

    _line("3｜车验收；弱网 confirm；互存；reverify")
    settled = loop.settle(offline_confirm=True, mutual_backup=True)
    print(f"state={settled['state']} flush_ok={[r['ok'] for r in settled['flush']]}")
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])

    checks = reverify(
        settled["vdc"],
        loop.deliverable,
        settled.get("verify_result"),
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    assert _all_ok(checks)

    arb = car.export_arbitration(loop.exchange_id)  # type: ignore[arg-type]
    (OUT / "arbitration.json").write_text(
        json.dumps(arb, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "deliverable.json").write_text(
        json.dumps(loop.deliverable, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "settled_vdc.json").write_text(
        json.dumps(settled["vdc"], ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"car_stats={settled['car_stats']}")
    print(f"pile_stats={settled['pile_stats']}")

    _line("4｜Intent：电量异议语（解析演示，本笔已 SETTLED）")
    print(car.intents.parse("不对：电量不对"))

    _line("done｜M2 车充竖切通过")
    print(f"工件: {OUT}")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
