"""Adopter Bundle 竖切：到场巡检四腿 · S-nested-site-patrol。

车到场 → 无人机 → 机器人 → 可选充电；多张 VDC + correlation_id + human_gate。
运行：  python demo/adopter_site_patrol.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.adopter import AdopterRuntime
from novapanda.adopter.meter import MeterAdapter
from novapanda.adopter.patrol import SitePatrolBundle
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import _all_ok, reverify
from novapanda.sdk import NovaPandaClient

OUT = Path(__file__).parent / "out" / "adopter_site_patrol"


def _line(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def _rt(tc: TestClient, root: Path, name: str) -> AdopterRuntime:
    return AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        root / name,
    )


def main() -> None:
    MeterAdapter.reset_sim()
    work = Path(tempfile.mkdtemp(prefix="np-patrol-"))
    OUT.mkdir(parents=True, exist_ok=True)

    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    owner = _rt(tc, work, "owner")
    gate = _rt(tc, work, "gate")
    drone = _rt(tc, work, "drone")
    robot = _rt(tc, work, "robot")
    pile = _rt(tc, work, "pile")

    patrol = SitePatrolBundle(
        owner=owner,
        gate=gate,
        drone=drone,
        robot=robot,
        pile=pile,
        include_charge=True,
    )

    _line("0｜主体")
    print(f"correlation_id={patrol.correlation_id}")
    print(f"owner={owner.agent_id}")
    print(f"gate/drone/robot/pile providers ready")

    _line("1｜四腿交割（各一张 VDC）")
    result = patrol.run_all(kwh_delivered="6.000")
    for lid, leg in result["legs"].items():
        assert V.is_valid_settled(leg["vdc"])
        print(f"  {lid}: {leg['exchange_id']} → {leg['vdc_id'][:16]}… SETTLED")

    _line("2｜Bundle 拓扑与 ready")
    print(json.dumps({
        "order": result["order"],
        "bundle_ready": result["bundle_ready"],
        "human_gate": result["human_gate"],
        "vdc_n": len(result["bundle"]["vdc_ids"]),
        "correlation_id": result["bundle"]["correlation_id"],
    }, ensure_ascii=False, indent=2))
    assert result["bundle_ready"] is True
    assert len(result["bundle"]["vdc_ids"]) == 4

    _line("3｜逐张 reverify + 导出 Bundle")
    for lid, leg in result["legs"].items():
        checks = reverify(leg["vdc"], leg["deliverable"])
        assert _all_ok(checks), (lid, checks)
        print(f"  reverify {lid} ok")

    bundle_path = OUT / "site_patrol_bundle.json"
    bundle_path.write_text(
        json.dumps(result["bundle"], ensure_ascii=False, indent=2), encoding="utf-8",
    )
    legs_path = OUT / "legs.json"
    # 精简导出：不含完整 vdc 大段时可另存
    slim = {
        lid: {
            "exchange_id": leg["exchange_id"],
            "vdc_id": leg["vdc_id"],
            "resource_type": leg["resource_type"],
            "deliverable": leg["deliverable"],
        }
        for lid, leg in result["legs"].items()
    }
    legs_path.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
    for lid, leg in result["legs"].items():
        (OUT / f"{lid}_vdc.json").write_text(
            json.dumps(leg["vdc"], ensure_ascii=False, indent=2), encoding="utf-8",
        )

    print(f"\nBundle → {bundle_path}")
    _line("done｜S-nested-site-patrol Adopter 竖切通过")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
