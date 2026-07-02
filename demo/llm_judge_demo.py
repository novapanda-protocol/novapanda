"""LLM 内置 judge 演示：regex judge + R-llm-summary-v1 全生命周期。

运行（仓库根目录）：
    python demo/llm_judge_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from novapanda import vdc as V
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.registry import load_default_registries
from novapanda.settlement import MockSettlement
from novapanda.terms import sign_contract_ack
from novapanda.verifier import make_verifier

_, RULES = load_default_registries()
RULE = RULES.get("R-llm-summary-v1")
GOOD = {"summary": "PASS: task completed with acceptable quality"}
BAD = {"summary": "FAIL: incomplete output"}


def _dual_contract(engine, eid, client, provider):
    for party in (client, provider):
        ex = engine.get(eid)
        engine.contract(
            eid, party=party.agent_id,
            signature=sign_contract_ack(party, ex),
        )


def run() -> bool:
    engine = ExchangeEngine(
        MockSettlement(),
        verifier=make_verifier("llm", llm_judge="regex"),
    )
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="service.task.generic", quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"},
        idempotency_key="llm-judge-demo",
    )
    _dual_contract(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    engine.deliver(ex.exchange_id, provider, GOOD)
    ok = engine.verify(ex.exchange_id, rule=RULE)
    assert ok.state == "VERIFIED"
    settled = engine.confirm(ex.exchange_id, client)
    assert settled.state == "SETTLED"
    assert V.is_valid_settled(settled.vdc)

    ex2 = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="service.task.generic", quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"},
        idempotency_key="llm-judge-demo-bad",
    )
    _dual_contract(engine, ex2.exchange_id, client, provider)
    engine.escrow(ex2.exchange_id, amount=50, currency="USD")
    engine.deliver(ex2.exchange_id, provider, BAD)
    rejected = engine.verify(ex2.exchange_id, rule=RULE)
    assert rejected.state == "REJECTED"

    print(json.dumps({
        "rule_id": "R-llm-summary-v1",
        "judge": "regex",
        "happy_exchange": ex.exchange_id,
        "rejected_exchange": ex2.exchange_id,
        "verify_result": ok.verify_result,
    }, ensure_ascii=False, indent=2))
    return True


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
