"""Adopter M3：PDF 壳 · 本地锚定 · 场站发现。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from novapanda.adopter import (
    AdopterRuntime,
    AvChargeLoop,
    ChargeControlAdapter,
    LocalAnchorLedger,
    StationRecord,
    build_pdf_bytes,
    write_arbitration_pdf,
)
from novapanda.adopter.charge import ENERGY_RESOURCE, ENERGY_RULE
from novapanda.adopter.export_pkg import build_arbitration_package
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.sdk import NovaPandaClient


def test_pdf_shell_bytes_are_pdf():
    raw = build_pdf_bytes(["line1", "fingerprint: sha256:abc"])
    assert raw.startswith(b"%PDF-1.4")
    assert b"%%EOF" in raw


def test_local_anchor_ledger(tmp_path: Path):
    ledger = LocalAnchorLedger(tmp_path)
    vdc = {
        "vdc_id": "v1",
        "state": "SETTLED",
        "parties": {"client": "c", "provider": "p"},
        "result_hash": "sha256:" + "a" * 64,
    }
    r = ledger.anchor(vdc=vdc, exchange_id="ex-1")
    assert r.rail == "local_jsonl"
    assert ledger.verify_local(vdc)["anchored"] is True
    assert len(ledger.find_by_fingerprint(r.vdc_fingerprint)) == 1


def test_station_discover_local_and_market(tmp_path: Path):
    ChargeControlAdapter.reset_sim()
    app = create_app(seed=True, auth=False, marketplace_enabled=True)
    tc = TestClient(app)
    car = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "car",
    )
    pile_id = Identity.generate().agent_id
    car.register_station(StationRecord(
        station_id="st-1",
        agent_id=pile_id,
        location_label="Lot",
        tags=["energy", "charging"],
    ))
    tc.post("/marketplace/listings", json={
        "listing_id": "lst-m3-ut",
        "agent_id": pile_id,
        "resource_type": ENERGY_RESOURCE,
        "capability_tags": ["energy", "charging"],
        "max_response_ms": 3000,
        "price_amount": 900,
        "price_currency": "USD",
        "exchange_endpoint": "http://testserver/exchanges",
        "rule_id_hint": ENERGY_RULE,
    })
    found = car.discover_stations(max_amount=2000)
    assert found["winner"] is not None
    assert found["local"]
    assert found["marketplace"]["available"] is True


def test_m3_export_pdf_and_anchor_after_charge(tmp_path: Path):
    ChargeControlAdapter.reset_sim()
    app = create_app(seed=True, auth=False, marketplace_enabled=False)
    tc = TestClient(app)
    car = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "car",
    )
    pile = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        tmp_path / "pile",
    )
    car.register_station(StationRecord(
        station_id="st-x",
        agent_id=pile.agent_id,
        tags=["energy", "charging"],
    ))
    found = car.discover_stations(prefer_marketplace=False)
    assert found["winner"]["agent_id"] == pile.agent_id

    loop = AvChargeLoop(car=car, pile=pile)
    loop.open_charge_intent(target_kwh="2.000", idempotency_key="m3-ut-1")
    loop.run_physical_session(kwh_delivered="2.000")
    out = loop.settle(offline_confirm=False)
    assert out["state"] == "SETTLED"

    eid = loop.exchange_id
    assert eid
    receipt = car.anchor_exchange(eid)
    assert car.anchors.verify_local(out["vdc"])["anchored"]

    pkg = car.export_arbitration(eid)
    pdf = write_arbitration_pdf(tmp_path / "a.pdf", pkg)
    assert pdf.read_bytes()[:5] == b"%PDF-"
    # package from vault also ok
    entry = car.vault.get_by_exchange(eid)
    assert entry is not None
    assert build_arbitration_package(entry)["vdc_id"] == receipt.vdc_id
