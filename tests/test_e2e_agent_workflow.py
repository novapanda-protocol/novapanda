"""全链路影子演练：Agent Skill invoke 贯通市场→定价→DAG→Paymaster→VDC 验证→结算。

不触碰 CORE 算法；仅组装既有组件经 ``NovaPandaAgentSkill.invoke`` 跑通商业场景。
"""

from __future__ import annotations

from pathlib import Path

from novapanda.agent_skill import (
    NovaPandaAgentSkill,
    build_tool_manifest,
    write_tool_manifest,
)
from novapanda.autonomy import (
    InMemoryExchangeRunner,
    SupplyChainOrchestrator,
    default_auctioneer,
)
from novapanda.identity import Identity
from novapanda.marketplace import (
    DynamicScoreEngine,
    InMemoryServiceRegistry,
    InMemoryVolumeIndex,
    PriceQuote,
    ServiceListing,
    SlaOffer,
)
from novapanda.marketplace.facade import DefaultMarketplaceFacade
from novapanda.reputation import ReputationLog
from novapanda.settlement import MockSettlement
from novapanda.verification_gateway import LocalSchemaBackend, VerificationGateway
from novapanda.wallet.manager import InMemoryChainAdapter
from novapanda.wallet.paymaster_4337 import EntryPointPaymaster4337
from novapanda.wallet.types import AssetRef, ChainRef


VERIFY_RULE = {
    "schema": {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string", "minLength": 1}},
        "additionalProperties": True,
    }
}


def _build_shadow_skill() -> tuple[NovaPandaAgentSkill, Identity, Identity]:
    client, provider = Identity.generate(), Identity.generate()
    reg = InMemoryServiceRegistry()
    reg.register(
        ServiceListing(
            listing_id="L-shadow-1",
            agent_id=provider.agent_id,
            resource_type="compute.pipeline",
            capability_tags=("nlp", "extract"),
            sla=SlaOffer(max_response_ms=8_000),
            price=PriceQuote(amount=25, currency="USD"),
            endpoints={"exchange": "http://shadow"},
        )
    )
    score = DynamicScoreEngine(
        reputation_log=ReputationLog(Identity.generate()),
        volume=InMemoryVolumeIndex(),
    )
    facade = DefaultMarketplaceFacade.build_default(reg, score)
    orch = SupplyChainOrchestrator(
        auctioneer=default_auctioneer(reg, score),
        runner=InMemoryExchangeRunner(
            results={
                # sub_ids 由 dispatcher 生成；用默认 echo，验证网关另走结构化 deliverable
            }
        ),
    )

    chain = ChainRef.evm(11155111)
    ledger = InMemoryChainAdapter(chain=chain, native_symbol="ETH")
    usdc = AssetRef(chain=chain, symbol="USDC", decimals=6, token_address="0xusdc")
    payer = "0xagent-a-wallet"
    ledger.credit(payer, usdc, 1_000_000)
    paymaster = EntryPointPaymaster4337(ledger=ledger)

    gw = VerificationGateway(
        identity=Identity.generate(),
        backend=LocalSchemaBackend(),
        verify_sla_seconds=60,
    )

    skill = NovaPandaAgentSkill(
        orchestrator=orch,
        settlement=MockSettlement(),
        marketplace=facade,
        chain_adapter=ledger,
        paymaster=paymaster,
        fee_token=usdc,
        verification_gateway=gw,
        verify_rule=VERIFY_RULE,
    )
    return skill, client, provider


def test_tool_manifest_json_covers_invoke_surface():
    """生成并校验 TOOL_MANIFEST.json，供第三方 Agent 直接注册。"""
    path = write_tool_manifest()
    assert path.name == "TOOL_MANIFEST.json"
    assert path.is_file()
    manifest = build_tool_manifest()
    names = set(manifest["tool_names"])
    required = {
        "novapanda_discover_providers",
        "novapanda_quote_price",
        "novapanda_split_task",
        "novapanda_estimate_gas",
        "novapanda_paymaster_sponsor",
        "novapanda_run_supply_chain",
        "novapanda_verify_proof",
        "novapanda_settlement_escrow",
        "novapanda_settlement_settle",
    }
    assert required <= names
    assert len(manifest["tools"]) == len(names)
    # 落盘文件与 build 一致
    import json

    disk = json.loads(path.read_text(encoding="utf-8"))
    assert disk["manifest_version"] == manifest["manifest_version"]
    assert disk["invoke"]["method"] == "NovaPandaAgentSkill.invoke"


