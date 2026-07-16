"""零号节点控制台：数据聚合 + HTML 渲染。"""

from __future__ import annotations

from .console_data import (
    collect_node_profile,
    collect_scenarios,
    collect_status,
    exchange_public_detail,
    list_exchanges,
)
from .console_render import (
    render_console,
    render_exchange_detail,
    render_tools_page,
    render_register_page,
    render_login_page,
    render_operator_claims,
    render_claim_detail,
    render_operator_reconcile,
    render_operator_disputes,
    render_operator_dashboard,
    render_operator_agents_ui,
    render_operator_exchanges,
    render_operator_settings,
    render_operator_help,
    render_operator_bundles,
    render_steward_certifications,
)

__all__ = [
    "collect_status",
    "collect_node_profile",
    "collect_scenarios",
    "list_exchanges",
    "exchange_public_detail",
    "render_console",
    "render_dashboard",
    "render_exchange_detail",
    "render_tools_page",
    "render_register_page",
    "render_login_page",
    "render_operator_claims",
    "render_claim_detail",
    "render_operator_reconcile",
    "render_operator_disputes",
    "render_operator_dashboard",
    "render_operator_agents_ui",
    "render_operator_exchanges",
    "render_operator_settings",
    "render_operator_help",
    "render_operator_bundles",
    "render_steward_certifications",
]


def render_dashboard(status, *, admin: bool = False) -> str:
    """向后兼容：仅 status dict 时渲染简版。"""
    profile = {
        "status": status,
        "capabilities": {
            "verifier": "SchemaVerifier",
            "reputation_gate": False,
            "witness_v2": False,
            "federation_v2": False,
            "transports": ["http", "mcp", "a2a", "skill"],
        },
        "discovery": {
            "manifest": {"endpoints": {"transport": ["http"]}},
            "resource_types": [],
            "active_types": [],
            "reserved_types": [],
            "rules": [],
            "rule_count": 0,
            "type_count": 0,
        },
        "reputation": {"total_entries": 0, "unique_agents": 0, "by_outcome": {}, "top_agents": [], "chain_valid": True},
        "exchanges": {"items": status.get("recent") or []},
        "links": {
            "trial": "https://novapanda.io/trial.html",
            "constitution": "https://novapanda.io/constitution.html",
            "spec": "https://github.com/novapanda-protocol/novapanda/blob/main/spec/SPEC.md",
            "github": "https://github.com/novapanda-protocol/novapanda",
        },
    }
    return render_console(profile, admin=admin)
