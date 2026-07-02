"""跨节点信誉加权聚合 v2 占位。"""

from __future__ import annotations

from typing import Optional

from .federation import validate_reputation_bundle

AGGREGATE_VERSION = "0.2-placeholder"


def aggregate_reputation_bundles(
    bundles: list[dict],
    *,
    weights: Optional[dict[str, float]] = None,
) -> dict:
    """对多个外链 bundle 做加权汇总（只读分析，不写账本）。"""
    weights = weights or {}
    errors: list[str] = []
    for i, bundle in enumerate(bundles):
        errs = validate_reputation_bundle(bundle)
        if errs:
            errors.append(f"bundle[{i}]: " + "; ".join(errs))
    if errors:
        return {"valid": False, "errors": errors, "agents": {}}

    agents: dict[str, dict] = {}
    for bundle in bundles:
        source = bundle["source_node_id"]
        w = float(weights.get(source, 1.0))
        for entry in bundle["entries"]:
            aid = entry["agent_id"]
            bucket = agents.setdefault(
                aid,
                {"settled": 0.0, "rejected": 0.0, "sources": {}},
            )
            outcome = entry.get("outcome")
            if outcome == "settled":
                bucket["settled"] += w
            elif outcome == "rejected":
                bucket["rejected"] += w
            src = bucket["sources"].setdefault(source, {"settled": 0, "rejected": 0})
            if outcome in src:
                src[outcome] += 1

    for bucket in agents.values():
        total = bucket["settled"] + bucket["rejected"]
        bucket["score"] = round(bucket["settled"] / total, 4) if total else None

    return {
        "valid": True,
        "errors": [],
        "aggregate_version": AGGREGATE_VERSION,
        "bundle_count": len(bundles),
        "agents": agents,
    }


def score_agent_from_ledger(
    entries: list[dict],
    agent_id: str,
    *,
    weights: Optional[dict[str, float]] = None,
) -> dict:
    """从本地账本（含 mirror 导入）计算 agent 加权 score。"""
    weights = weights or {}
    matched = [e for e in entries if e.get("agent_id") == agent_id]
    settled = rejected = 0.0
    sources: dict[str, dict] = {}
    for entry in matched:
        source = (
            (entry.get("external_ref") or {}).get("source_node_id")
            or entry.get("node_id")
        )
        w = float(weights.get(source, 1.0))
        outcome = entry.get("outcome")
        if outcome == "settled":
            settled += w
        elif outcome == "rejected":
            rejected += w
        bucket = sources.setdefault(source, {"settled": 0, "rejected": 0, "weight": w})
        if outcome in ("settled", "rejected"):
            bucket[outcome] += 1
    total = settled + rejected
    return {
        "agent_id": agent_id,
        "entry_count": len(matched),
        "weighted_settled": settled,
        "weighted_rejected": rejected,
        "score": round(settled / total, 4) if total else None,
        "sources": sources,
        "score_version": AGGREGATE_VERSION,
    }
