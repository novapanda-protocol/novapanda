"""Adopter Bundle：到场巡检四腿。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.adopter import AdopterRuntime
from novapanda.adopter.meter import MeterAdapter
from novapanda.adopter.patrol import (
    LEG_ARRIVAL,
    LEG_CHARGE,
    LEG_DRONE,
    LEG_ROBOT,
    SitePatrolBundle,
)
from novapanda.bundle import topological_order
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import _all_ok, reverify
from novapanda.sdk import NovaPandaClient


def _rt(tc: TestClient, root: Path, name: str) -> AdopterRuntime:
    return AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        root / name,
    )


def test_site_patrol_four_legs_bundle(tmp_path: Path):
    MeterAdapter.reset_sim()
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    patrol = SitePatrolBundle(
        owner=_rt(tc, tmp_path, "owner"),
        gate=_rt(tc, tmp_path, "gate"),
        drone=_rt(tc, tmp_path, "drone"),
        robot=_rt(tc, tmp_path, "robot"),
        pile=_rt(tc, tmp_path, "pile"),
        include_charge=True,
        correlation_id="ut-patrol-1",
    )
    result = patrol.run_all(kwh_delivered="3.000")
    assert result["bundle_ready"] is True
    assert len(result["bundle"]["vdc_ids"]) == 4
    assert set(patrol.outcomes) == {LEG_ARRIVAL, LEG_DRONE, LEG_ROBOT, LEG_CHARGE}
    order = topological_order(result["bundle"])
    assert order[0] == patrol.outcomes[LEG_ARRIVAL].exchange_id
    assert order[-1] == patrol.outcomes[LEG_CHARGE].exchange_id
    assert result["human_gate"]["status"] == "approved"
    for leg in result["legs"].values():
        assert V.is_valid_settled(leg["vdc"])
        assert _all_ok(reverify(leg["vdc"], leg["deliverable"]))


def test_site_patrol_without_charge(tmp_path: Path):
    MeterAdapter.reset_sim()
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    patrol = SitePatrolBundle(
        owner=_rt(tc, tmp_path, "owner"),
        gate=_rt(tc, tmp_path, "gate"),
        drone=_rt(tc, tmp_path, "drone"),
        robot=_rt(tc, tmp_path, "robot"),
        pile=_rt(tc, tmp_path, "pile"),
        include_charge=False,
    )
    result = patrol.run_all()
    assert len(result["bundle"]["vdc_ids"]) == 3
    assert LEG_CHARGE not in patrol.outcomes
    assert result["bundle_ready"] is True
