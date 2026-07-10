"""BINDING-MCP 工具面登记 + 只读处理器（路线 B4 样板）。

完整 MCP Server 另部署；此处提供工具名 → HTTP 路径映射与只读调用，
供实现者复制到 MCP / Skill 宿主。
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import httpx

# 建议工具名 → (HTTP method, path template, 说明)
MCP_TOOL_CATALOG: list[dict[str, str]] = [
    {"name": "np_manifest", "method": "GET", "path": "/.well-known/novapanda.json", "auth": "none"},
    {"name": "np_settlement_rails", "method": "GET", "path": "/node/settlement/rails", "auth": "none"},
    {"name": "np_settlement_quote", "method": "GET", "path": "/node/settlement/quote", "auth": "none"},
    {"name": "np_get_exchange", "method": "GET", "path": "/exchanges/{exchange_id}", "auth": "none"},
    {"name": "np_list_scenarios", "method": "GET", "path": "/node/scenarios", "auth": "none"},
    {"name": "np_propose", "method": "POST", "path": "/exchanges", "auth": "agent"},
    {"name": "np_confirm", "method": "POST", "path": "/exchanges/{exchange_id}/confirm", "auth": "agent"},
]

FORBIDDEN_TOOLS = frozenset({
    "np_admin_settle",
    "np_force_settled",
    "np_bypass_verify",
})


def list_tools() -> list[dict[str, str]]:
    return list(MCP_TOOL_CATALOG)


def fetch_manifest(*, base_url: str, http: Optional[httpx.Client] = None) -> dict[str, Any]:
    """只读：节点 Manifest。"""
    client = http or httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)
    own = http is None
    try:
        r = client.get("/.well-known/novapanda.json")
        r.raise_for_status()
        return r.json()
    finally:
        if own:
            client.close()


def fetch_settlement_rails(*, base_url: str, http: Optional[httpx.Client] = None) -> dict[str, Any]:
    client = http or httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)
    own = http is None
    try:
        r = client.get("/node/settlement/rails")
        r.raise_for_status()
        return r.json()
    finally:
        if own:
            client.close()


def dispatch_readonly(
    tool_name: str,
    *,
    base_url: str,
    http: Optional[httpx.Client] = None,
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """只读工具分发（写路径 MUST 在 MCP 宿主侧带 Agent 签）。"""
    if tool_name in FORBIDDEN_TOOLS:
        raise ValueError(f"forbidden MCP tool: {tool_name}")
    handlers: dict[str, Callable[..., dict[str, Any]]] = {
        "np_manifest": lambda **_: fetch_manifest(base_url=base_url, http=http),
        "np_settlement_rails": lambda **_: fetch_settlement_rails(base_url=base_url, http=http),
    }
    if tool_name == "np_settlement_quote":
        if not params or "amount" not in params or "currency" not in params:
            raise ValueError("np_settlement_quote requires amount and currency")
        client = http or httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)
        own = http is None
        try:
            r = client.get("/node/settlement/quote", params=params)
            r.raise_for_status()
            return r.json()
        finally:
            if own:
                client.close()
    if tool_name == "np_get_exchange":
        eid = (params or {}).get("exchange_id")
        if not eid:
            raise ValueError("np_get_exchange requires exchange_id")
        client = http or httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)
        own = http is None
        try:
            r = client.get(f"/exchanges/{eid}")
            r.raise_for_status()
            return r.json()
        finally:
            if own:
                client.close()
    fn = handlers.get(tool_name)
    if fn is None:
        raise ValueError(f"unknown or write-only tool: {tool_name}")
    return fn()
