"""节点配置：环境变量驱动，便于部署而不改代码。

协议品牌：**Troodon**（环境变量前缀 `TROODON_*`、包名 `troodon` 保持不变）。

环境变量（均可选）：  TROODON_AUTH=1|0              默认 1（开启请求鉴权）
  TROODON_DB=path.sqlite        SQLite 路径；不设则用内存
  TROODON_SETTLEMENT=mock|x402|ap2|fiat  结算适配器
  TROODON_X402_URL=http://...   x402 网关 base URL
  TROODON_AP2_URL=http://...    AP2 网关 base URL
  TROODON_FIAT_URL=http://...   法币伙伴网关 URL
  TROODON_ONTOLOGY=path.json    本体注册表路径
  TROODON_RULES=path.json       规则注册表路径
  TROODON_REPUTATION_DB=path    信誉 SQLite（默认同 TROODON_DB 或内存）
  TROODON_ARBITRATOR=agent_id   争议裁决者（设后 resolve 仅允许该身份）
  TROODON_WITNESS_V2=1|0        启用 witness v2 attach/slash（默认 0）
  TROODON_FEDERATION_V2=1|0     启用跨节点信誉导入（默认 0）
  TROODON_TIMEOUT_CONTRACT=sec  默认 contract 超时（默认 300）
  TROODON_TIMEOUT_ESCROW=sec      默认 escrow 超时（默认 300）
  TROODON_TIMEOUT_DELIVER=sec     默认 deliver 超时（默认 600）
  TROODON_TIMEOUT_VERIFY=sec      可选 verify 超时（DELIVERED 后须验收）
  TROODON_TIMEOUT_CONFIRM=sec     可选 confirm 超时（VERIFIED 后 client 须确认）
  TROODON_VERIFIER=schema|llm     验收器（默认 schema）
  TROODON_LLM_JUDGE=regex|field_match|http|openai  llm 验收器 judge（http/openai 需 LLM_GATEWAY_URL）
  TROODON_LLM_GATEWAY_URL=http://...  LLM 裁判 HTTP 网关（TROODON_LLM_JUDGE=http|openai）
  TROODON_REP_WEIGHTS=json        默认信誉加权，如 {"ed25519:NodeA":1.0}
  TROODON_REP_MIN_SCORE=float     propose/escrow 前 provider 信誉门槛（不设则关闭）
  TROODON_REP_GATE_STRICT=1|0     无信誉历史时也拒绝（默认 0）
  TROODON_WITNESS_REQUIRE_STAKE=1|0  attach witness 前须锁定 stake（默认 0）
  TROODON_LLM_MODEL=name          OpenAI-compat 模型名（TROODON_LLM_JUDGE=openai）
  TROODON_LLM_API_KEY=secret      OpenAI-compat Bearer（可选）
  TROODON_LLM_CONSENSUS=spec      多裁判共识，如 unanimous:regex,field_match
  TROODON_REP_WITNESS_BONUS=0.05  每条 locked stake 对 gate 的有效分加成
  TROODON_REP_WITNESS_BONUS_CAP=0.25  见证加成上限
  TROODON_X402_API_KEY=secret     x402 网关 Bearer（可选）
  TROODON_AP2_API_KEY=secret      AP2 网关 Bearer（可选）
  TROODON_FIAT_API_KEY=secret     法币网关 Bearer（可选）
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .registry import DEFAULT_ONTOLOGY_PATH, DEFAULT_RULES_PATH
from .verifier import make_verifier

DEFAULT_TIMEOUTS = {"contract": 300, "escrow": 300, "deliver": 600}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class NodeConfig:
    auth: bool = True
    db_path: Optional[str] = None
    settlement: str = "mock"
    x402_gateway_url: Optional[str] = None
    ontology_path: Path = DEFAULT_ONTOLOGY_PATH
    rules_path: Path = DEFAULT_RULES_PATH
    reputation_db_path: Optional[str] = None
    arbitrator_id: Optional[str] = None
    ap2_gateway_url: Optional[str] = None
    fiat_gateway_url: Optional[str] = None
    witness_v2: bool = False
    federation_v2: bool = False
    verifier: str = "schema"
    llm_judge: Optional[str] = None
    llm_gateway_url: Optional[str] = None
    reputation_weights: dict = field(default_factory=dict)
    reputation_min_score: Optional[float] = None
    reputation_gate_strict: bool = False
    witness_require_stake: bool = False
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_consensus: Optional[str] = None
    rep_witness_bonus_per_stake: float = 0.05
    rep_witness_bonus_cap: float = 0.25
    x402_api_key: Optional[str] = None
    ap2_api_key: Optional[str] = None
    fiat_api_key: Optional[str] = None
    default_timeouts: dict = field(default_factory=lambda: dict(DEFAULT_TIMEOUTS))
    seed: bool = True

    @classmethod
    def from_env(cls) -> "NodeConfig":
        db = os.environ.get("TROODON_DB")
        rep = os.environ.get("TROODON_REPUTATION_DB") or db
        onto = os.environ.get("TROODON_ONTOLOGY")
        rules = os.environ.get("TROODON_RULES")
        timeouts = dict(DEFAULT_TIMEOUTS)
        for phase, env_name in (
            ("contract", "TROODON_TIMEOUT_CONTRACT"),
            ("escrow", "TROODON_TIMEOUT_ESCROW"),
            ("deliver", "TROODON_TIMEOUT_DELIVER"),
            ("verify", "TROODON_TIMEOUT_VERIFY"),
            ("confirm", "TROODON_TIMEOUT_CONFIRM"),
        ):
            raw = os.environ.get(env_name)
            if raw is not None:
                timeouts[phase] = int(raw)
        rep_weights: dict = {}
        raw_weights = os.environ.get("TROODON_REP_WEIGHTS")
        if raw_weights:
            rep_weights = json.loads(raw_weights)
        rep_min_raw = os.environ.get("TROODON_REP_MIN_SCORE")
        rep_min = float(rep_min_raw) if rep_min_raw is not None else None
        rep_bonus_raw = os.environ.get("TROODON_REP_WITNESS_BONUS")
        rep_bonus_cap_raw = os.environ.get("TROODON_REP_WITNESS_BONUS_CAP")
        llm_judge = os.environ.get("TROODON_LLM_JUDGE")
        llm_consensus = os.environ.get("TROODON_LLM_CONSENSUS")
        if llm_consensus and not llm_judge:
            llm_judge = llm_consensus if llm_consensus.startswith("consensus:") else f"consensus:{llm_consensus}"
        return cls(
            auth=_env_bool("TROODON_AUTH", True),
            db_path=db,
            settlement=os.environ.get("TROODON_SETTLEMENT", "mock").lower(),
            x402_gateway_url=os.environ.get("TROODON_X402_URL"),
            ontology_path=Path(onto) if onto else DEFAULT_ONTOLOGY_PATH,
            rules_path=Path(rules) if rules else DEFAULT_RULES_PATH,
            reputation_db_path=rep,
            arbitrator_id=os.environ.get("TROODON_ARBITRATOR"),
            ap2_gateway_url=os.environ.get("TROODON_AP2_URL"),
            fiat_gateway_url=os.environ.get("TROODON_FIAT_URL"),
            witness_v2=_env_bool("TROODON_WITNESS_V2", False),
            federation_v2=_env_bool("TROODON_FEDERATION_V2", False),
            verifier=os.environ.get("TROODON_VERIFIER", "schema").lower(),
            llm_judge=llm_judge,
            llm_gateway_url=os.environ.get("TROODON_LLM_GATEWAY_URL"),
            reputation_weights=rep_weights,
            reputation_min_score=rep_min,
            reputation_gate_strict=_env_bool("TROODON_REP_GATE_STRICT", False),
            witness_require_stake=_env_bool("TROODON_WITNESS_REQUIRE_STAKE", False),
            llm_model=os.environ.get("TROODON_LLM_MODEL"),
            llm_api_key=os.environ.get("TROODON_LLM_API_KEY"),
            llm_consensus=llm_consensus,
            rep_witness_bonus_per_stake=float(rep_bonus_raw) if rep_bonus_raw else 0.05,
            rep_witness_bonus_cap=float(rep_bonus_cap_raw) if rep_bonus_cap_raw else 0.25,
            x402_api_key=os.environ.get("TROODON_X402_API_KEY"),
            ap2_api_key=os.environ.get("TROODON_AP2_API_KEY"),
            fiat_api_key=os.environ.get("TROODON_FIAT_API_KEY"),
            default_timeouts=timeouts,
        )

    def apply_feature_flags(self) -> None:
        """将配置中的 v2 特性开关同步到模块级占位常量。"""
        from .v2 import federation, witness

        witness.WITNESS_V2_ENABLED = self.witness_v2
        federation.FEDERATION_V2_ENABLED = self.federation_v2

    def make_store(self):
        from .store import InMemoryStore, SQLiteStore

        if self.db_path:
            return SQLiteStore(self.db_path)
        return InMemoryStore()

    def make_reputation_store(self):
        from .reputation import InMemoryReputationStore, SQLiteReputationStore

        if self.reputation_db_path:
            return SQLiteReputationStore(self.reputation_db_path)
        return InMemoryReputationStore()

    def make_blob_store(self, store=None):
        from .blobs import SQLiteBlobStore

        if self.db_path:
            return SQLiteBlobStore(self.db_path)
        return None

    def make_settlement(self):
        from .settlement import (
            AP2Settlement, FiatSettlement, MockSettlement, X402Settlement,
        )
        from .ap2_gateway import HttpAP2Gateway
        from .fiat_gateway import HttpFiatGateway
        from .x402_gateway import HttpX402Gateway

        if self.settlement == "mock":
            return MockSettlement()
        if self.settlement == "x402":
            url = self.x402_gateway_url
            if not url:
                raise ValueError("TROODON_SETTLEMENT=x402 时必须设置 TROODON_X402_URL")
            return X402Settlement(HttpX402Gateway(url, api_key=self.x402_api_key))
        if self.settlement == "ap2":
            url = self.ap2_gateway_url
            if not url:
                raise ValueError("TROODON_SETTLEMENT=ap2 时必须设置 TROODON_AP2_URL")
            return AP2Settlement(HttpAP2Gateway(url, api_key=self.ap2_api_key))
        if self.settlement == "fiat":
            url = self.fiat_gateway_url
            if not url:
                raise ValueError("TROODON_SETTLEMENT=fiat 时必须设置 TROODON_FIAT_URL")
            return FiatSettlement(HttpFiatGateway(url, api_key=self.fiat_api_key))
        raise ValueError(f"未知 TROODON_SETTLEMENT: {self.settlement}")

    def make_verifier(self):
        return make_verifier(
            self.verifier,
            llm_judge=self.llm_judge,
            llm_gateway_url=self.llm_gateway_url,
            llm_model=self.llm_model,
            llm_api_key=self.llm_api_key,
        )
