"""导出 ``TOOL_MANIFEST.json``（供第三方 Agent 直接注册 Function Calling）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import RecoveryAction
from .tools import TOOL_DEFINITIONS, tool_names

MANIFEST_VERSION = "1.0.0"
_MANIFEST_PATH = Path(__file__).resolve().parent / "TOOL_MANIFEST.json"


def build_tool_manifest() -> dict[str, Any]:
    """结构化 tool manifest：读完即可生成 LLM Function Calling 提示。"""
    return {
        "manifest_version": MANIFEST_VERSION,
        "skill": "NovaPandaAgentSkill",
        "package": "novapanda.agent_skill",
        "invoke": {
            "method": "NovaPandaAgentSkill.invoke",
            "signature": "invoke(name: str, arguments: dict | None) -> {ok, result|fault}",
            "ok_shape": {"ok": True, "result": "object"},
            "error_shape": {
                "ok": False,
                "fault": {
                    "code": "string",
                    "message": "string",
                    "recovery": [a.value for a in RecoveryAction],
                    "retryable": "boolean",
                    "hint": "string",
                    "details": "object",
                },
            },
        },
        "conventions": {
            "no_raw_tx_hex": True,
            "amounts_are_integers": True,
            "default_views_are_token_compact": True,
            "publication": "ready-but-not-public",
        },
        "tool_names": tool_names(),
        "tools": list(TOOL_DEFINITIONS),
        "suggested_workflow": [
            "novapanda_list_tools",
            "novapanda_discover_providers",
            "novapanda_quote_price",
            "novapanda_hold_auction",
            "novapanda_split_task",
            "novapanda_estimate_gas",
            "novapanda_paymaster_sponsor",
            "novapanda_run_supply_chain",
            "novapanda_verify_proof",
            "novapanda_settlement_escrow",
            "novapanda_settlement_settle",
            "novapanda_compact_terminal",
        ],
    }


def write_tool_manifest(path: Path | None = None) -> Path:
    """写入 ``TOOL_MANIFEST.json``；返回路径。"""
    target = path or _MANIFEST_PATH
    payload = build_tool_manifest()
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    out = write_tool_manifest()
    print(f"wrote {out} ({len(tool_names())} tools)")
