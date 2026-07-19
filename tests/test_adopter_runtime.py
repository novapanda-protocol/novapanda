"""Adopter Runtime：单元 + M1 闭环集成。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.adopter import AdopterRuntime, IntentMap, OutboxOp
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import reverify
from novapanda.sdk import NovaPandaClient

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "T-ADOPT", "total": "10.00", "currency": "USD"}


def test_intent_map_confirm_and_dispute():
    m = IntentMap()
    assert m.parse("确认").action == "confirm"
    assert m.parse("ok").action == "confirm"
    d = m.parse("不对：少了 currency")
    assert d is not None and d.action == "dispute"
    assert "currency" in d.reason
    assert m.parse("随便聊聊") is None


def test_draft_and_outbox_persist(tmp_path: Path):
    from novapanda.adopter import DraftStore, Outbox

    drafts = DraftStore(tmp_path)
    rec = drafts.create(
        agent_id="ed25519:a",
        peer_id="ed25519:b",
        resource_type=RESOURCE,
        rule_id=RULE_ID,
        intent_summary="x",
    )
    drafts.set_deliverable(rec.draft_id, GOOD)
    again = DraftStore(tmp_path)
    assert again.get(rec.draft_id).status == "ready"
    assert again.get(rec.draft_id).deliverable == GOOD

    box = Outbox(tmp_path)
    box.partition()
    item = box.enqueue(OutboxOp.CONFIRM, "ex-1")
    assert len(box.list_pending()) == 1
    with pytest.raises(RuntimeError, match="网络仍断开"):
        box.flush(lambda _i: None)
    box.restore()
    results = box.flush(lambda _i: {"ok": True})
    assert results[0]["ok"] is True
    assert box.get(item.item_id).status == "done"


def test_peer_backup_fingerprint(tmp_path: Path):
    from novapanda.adopter import PeerBackup, VdcVault

    vault = VdcVault(tmp_path)
    vdc = {
        "vdc_id": "vdc-test-1",
        "state": "SETTLED",
        "resource_type": RESOURCE,
        "result_hash": "sha256:" + "a" * 64,
        "parties": {"client": "c", "provider": "p"},
        "signatures": {},
    }
    entry = vault.put(
        vdc=vdc, exchange_id="ex-1", peer_id="p", role="client", deliverable=GOOD,
    )
    peers = PeerBackup(vault)
    pkg = peers.export_for_peer(entry)
    other = VdcVault(tmp_path / "other")
    PeerBackup(other).import_from_peer(pkg, peer_id="p", role="client")
    assert other.contains("vdc-test-1")
    bad = dict(pkg)
    bad["fingerprint"] = "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        PeerBackup(other).import_from_peer(bad, peer_id="p", role="client")


def _pair(tc: TestClient, root: Path):
    buyer = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        root / "buyer",
    )
    seller = AdopterRuntime(
        NovaPandaClient("http://testserver", Identity.generate(), http=tc),
        root / "seller",
    )
    return buyer, seller


def test_closed_loop_offline_confirm_mutual_backup(tmp_path: Path):
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    buyer, seller = _pair(tc, tmp_path)

    draft = seller.open_draft(
        peer_id=buyer.agent_id,
        resource_type=RESOURCE,
        rule_id=RULE_ID,
        intent_summary="unit",
    )
    ex = buyer.client.propose(
        provider=seller.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price=PRICE,
        idempotency_key="adopter-ut-1",
    )
    eid = ex["exchange_id"]
    seller.drafts.bind_exchange(draft.draft_id, eid)
    buyer.client.contract(eid)
    seller.client.contract(eid)
    buyer.client.escrow(eid, amount=100, currency="USD")
    seller.prepare_deliverable(draft.draft_id, GOOD)
    seller.deliver_from_draft(draft.draft_id)
    assert buyer.verify(eid)["state"] == "VERIFIED"

    buyer.outbox.partition()
    buyer.confirm(eid)
    assert buyer.client.get_exchange(eid)["state"] == "VERIFIED"
    buyer.outbox.restore()
    assert all(r["ok"] for r in buyer.flush_outbox())
    settled = buyer.client.get_exchange(eid)
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])

    buyer.remember_settled(eid, role="client", deliverable=GOOD)
    seller.remember_settled(eid, role="provider", deliverable=GOOD)
    pkg = seller.mutual_backup_export(eid)
    # wipe buyer vault
    import shutil

    shutil.rmtree(tmp_path / "buyer" / "vault")
    from novapanda.adopter import VdcVault, PeerBackup, VaultQuery

    buyer.vault = VdcVault(tmp_path / "buyer")
    buyer.peers = PeerBackup(buyer.vault)
    buyer.query = VaultQuery(buyer.vault)
    buyer.mutual_backup_import(pkg, peer_id=seller.agent_id, role="client")

    hits = buyer.query.search(state="SETTLED", keyword="T-ADOPT")
    assert len(hits) == 1
    arb = buyer.export_arbitration(eid)
    checks = reverify(arb["vdc"], GOOD)
    assert checks["settled_valid"] is True
    assert checks["result_hash_matches"] is True

    # Intent export
    out = buyer.apply_intent(eid, "导出")
    assert out["action"] == "export"
    assert "vdc" in out["package"]


def test_sdk_dispute_method():
    """SDK 暴露 dispute（IntentMap 依赖）。"""
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    # 仅检查方法存在且路由可达形状：完整 dispute 路径需 VERIFIED 后
    c = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    assert callable(c.dispute)