def test_e2e_agent_shadow_workflow_via_invoke():
    """商业影子链路：发现 → 定价 → 双任务拆解 → Paymaster → 供应链 → 验证 → 结算。"""
    skill, client, _provider = _build_shadow_skill()

    # 0) 工具清单
    tools = skill.invoke("novapanda_list_tools", {})
    assert tools["ok"]
    assert "novapanda_run_supply_chain" in tools["result"]

    # 1) 市场发现 / 路由撮合
    discover = skill.invoke(
        "novapanda_discover_providers",
        {
            "resource_type": "compute.pipeline",
            "max_price_amount": 200,
            "required_tags": ["nlp"],
            "client_agent_id": client.agent_id,
            "limit": 5,
        },
    )
    assert discover["ok"], discover
    assert discover["result"]["winner"] is not None
    assert discover["result"]["n_ranked"] >= 1

    # 2) 动态定价（评估复杂度）
    quote = skill.invoke(
        "novapanda_quote_price",
        {
            "resource_type": "compute.pipeline",
            "benchmark_amount": 25,
            "load_ratio": 0.4,
            "token_estimate": 2500,
            "step_estimate": 2,
            "reputation": 0.6,
        },
    )
    assert quote["ok"]
    budget = int(quote["result"]["amount"]) + 80
    assert budget > 25

    # 3) DAG 拆成 2 个并行子任务
    split = skill.invoke(
        "novapanda_split_task",
        {
            "goal_id": "shadow-commerce-1",
            "resource_type": "compute.pipeline",
            "client_agent_id": client.agent_id,
            "budget_amount": budget,
            "payload": [
                {"answer": "extract-ok", "part": 0},
                {"answer": "enrich-ok", "part": 1},
            ],
        },
    )
    assert split["ok"]
    assert split["result"]["n_tasks"] == 2
    assert all(t["depends_on"] == [] for t in split["result"]["tasks"])

    # 4) 多链钱包影子：估气 + Paymaster 代付
    gas = skill.invoke(
        "novapanda_estimate_gas",
        {
            "from_address": "0xagent-a-wallet",
            "to_address": "0xescrow-vault",
            "amount": 0,
            "symbol": "ETH",
        },
    )
    assert gas["ok"], gas
    assert gas["result"]["native_gas_estimate"] > 0

    sponsor = skill.invoke(
        "novapanda_paymaster_sponsor",
        {
            "payer_address": "0xagent-a-wallet",
            "gas_native": int(gas["result"]["native_gas_estimate"]),
            "user_op_ref": "shadow-uop-1",
        },
    )
    assert sponsor["ok"], sponsor
    assert sponsor["result"]["paymaster_available"] is True
    assert sponsor["result"]["fee_token_amount"] is not None

    # 5) 自治供应链闭环（拍卖 + 双腿 + 聚合）
    run = skill.invoke(
        "novapanda_run_supply_chain",
        {
            "goal_id": "shadow-commerce-1",
            "resource_type": "compute.pipeline",
            "client_agent_id": client.agent_id,
            "budget_amount": budget,
            "payload": [
                {"answer": "extract-ok", "part": 0},
                {"answer": "enrich-ok", "part": 1},
            ],
            "required_tags": ["nlp"],
            "include_results": True,
        },
    )
    assert run["ok"], run
    assert run["result"]["phase"] == "done"
    assert len(run["result"]["legs"]) == 2
    assert all(leg["state"] == "SETTLED" for leg in run["result"]["legs"])

    # 6) VDC 验证网关：对每条腿提交结构化 proof
    for i, leg in enumerate(run["result"]["legs"]):
        verified = skill.invoke(
            "novapanda_verify_proof",
            {
                "exchange_id": leg["exchange_id"],
                "vdc_id": leg["vdc_id"] or f"vdc-shadow-{i}",
                "rule_id": "R-shadow",
                "deliverable": {"answer": f"part-{i}-verified"},
            },
        )
        assert verified["ok"], verified
        assert verified["result"]["passed"] is True
        assert verified["result"]["credential"] is not None

    # 7) 结算轨影子：托管 → 释放（用聚合目标 id 作 exchange 键）
    esc = skill.invoke(
        "novapanda_settlement_escrow",
        {
            "exchange_id": "shadow-commerce-1",
            "amount": budget,
            "currency": "USD",
        },
    )
    assert esc["ok"]
    settled = skill.invoke(
        "novapanda_settlement_settle", {"handle": esc["result"]["handle"]}
    )
    assert settled["ok"]
    assert settled["result"]["status"] == "settled"

    # 8) 终态快照瘦身（喂回 LLM 上下文）
    sample_leg = run["result"]["legs"][0]
    terminal = skill.invoke(
        "novapanda_compact_terminal",
        {
            "exchange_id": sample_leg["exchange_id"],
            "state": "SETTLED",
            "client": client.agent_id,
            "provider": "ed25519:" + ("B" * 48),
            "resource_type": "compute.pipeline",
            "quantity": 1,
            "vdc_id": sample_leg["vdc_id"],
            "price_amount": budget // 2,
            "outcome_hint": "settled",
        },
    )
    assert terminal["ok"]
    assert terminal["result"]["outcome"] == "settled"
    assert "…" in terminal["result"]["provider"]

    # 上下文负载烟测：整次会话关键 tool result 不应膨胀
    blob = str(
        [
            discover["result"],
            quote["result"],
            split["result"],
            gas["result"],
            sponsor["result"],
            run["result"],
            settled["result"],
            terminal["result"],
        ]
    )
    assert len(blob) < 12_000


def test_manifest_file_exists_beside_package():
    pkg = Path(__file__).resolve().parents[1] / "novapanda" / "agent_skill" / "TOOL_MANIFEST.json"
    write_tool_manifest(pkg)
    assert pkg.exists()
