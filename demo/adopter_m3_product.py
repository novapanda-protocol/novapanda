"""Adopter M3：场站发现 → 车充闭环 → 本地锚定 → PDF/JSON 仲裁导出。

运行：  python demo/adopter_m3_product.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.adopter import (
    AdopterRuntime,
    AvChargeLoop,
    ChargeControlAdapter,
    StationRecord,
)
from novapanda.adopter.charge import ENERGY_RESOURCE, ENERGY_RULE
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import _all_ok, reverify
from novapanda.sdk import NovaPandaClient

OUT = Path(__file__).parent / "out" / "adopter_m3"


def _line(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def main() -> None:
    ChargeControlAdapter.reset_sim()
    work = Path(tempfile.mkdtemp(prefix="np-m3-"))
    OUT.mkdir(parents=True, exist_ok=True)

    # marketplace 开：演示 discover 合并；本地目录作 fallback
    app = create_app(seed=True, auth=False, marketplace_enabled=True)
    tc = TestClient(app)
    car = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        work / "car",
    )
    pile = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        work / "pile",
    )

    _line("0｜场站目录 + marketplace 挂牌")
    car.register_station(StationRecord(
        station_id="st-local-01",
        agent_id=pile.agent_id,
        resource_type=ENERGY_RESOURCE,
        rule_id_hint=ENERGY_RULE,
        price_amount=1050,
        price_currency="USD",
        location_label="Demo Lot A",
        exchange_endpoint="http://testserver/exchanges",
        tags=["energy", "charging", "dc"],
    ))
    # 市场挂牌（供 discover）
    listing = {
        "listing_id": "lst-pile-m3",
        "agent_id": pile.agent_id,
        "resource_type": ENERGY_RESOURCE,
        "capability_tags": ["energy", "charging", "dc"],
        "max_response_ms": 5000,
        "price_amount": 1050,
        "price_currency": "USD",
        "exchange_endpoint": "http://testserver/exchanges",
        "rule_id_hint": ENERGY_RULE,
    }
    reg = tc.post("/marketplace/listings", json=listing)
    print(f"marketplace register status={reg.status_code}")

    found = car.discover_stations(max_amount=2000, prefer_marketplace=True)
    print(json.dumps({
        "winner_source": (found.get("winner") or {}).get("source"),
        "winner_agent": (found.get("winner") or {}).get("agent_id"),
        "local_n": len(found.get("local") or []),
        "market_available": (found.get("marketplace") or {}).get("available"),
    }, ensure_ascii=False, indent=2))
    assert found.get("winner")
    assert found["winner"]["agent_id"] == pile.agent_id

    _line("1｜按发现结果跑车充闭环")
    loop = AvChargeLoop(car=car, pile=pile)
    loop.open_charge_intent(target_kwh="5.000", idempotency_key="adopter-m3-1")
    loop.run_physical_session(kwh_delivered="5.000")
    settled = loop.settle(offline_confirm=False, mutual_backup=True)
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])

    _line("2｜廉价本地锚定（旁路，非终局）")
    receipt = car.anchor_exchange(
        loop.exchange_id,  # type: ignore[arg-type]
        meta={"scenario": "S-av-charge", "station": "st-local-01"},
    )
    print(json.dumps(receipt.to_dict(), ensure_ascii=False, indent=2))
    check = car.anchors.verify_local(settled["vdc"])
    assert check["anchored"] is True
    print(f"anchor verify: anchored={check['anchored']}")

    _line("3｜仲裁 JSON + PDF 展示壳")
    eid = loop.exchange_id
    assert eid
    arb = car.export_arbitration(eid)
    pdf_path = car.export_arbitration_pdf(eid, OUT / "arbitration.pdf")
    (OUT / "arbitration.json").write_text(
        json.dumps(arb, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "anchor_receipt.json").write_text(
        json.dumps(receipt.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "stations_discover.json").write_text(
        json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    raw = pdf_path.read_bytes()
    assert raw.startswith(b"%PDF-")
    print(f"pdf bytes={len(raw)} path={pdf_path}")

    checks = reverify(settled["vdc"], loop.deliverable, settled.get("verify_result"))
    assert _all_ok(checks)
    print(json.dumps(checks, ensure_ascii=False, indent=2))

    _line("done｜M3 产品面竖切通过")
    print(f"工件: {OUT}")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
