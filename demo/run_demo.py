"""模拟舱 demo：用两个**陌生**软件 Agent（无预建关系）跑通跨主体交割。

模拟未来物理世界的样态：双方此前从不相识，仅凭各自的 Ed25519 身份与开放协议，
即可完成「交割 -> 验收 -> 结算」，并产出一份任何第三方可独立复验的 VDC。

运行：  python demo/run_demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import reverify
from novapanda.sdk import NovaPandaClient

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}
BAD = {"invoice_no": "A-001", "total": "100.00"}  # 缺 currency，验收必拒
OUT = Path(__file__).parent / "out"


def _line(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def _make_pair(tc: TestClient):
    # 两个全新的、互不相识的身份
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    print(f"client  (买方) agent_id = {client.agent_id}")
    print(f"provider(卖方) agent_id = {provider.agent_id}")
    return client, provider


def scenario_happy(tc: TestClient) -> None:
    _line("场景 1｜happy path：交割成功并结算")
    client, provider = _make_pair(tc)
    ex = client.propose(provider=provider.agent_id, resource_type=RESOURCE,
                        quantity=1, rule_id=RULE_ID, price=PRICE, idempotency_key="happy-1")
    eid = ex["exchange_id"]
    print(f"PROPOSED  -> {eid}")
    client.contract(eid)
    provider.contract(eid)
    print(f"CONTRACTED-> {client.get_exchange(eid)['state']}（client+provider 双签条款）")
    print(f"ESCROWED  -> {client.escrow(eid, amount=100, currency='USD')['state']}")
    print(f"DELIVERED -> {provider.deliver(eid, GOOD)['state']}（provider 本地签名后提交）")
    print(f"VERIFIED  -> {client.verify(eid)['state']}（节点用 SchemaVerifier 确定性验收）")
    settled = client.confirm(eid)
    print(f"SETTLED   -> {settled['state']}，结算回执 = {settled['settlement_receipt']['status']}")

    doc = settled["vdc"]
    OUT.mkdir(exist_ok=True)
    (OUT / "settled_vdc.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "deliverable.json").write_text(json.dumps(GOOD, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n[离线独立复验] 不连任何节点，仅凭 VDC + deliverable：")
    print(json.dumps(reverify(doc, GOOD), ensure_ascii=False, indent=2))
    assert V.is_valid_settled(doc)
    print("已写出 demo/out/settled_vdc.json，可执行：")
    print("  python -m novapanda.reverify demo/out/settled_vdc.json --deliverable demo/out/deliverable.json")


def scenario_reject(tc: TestClient) -> None:
    _line("场景 2｜reject：交付不达标，验收拒绝并退款")
    client, provider = _make_pair(tc)
    ex = client.propose(provider=provider.agent_id, resource_type=RESOURCE,
                        quantity=1, rule_id=RULE_ID, price=PRICE, idempotency_key="reject-1")
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, BAD)
    v = client.verify(eid)
    print(f"状态 -> {v['state']}，原因 = {v['verify_result']['reason']}")
    print(f"退款 -> {v['settlement_receipt']['status']}")
    assert v["state"] == "REJECTED" and v["settlement_receipt"]["status"] == "refunded"


def scenario_timeout(tc: TestClient) -> None:
    _line("场景 3｜timeout：超时未交付，清扫器过期并退款")
    client, provider = _make_pair(tc)
    # deliver 阶段超时设为 0 秒：托管后立刻进入「已过期」窗口
    ex = client.propose(provider=provider.agent_id, resource_type=RESOURCE, quantity=1,
                        rule_id=RULE_ID, price=PRICE, idempotency_key="timeout-1",
                        timeouts={"deliver": 0})
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=100, currency="USD")
    print(f"已托管，deadline = {client.get_exchange(eid)['deadline_at']}（provider 迟迟不交付）")
    # 真实部署由后台调度器周期触发；此处显式调用 /admin/sweep 表示「清扫器到点运行」
    swept = client._http.post("/admin/sweep").json()
    print(f"清扫器过期 -> {swept['expired']}")
    final = client.get_exchange(eid)
    print(f"状态 -> {final['state']}，退款 = {final['settlement_receipt']['status']}")
    assert final["state"] == "EXPIRED_REFUNDED"


def main() -> None:
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    scenario_happy(tc)
    scenario_reject(tc)
    scenario_timeout(tc)
    _line("done｜三条路径均通过，VDC 可被任意第三方离线复验")


if __name__ == "__main__":
    main()
