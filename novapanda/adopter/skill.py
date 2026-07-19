"""Adopter Skill 面（M6）：LLM Function Calling → AdopterRuntime。

只翻译，不改 CORE；私钥仍在 Runtime 背后的本地 Identity。
与 ``novapanda.agent_skill``（自治/结算）并列，专责交割产品面。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from .export_pkg import package_summary_text
from .runtime import AdopterRuntime

ADOPTER_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "adopter_list_tools",
        "description": (
            "List Adopter Runtime skill tools (draft/vault/cabin/discover/export). "
            "Call first when integrating verifiable delivery UX—not accounting APIs."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "adopter_parse_intent",
        "description": (
            "Parse a short natural-language cabin phrase into a protocol action "
            "(confirm/dispute/verify/export/status). Does not sign or call the node."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "e.g. 确认 / 不对：电量不对"},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "adopter_apply_intent",
        "description": (
            "Apply cabin intent to an exchange: maps phrase to confirm/dispute/verify/"
            "export/status via AdopterRuntime. Signing stays local to the bound agent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "exchange_id": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["exchange_id", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "adopter_discover_stations",
        "description": (
            "Discover EV charging / energy stations from local catalog and optional "
            "marketplace. Returns winner agent_id for a later propose—not a settlement."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "max_amount": {"type": "integer", "description": "Max price minor units"},
                "prefer_marketplace": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "adopter_vault_stats",
        "description": (
            "Return local VdcVault statistics (counts by state/peer). "
            "Useful after SETTLED for audit UI."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "adopter_export_pack",
        "description": (
            "Build an arbitration export package for an exchange already in the vault. "
            "Returns fingerprint + text summary shell; verify with JSON + reverify, "
            "never trust the text alone."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "exchange_id": {"type": "string"},
                "include_summary": {"type": "boolean"},
            },
            "required": ["exchange_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "adopter_anchor",
        "description": (
            "Anchor a vaulted VDC fingerprint on local ledger and optional multi-rails "
            "(bulletin/chain stub). Side-path only—never substitutes SETTLED dual-sign."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "exchange_id": {"type": "string"},
                "multi": {"type": "boolean", "description": "Fan-out to bulletin/chain stub"},
            },
            "required": ["exchange_id"],
            "additionalProperties": False,
        },
    },
]


def adopter_tool_names() -> list[str]:
    return [t["name"] for t in ADOPTER_TOOL_DEFINITIONS]


def _ok(result: Any) -> dict[str, Any]:
    return {"ok": True, "result": result}


def _err(code: str, message: str, *, hint: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "fault": {
            "code": code,
            "message": message,
            "hint": hint,
            "retryable": False,
        },
    }


@dataclass
class AdopterSkill:
    """Bound to one AdopterRuntime (one local agent identity)."""

    runtime: AdopterRuntime

    def tool_definitions(self) -> list[dict[str, Any]]:
        return list(ADOPTER_TOOL_DEFINITIONS)

    def tool_names(self) -> list[str]:
        return adopter_tool_names()

    def invoke(self, name: str, arguments: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        args = dict(arguments or {})
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "adopter_list_tools": lambda _a: _ok(self.tool_names()),
            "adopter_parse_intent": self._parse_intent,
            "adopter_apply_intent": self._apply_intent,
            "adopter_discover_stations": self._discover,
            "adopter_vault_stats": lambda _a: _ok(self.runtime.query.stats()),
            "adopter_export_pack": self._export,
            "adopter_anchor": self._anchor,
        }
        fn = handlers.get(name)
        if fn is None:
            return _err(
                "UNKNOWN_TOOL",
                f"unknown adopter tool: {name}",
                hint=f"Use one of {self.tool_names()}",
            )
        try:
            return fn(args)
        except KeyError as exc:
            return _err("NOT_FOUND", str(exc), hint="Ensure exchange is in VdcVault.")
        except ValueError as exc:
            return _err("INVALID", str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err("ADOPTER_ERROR", str(exc)[:200])

    def _parse_intent(self, a: dict[str, Any]) -> dict[str, Any]:
        hit = self.runtime.intents.parse(str(a.get("text") or ""))
        if hit is None:
            return _ok({"matched": False, "action": None})
        return _ok({
            "matched": True,
            "action": hit.action,
            "reason": hit.reason,
            "raw": hit.raw,
        })

    def _apply_intent(self, a: dict[str, Any]) -> dict[str, Any]:
        out = self.runtime.apply_intent(str(a["exchange_id"]), str(a["text"]))
        # 压缩 export 大包
        if out.get("action") == "export" and "package" in out:
            pkg = out["package"]
            return _ok({
                "action": "export",
                "vdc_id": pkg.get("vdc_id"),
                "fingerprint": pkg.get("vdc_fingerprint"),
                "summary_text": out.get("summary_text") or package_summary_text(pkg),
            })
        if out.get("action") == "status" and isinstance(out.get("result"), dict):
            r = out["result"]
            return _ok({
                "action": "status",
                "exchange_id": r.get("exchange_id"),
                "state": r.get("state"),
            })
        # confirm/dispute/verify：尽量只回状态
        result = out.get("result")
        if isinstance(result, dict) and "state" in result:
            return _ok({
                "action": out.get("action"),
                "state": result.get("state"),
                "exchange_id": result.get("exchange_id"),
            })
        return _ok({"action": out.get("action"), "result_type": type(result).__name__})

    def _discover(self, a: dict[str, Any]) -> dict[str, Any]:
        found = self.runtime.discover_stations(
            max_amount=int(a.get("max_amount") or 10_000),
            prefer_marketplace=bool(a.get("prefer_marketplace", True)),
        )
        winner = found.get("winner") or {}
        return _ok({
            "winner_agent_id": winner.get("agent_id"),
            "winner_source": winner.get("source"),
            "local_n": len(found.get("local") or []),
            "marketplace_available": (found.get("marketplace") or {}).get("available"),
        })

    def _export(self, a: dict[str, Any]) -> dict[str, Any]:
        pkg = self.runtime.export_arbitration(str(a["exchange_id"]))
        include_summary = bool(a.get("include_summary", True))
        out: dict[str, Any] = {
            "vdc_id": pkg.get("vdc_id"),
            "exchange_id": pkg.get("exchange_id"),
            "fingerprint": pkg.get("vdc_fingerprint"),
            "export_version": pkg.get("export_version"),
        }
        if include_summary:
            out["summary_text"] = package_summary_text(pkg)
        return _ok(out)

    def _anchor(self, a: dict[str, Any]) -> dict[str, Any]:
        multi = bool(a.get("multi", False))
        receipt = self.runtime.anchor_exchange(str(a["exchange_id"]), multi=multi)
        if isinstance(receipt, dict):
            return _ok({
                "multi": True,
                "local_rail": (receipt.get("local") or {}).get("rail"),
                "fanout_n": len(receipt.get("fanout") or []),
            })
        return _ok(receipt.to_dict())
