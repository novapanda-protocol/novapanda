"""独立复验：不依赖任何节点，仅凭 VDC（+可选 deliverable）验真。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from . import vdc as V
from .hashing import result_hash_of_json
from .verifier import SchemaVerifier


def replay_verify(deliverable: Any, verify_result: dict) -> dict:
    """用 VerifyResult.replay_inputs_ref 独立复跑 Schema 验收（与节点结论对照）。"""
    ref = verify_result.get("replay_inputs_ref") or {}
    schema = ref.get("schema_inline")
    if not schema:
        return {"replay_skipped": True, "reason": "replay_inputs_ref 无 schema_inline"}
    rule = {"rule_id": ref.get("rule_id", "?"), "schema": schema}
    vr = SchemaVerifier().verify(deliverable, rule)
    node_passed = verify_result.get("passed")
    return {
        "replay_passed": vr["passed"],
        "matches_node": vr["passed"] == node_passed if node_passed is not None else None,
        "replay_reason": vr.get("reason"),
    }


def reverify(
    doc: dict,
    deliverable: Optional[Any] = None,
    verify_result: Optional[dict] = None,
) -> dict:
    sigs = doc.get("signatures", {})
    checks: dict[str, Any] = {
        "provider_sig_valid": V.verify_provider(doc),
        "client_sig_valid": V.verify_client(doc) if sigs.get("client_sig") else None,
        "settled_valid": V.is_valid_settled(doc),
    }
    if deliverable is not None:
        checks["result_hash_matches"] = (
            result_hash_of_json(deliverable) == doc.get("result_hash")
        )
    if deliverable is not None and verify_result is not None:
        checks["replay"] = replay_verify(deliverable, verify_result)
    return checks


def _all_ok(checks: dict) -> bool:
    for k, v in checks.items():
        if k == "replay" and isinstance(v, dict):
            if v.get("replay_skipped"):
                continue
            if v.get("replay_passed") is False or v.get("matches_node") is False:
                return False
            continue
        if v is False:
            return False
    return True


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="novapanda.reverify")
    parser.add_argument("vdc", help="VDC JSON 文件路径")
    parser.add_argument("--deliverable", help="交付物 JSON 文件路径（可选）")
    parser.add_argument("--verify-result", help="VerifyResult JSON（含 replay_inputs_ref）")
    args = parser.parse_args(argv)

    with open(args.vdc, "r", encoding="utf-8") as f:
        doc = json.load(f)
    deliverable = None
    if args.deliverable:
        with open(args.deliverable, "r", encoding="utf-8") as f:
            deliverable = json.load(f)
    verify_result = None
    if args.verify_result:
        with open(args.verify_result, "r", encoding="utf-8") as f:
            verify_result = json.load(f)

    checks = reverify(doc, deliverable, verify_result)
    ok = _all_ok(checks)
    print(json.dumps({"vdc_id": doc.get("vdc_id"), "checks": checks, "ok": ok},
                     ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
