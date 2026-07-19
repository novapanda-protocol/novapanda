"""Adopter Runtime M0–M1 竖切：草稿 → 交割 → 离线确认 → 互存 → 仲裁导出。

运行：  python demo/adopter_closed_loop.py

对齐 docs/adopter-closed-loop.md · S-invoice-extract。
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.adopter import AdopterRuntime, VdcVault, PeerBackup, VaultQuery
from novapanda.adopter.export_pkg import package_summary_text
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import reverify
from novapanda.sdk import NovaPandaClient

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "ADOPT-001", "total": "100.00", "currency": "USD"}
OUT = Path(__file__).parent / "out" / "adopter"


def _line(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def _reverify_ok(checks: dict) -> bool:
    return (
        checks.get("provider_sig_valid") is True
        and checks.get("client_sig_valid") is True
        and checks.get("settled_valid") is True
        and checks.get("result_hash_matches") is True
    )


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="np-adopter-"))
    client_root = work / "client"
    provider_root = work / "provider"
    OUT.mkdir(parents=True, exist_ok=True)

    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client_sdk = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider_sdk = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    buyer = AdopterRuntime(client_sdk, client_root)
    seller = AdopterRuntime(provider_sdk, provider_root)

    _line("0｜身份与 Runtime 根目录")
    print(f"client  = {buyer.agent_id}")
    print(f"provider= {seller.agent_id}")
    print(f"roots   = {client_root} | {provider_root}")

    _line("1｜Provider 开草稿（任务进行中，尚未 deliver）")
    draft = seller.open_draft(
        peer_id=buyer.agent_id,
        resource_type=RESOURCE,
        rule_id=RULE_ID,
        intent_summary="抽取发票字段 ADOPT-001",
    )
    print(f"draft_id={draft.draft_id} status={draft.status}")

    _line("2｜Client propose → 双签条款 → escrow (mock)")
    ex = buyer.client.propose(
        provider=seller.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price=PRICE,
        idempotency_key="adopter-loop-1",
    )
    eid = ex["exchange_id"]
    seller.drafts.bind_exchange(draft.draft_id, eid)
    buyer.client.contract(eid)
    seller.client.contract(eid)
    buyer.client.escrow(eid, amount=100, currency="USD")
    print(f"exchange={eid} state={buyer.client.get_exchange(eid)['state']}")

    _line("3｜Provider 填交付物哈希并 deliver_from_draft")
    seller.prepare_deliverable(draft.draft_id, GOOD)
    print(f"result_hash={seller.deliverable_hash(GOOD)}")
    delivered = seller.deliver_from_draft(draft.draft_id)
    print(f"DELIVERED state={delivered['state']}")
    print(f"draft status={seller.drafts.get(draft.draft_id).status}")

    _line("4｜Client verify；断网排队 confirm；恢复 flush")
    verified = buyer.verify(eid)
    print(f"VERIFIED state={verified['state']}")
    buyer.outbox.partition()
    queued = buyer.confirm(eid)
    print(f"offline queued confirm item_id={queued.item_id} status={queued.status}")
    assert buyer.client.get_exchange(eid)["state"] == "VERIFIED", "断网不得伪 SETTLED"
    buyer.outbox.restore()
    flushed = buyer.flush_outbox()
    print(f"flush ok={[r['ok'] for r in flushed]}")
    settled = buyer.client.get_exchange(eid)
    print(f"SETTLED state={settled['state']}")
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"])

    _line("5｜双方 VdcVault 互存")
    buyer.remember_settled(eid, role="client", deliverable=GOOD)
    seller.remember_settled(eid, role="provider", deliverable=GOOD)
    pkg = seller.mutual_backup_export(eid)
    # 模拟 client 丢库后从 peer 恢复
    shutil.rmtree(client_root / "vault", ignore_errors=True)
    buyer.vault = VdcVault(client_root)
    buyer.peers = PeerBackup(buyer.vault)
    buyer.query = VaultQuery(buyer.vault)
    restored = buyer.mutual_backup_import(
        pkg, peer_id=seller.agent_id, role="client",
    )
    print(f"restored vdc_id={restored.vdc_id} source={restored.source}")
    assert buyer.vault.contains(restored.vdc_id)

    _line("6｜Query / 统计 / 仲裁导出 + 离线 reverify")
    hits = buyer.query.search(peer_id=seller.agent_id, state="SETTLED")
    print(f"query hits={len(hits)} stats={buyer.query.stats()}")
    arb = buyer.export_arbitration(eid)
    summary = package_summary_text(arb)
    (OUT / "arbitration.json").write_text(
        json.dumps(arb, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "arbitration_summary.txt").write_text(summary, encoding="utf-8")
    (OUT / "settled_vdc.json").write_text(
        json.dumps(arb["vdc"], ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "deliverable.json").write_text(
        json.dumps(GOOD, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    checks = reverify(arb["vdc"], GOOD)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    assert _reverify_ok(checks)

    _line("7｜IntentMap：确认语 / 异议语（演示解析）")
    print("确认 =>", buyer.intents.parse("确认"))
    print("异议 =>", buyer.intents.parse("不对：少了 currency"))
    intent_result = buyer.apply_intent(eid, "导出")
    assert intent_result["action"] == "export"
    print("intent 导出 ok, summary lines=", len(intent_result["summary_text"].splitlines()))

    _line("done｜M1 竖切通过")
    print(f"工件目录: {OUT}")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
