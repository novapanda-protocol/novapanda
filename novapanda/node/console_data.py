"""零号节点控制台 — 数据聚合（只读、不含密钥）。"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..privacy import privacy_manifest_block
from ..state_machine import TERMINAL_STATES

# docs/scenarios/catalog.json — 与开源场景同源；找不到时降级为空目录
_CATALOG_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "docs" / "scenarios" / "catalog.json",
)


def load_scenario_catalog() -> dict[str, Any]:
    for path in _CATALOG_CANDIDATES:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_path"] = str(path)
            return data
    return {
        "protocol": "novapanda",
        "version": "0",
        "scenarios": [],
        "error": "catalog.json not found",
        "_path": None,
    }


def collect_scenarios() -> dict[str, Any]:
    catalog = load_scenario_catalog()
    scenarios = list(catalog.get("scenarios") or [])
    by_status: Counter[str] = Counter(str(s.get("status") or "unknown") for s in scenarios)
    by_tier: Counter[str] = Counter(str(s.get("tier") or "unknown") for s in scenarios)
    bundles = [s for s in scenarios if s.get("bundle")]
    return {
        "catalog_version": catalog.get("version"),
        "updated": catalog.get("updated"),
        "title": catalog.get("title_zh") or catalog.get("title"),
        "source": catalog.get("source") or "docs/scenarios/catalog.json",
        "path": catalog.get("_path"),
        "total": len(scenarios),
        "by_status": dict(by_status),
        "by_tier": dict(by_tier),
        "bundle_count": len(bundles),
        "scenarios": scenarios,
        "figures": catalog.get("figures") or {},
        "error": catalog.get("error"),
    }


def _short(text: str, n: int = 28) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _exchange_row(ex) -> dict[str, Any]:
    return {
        "exchange_id": ex.exchange_id,
        "state": ex.state,
        "client": ex.client,
        "provider": ex.provider,
        "resource_type": ex.resource_type,
        "quantity": ex.quantity,
        "rule_id": ex.rule_id,
        "price": ex.price,
        "updated_at": ex.updated_at,
        "created_at": getattr(ex, "created_at", ex.updated_at),
        "vdc_id": getattr(ex, "vdc_id", None),
        "terminal": ex.state in TERMINAL_STATES,
    }


def collect_status(*, engine, app_state) -> dict[str, Any]:
    exchanges = list(engine._store.values())
    by_state = Counter(ex.state for ex in exchanges)
    settled = by_state.get("SETTLED", 0)
    settlement_cls = type(engine._settlement).__name__
    settlement = settlement_cls.replace("Settlement", "").lower() or "unknown"
    settlement_env = getattr(engine._settlement, "environment", "mock" if settlement == "mock" else "production")
    partner = getattr(engine._settlement, "partner", None)
    recent = sorted(exchanges, key=lambda ex: ex.updated_at, reverse=True)[:20]
    return {
        "service": "novapanda-node",
        "protocol": "novapanda",
        "version": "0.0.1",
        "node_id": app_state.node_id,
        "settlement": settlement,
        "settlement_environment": settlement_env,
        "settlement_partner": partner,
        "auth_enabled": bool(app_state.auth_enabled),
        "exchange_total": len(exchanges),
        "settled_total": settled,
        "success_rate": round(settled / len(exchanges), 3) if exchanges else None,
        "by_state": dict(sorted(by_state.items())),
        "recent": [_exchange_row(ex) for ex in recent],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def collect_capabilities(*, engine, app_state) -> dict[str, Any]:
    settlement_cls = type(engine._settlement).__name__.replace("Settlement", "").lower() or "unknown"
    settlement_env = getattr(
        engine._settlement,
        "environment",
        "mock" if settlement_cls == "mock" else "production",
    )
    return {
        "auth": bool(app_state.auth_enabled),
        "settlement": settlement_cls,
        "settlement_environment": settlement_env,
        "settlement_partner": getattr(engine._settlement, "partner", None),
        "verifier": type(engine._verifier).__name__,
        "witness_v2": bool(getattr(app_state, "witness_v2_enabled", False)),
        "federation_v2": bool(getattr(app_state, "federation_v2_enabled", False)),
        "reputation_gate": app_state.reputation_min_score is not None,
        "reputation_min_score": app_state.reputation_min_score,
        "arbitrator": app_state.arbitrator_id,
        "transports": ["http", "mcp", "a2a", "skill"],
        "default_timeouts": dict(app_state.default_timeouts or {}),
    }


def collect_discovery(*, ontology, rules, manifest: dict[str, Any]) -> dict[str, Any]:
    types = ontology.list()
    rule_list = rules.list()
    active_types = [t for t in types if not t.get("reserved")]
    reserved_types = [t for t in types if t.get("reserved")]
    return {
        "manifest": manifest,
        "resource_types": types,
        "active_types": active_types,
        "reserved_types": reserved_types,
        "rules": rule_list,
        "rule_count": len(rule_list),
        "type_count": len(types),
    }


def collect_reputation_summary(*, reputation) -> dict[str, Any]:
    entries = reputation._store.all()
    by_agent: Counter[str] = Counter()
    by_outcome: Counter[str] = Counter()
    for ent in entries:
        by_agent[ent["agent_id"]] += 1
        by_outcome[ent.get("outcome", "unknown")] += 1
    top_agents = [{"agent_id": aid, "entries": count} for aid, count in by_agent.most_common(12)]
    chain_ok = reputation.verify_chain() if entries else True
    return {
        "total_entries": len(entries),
        "unique_agents": len(by_agent),
        "by_outcome": dict(by_outcome),
        "top_agents": top_agents,
        "chain_valid": chain_ok,
    }


def list_exchanges(
    *,
    engine,
    limit: int = 50,
    offset: int = 0,
    state: Optional[str] = None,
    agent_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    items = list(engine._store.values())
    if state:
        items = [ex for ex in items if ex.state == state]
    if agent_ids:
        allowed = set(agent_ids)
        items = [
            ex for ex in items
            if ex.client in allowed or ex.provider in allowed
        ]
    items.sort(key=lambda ex: ex.updated_at, reverse=True)
    total = len(items)
    page = items[offset : offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_exchange_row(ex) for ex in page],
    }


def settlement_rail_stressed(*, engine, settlement) -> bool:
    """全局结算轨是否异常（UC-24 · F-rail 横幅）。"""
    from .rb04 import scan_settlement_health

    health = scan_settlement_health(engine=engine, settlement=settlement)
    return bool(health.get("stale_pending")) or int(health.get("held_escrow_count") or 0) > 0


def exchange_public_detail(
    *,
    engine,
    exchange_id: str,
    dispute_ticket: Optional[dict] = None,
    settlement_rail_down: bool = False,
) -> Optional[dict[str, Any]]:
    try:
        ex = engine.get(exchange_id)
    except Exception:
        return None
    row = _exchange_row(ex)
    row.update(
        {
            "timeouts": ex.timeouts,
            "terms_hash": ex.terms_hash,
            "nonce": ex.nonce,
            "idempotency_key": ex.idempotency_key,
            "verify_result": getattr(ex, "verify_result", None),
            "settlement_receipt": getattr(ex, "settlement_receipt", None),
            "has_vdc": bool(getattr(ex, "vdc_id", None) or getattr(ex, "vdc", None)),
            "dispute_info": getattr(ex, "dispute_info", None),
        }
    )
    if dispute_ticket:
        row["dispute_ticket"] = dispute_ticket
    if settlement_rail_down:
        row["settlement_rail_down"] = True
    vdc_id = getattr(ex, "vdc_id", None)
    if vdc_id:
        row["vdc_lookup"] = f"/vdc/{vdc_id}"
    tc = getattr(ex, "trace_context", None)
    if tc:
        from ..trace import attach_trace_extensions

        row = attach_trace_extensions(row, tc)
    return row


def build_node_manifest(
    *,
    app_state,
    engine,
    ontology,
    rules,
    base_url: str,
) -> dict[str, Any]:
    """节点级 manifest（发现用；Agent manifest 见 SPEC §12.1）。"""
    settlement = type(engine._settlement).__name__.replace("Settlement", "").lower()
    settlement_rail = getattr(engine._settlement, "rail", settlement)
    settlement_env = getattr(engine._settlement, "environment", "mock" if settlement == "mock" else "production")
    types = ontology.list()
    rule_list = rules.list()
    capabilities = []
    for t in types:
        if t.get("reserved"):
            continue
        matching = [r["rule_id"] for r in rule_list if r.get("resource_type") == t["type_id"]]
        capabilities.append(
            {
                "resource_type": t["type_id"],
                "rules": matching,
                "unit": t.get("unit"),
                "description": t.get("description"),
            }
        )
    base = base_url.rstrip("/")
    profiles = list(
        getattr(app_state, "node_profiles", None)
        or ["NP-MIN", "NP-NODE", "NP-SETTLE", "NP-DELEGATE", "NP-PRIV", "NP-LITE"]
    )
    return {
        "protocol": "novapanda",
        "version": "0.0.1",
        "kind": "node",
        "node_id": app_state.node_id,
        "operator": "北京青合数智科技有限公司",
        "settlement": settlement,
        "mock_trial": settlement in ("mock", "sandbox") or settlement_env == "sandbox",
        "terms_url": "https://novapanda.io/terms.html",
        "privacy_url": "https://novapanda.io/privacy.html",
        "endpoints": {
            "exchange": base,
            "console": f"{base}/",
            "health": f"{base}/health",
            "openapi": f"{base}/docs",
            "manifest": f"{base}/.well-known/novapanda.json",
            "node_info": f"{base}/node/info",
            "transport": ["http", "mcp", "a2a", "skill"],
        },
        "capabilities": capabilities,
        "resource_types": [t["type_id"] for t in types],
        "features": {
            "auth": bool(app_state.auth_enabled),
            "reputation": True,
            "reputation_gate": app_state.reputation_min_score is not None,
            "witness_v2": bool(getattr(app_state, "witness_v2_enabled", False)),
            "federation_v2": bool(getattr(app_state, "federation_v2_enabled", False)),
            "marketplace": bool(getattr(app_state, "marketplace_enabled", False)),
            "did_registry": True,
            "iso15118_adapter": True,
            "scenarios_catalog": True,
            "access_policy": getattr(app_state, "access_policy", "open_quota"),
            "profiles": profiles,
            "claim_mock_only": not bool(getattr(app_state, "claim_production", False)),
        },
        "profiles": profiles,
        "delegation": {
            "supported": "NP-DELEGATE" in profiles,
            "max_ttl_seconds": 86400,
            "payment_constraints": True,
        },
        "privacy": privacy_manifest_block() if "NP-PRIV" in profiles else None,
        "lite": {
            "tier": "edge",
            "canonical": "novapanda-c1",
            "offline_queue": True,
        } if "NP-LITE" in profiles else None,
        "physical": {
            "types": ["energy.electric.dc", "actuation.robot.task"],
            "note": "ISO15118 adapter — not CORE state machine",
        }
        if "NP-PHYS" in profiles
        else None,
        "settlement_detail": (
            app_state.rail_registry.manifest_block()
            if getattr(app_state, "rail_registry", None) is not None
            else {
                "default_rail": settlement_rail,
                "rails": [
                    (
                        engine._settlement.manifest_rail()
                        if hasattr(engine._settlement, "manifest_rail")
                        else {
                            "id": settlement_rail,
                            "currencies": ["USD"],
                            "finality": "instant" if settlement == "mock" else "t+1",
                            "licensed": bool(getattr(engine._settlement, "licensed", False)),
                            "environment": settlement_env,
                            **(
                                {"partner": engine._settlement.partner}
                                if getattr(engine._settlement, "partner", None)
                                else {}
                            ),
                        }
                    )
                ],
            }
        ),
        "profile_gate_warnings": list(getattr(app_state, "profile_gate_warnings", []) or []),
    }


def collect_node_profile(*, engine, app_state, ontology, rules, base_url: str) -> dict[str, Any]:
    manifest = build_node_manifest(
        app_state=app_state, engine=engine, ontology=ontology, rules=rules, base_url=base_url,
    )
    status = collect_status(engine=engine, app_state=app_state)
    caps = collect_capabilities(engine=engine, app_state=app_state)
    discovery = collect_discovery(ontology=ontology, rules=rules, manifest=manifest)
    reputation = collect_reputation_summary(reputation=app_state.reputation)
    scenarios = collect_scenarios()
    return {
        "status": status,
        "capabilities": caps,
        "discovery": discovery,
        "reputation": reputation,
        "exchanges": list_exchanges(engine=engine, limit=100),
        "scenarios": scenarios,
        "operator_policy": getattr(app_state, "operators", None).policy_snapshot()
        if getattr(app_state, "operators", None)
        else {},
        "links": {
            "spec": "https://github.com/novapanda-protocol/novapanda/blob/main/spec/SPEC.md",
            "trial": "https://novapanda.io/trial.html",
            "constitution": "https://novapanda.io/constitution.html",
            "scenarios": "https://novapanda.io/scenarios/overview.html",
            "github": "https://github.com/novapanda-protocol/novapanda",
        },
    }
