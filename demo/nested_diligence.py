"""尽调三连 Composer demo · S-nested-soft-diligence

抽取 → 合规任务 → LLM 摘要，三张 VDC + Bundle；后腿引用前腿 prior_vdc_refs（编排侧校验）。

运行：  python demo/nested_diligence.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from novapanda.bundle import bundle_ready, topological_order, validate_bundle, validate_prior_vdc_refs
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.sdk import NovaPandaClient
from novapanda.verifier import make_verifier

OUT = Path(__file__).parent / "out"
PRICE = {"amount": 10, "currency": "USD"}


def _settle(client: NovaPandaClient, provider: NovaPandaClient, *, resource_type: str,
            rule_id: str, deliverable: dict, idem: str) -> dict:
    ex = client.propose(
        provider=provider.agent_id,
        resource_type=resource_type,
        quantity=1,
        rule_id=rule_id,
        price=PRICE,
        idempotency_key=idem,
    )
    eid = ex["exchange_id"]
    client.contract(eid)
    provider.contract(eid)
    client.escrow(eid, amount=PRICE["amount"], currency=PRICE["currency"])
    provider.deliver(eid, deliverable)
    client.verify(eid)
    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    return {
        "exchange_id": eid,
        "vdc": settled["vdc"],
        "vdc_id": settled["vdc"]["vdc_id"],
        "deliverable": deliverable,
        "state": "SETTLED",
    }


def main() -> None:
    # 腿 1 用 Schema；腿 2/3 用内置 LLM judge（无外网）
    verifier = make_verifier("llm", llm_judge="field_match")
    # field_match 主要用于 task；summary 用 regex judge 更贴 R-llm-summary-v1
    # 分节点简化：两台引擎同进程先后跑 — 摘要腿单独起 regex verifier
    app_schema = create_app(seed=True, auth=False)
    tc1 = TestClient(app_schema)
    owner = NovaPandaClient("http://testserver", Identity.generate(), http=tc1)
    extractor = NovaPandaClient("http://testserver", Identity.generate(), http=tc1)

    print("=== 腿 1 · 发票抽取 ===")
    leg1 = _settle(
        owner, extractor,
        resource_type="data.extraction.structured",
        rule_id="R-extract-invoice-v1",
        deliverable={"invoice_no": "DD-001", "total": "99.00", "currency": "USD"},
        idem="nested-dd-extract",
    )
    print(f"SETTLED {leg1['exchange_id']} vdc={leg1['vdc_id']}")

    print("=== 腿 2 · 合规任务（prior → 抽取 VDC）===")
    app_task = create_app(seed=True, auth=False, verifier=verifier)
    tc2 = TestClient(app_task)
    owner2 = NovaPandaClient("http://testserver", owner.identity, http=tc2)
    checklist = NovaPandaClient("http://testserver", Identity.generate(), http=tc2)

    # 编排侧：下一跳前校验 prior
    prior_errs = validate_prior_vdc_refs(
        [{"vdc_id": leg1["vdc_id"], "claim": "invoice_extracted", "required": True}],
        resolve_vdc=lambda _i: leg1["vdc"],
        resolve_deliverable=lambda _i: leg1["deliverable"],
    )
    assert prior_errs == [], prior_errs

    leg2 = _settle(
        owner2, checklist,
        resource_type="service.task.generic",
        rule_id="R-task-status-v1",
        deliverable={"status": "done", "score": "A", "prior_vdc": leg1["vdc_id"]},
        idem="nested-dd-task",
    )
    print(f"SETTLED {leg2['exchange_id']} vdc={leg2['vdc_id']}")

    print("=== 腿 3 · LLM 摘要 ===")
    verifier_sum = make_verifier("llm", llm_judge="regex")
    app_sum = create_app(seed=True, auth=False, verifier=verifier_sum)
    tc3 = TestClient(app_sum)
    owner3 = NovaPandaClient("http://testserver", owner.identity, http=tc3)
    summarizer = NovaPandaClient("http://testserver", Identity.generate(), http=tc3)

    prior_errs2 = validate_prior_vdc_refs(
        [
            {"vdc_id": leg1["vdc_id"], "required": True},
            {"vdc_id": leg2["vdc_id"], "required": True},
        ],
        resolve_vdc=lambda i: {leg1["vdc_id"]: leg1["vdc"], leg2["vdc_id"]: leg2["vdc"]}.get(i),
        resolve_deliverable=lambda i: {
            leg1["vdc_id"]: leg1["deliverable"],
            leg2["vdc_id"]: leg2["deliverable"],
        }.get(i),
    )
    assert prior_errs2 == [], prior_errs2

    leg3 = _settle(
        owner3, summarizer,
        resource_type="service.task.generic",
        rule_id="R-llm-summary-v1",
        deliverable={"summary": "PASS: due-diligence pack ready for gate"},
        idem="nested-dd-summary",
    )
    print(f"SETTLED {leg3['exchange_id']} vdc={leg3['vdc_id']}")

    placeholder_ids = ["ex_a", "ex_b", "ex_c"]
    bundle = {
        "bundle_version": "0.1",
        "goal_id": "goal-soft-diligence",
        "correlation_id": "nested-dd-demo",
        "title": "供应商尽调包",
        "exchange_ids": placeholder_ids,
        "depends_on": {"ex_c": ["ex_a", "ex_b"], "ex_b": ["ex_a"]},
        "success_rule": "all_settled",
        "human_gate": {"required": False, "status": "skipped"},
        "vdc_ids": [leg1["vdc_id"], leg2["vdc_id"], leg3["vdc_id"]],
        "prior_refs_note": "legs 2–3 validated prior_vdc_refs client-side",
        "resolved_exchange_ids": {
            "ex_a": leg1["exchange_id"],
            "ex_b": leg2["exchange_id"],
            "ex_c": leg3["exchange_id"],
        },
    }
    # 用真实 id 重写便于 ready 检查
    real_ids = [leg1["exchange_id"], leg2["exchange_id"], leg3["exchange_id"]]
    bundle_check = {
        **bundle,
        "exchange_ids": real_ids,
        "depends_on": {
            real_ids[1]: [real_ids[0]],
            real_ids[2]: [real_ids[0], real_ids[1]],
        },
    }
    assert validate_bundle(bundle_check) == []
    order = topological_order(bundle_check)
    assert order == real_ids
    states = {i: "SETTLED" for i in real_ids}
    assert bundle_ready(bundle_check, exchange_states=states)

    OUT.mkdir(exist_ok=True)
    out_path = OUT / "nested_diligence_bundle.json"
    out_path.write_text(json.dumps(bundle_check, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nBundle OK →", out_path)
    print(json.dumps({"order": order, "vdc_ids": bundle_check["vdc_ids"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
