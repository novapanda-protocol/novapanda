"""NP-CLAIM-XFER 生产路径演示：发行 → assignment 验签 → redeem。

运行：
  python demo/claim_xfer_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.node.claim_registry import assignment_bytes
from novapanda.node import create_app_from_config
from novapanda.config import NodeConfig


def main() -> None:
    os.environ["NOVAPANDA_AUTH"] = "0"
    os.environ["NOVAPANDA_CLAIM_MODE"] = "production"
    cfg = NodeConfig.from_env()
    app = create_app_from_config(cfg)
    tc = TestClient(app)

    holder = Identity.generate()
    next_hop = Identity.generate()
    vdc_id = "vdc-demo-claim-001"

    issued = tc.post(
        "/node/claims/issue",
        json={"vdc_id": vdc_id, "amount": 1000, "currency": "USD", "holder": holder.agent_id},
    )
    issued.raise_for_status()
    claim = issued.json()["claim"]
    assert claim["mock"] is False
    assert claim["claim_id"].startswith("claim_")
    print("issued", claim["claim_id"], "holder", holder.agent_id[:20] + "…")

    at = "2026-07-09T12:00:00Z"
    nonce = "demo-nonce-1"
    sig = holder.sign(
        assignment_bytes(
            claim_id=claim["claim_id"],
            to_agent_id=next_hop.agent_id,
            nonce=nonce,
            at=at,
        )
    )
    assigned = tc.post(
        "/node/claims/assign",
        json={
            "claim_id": claim["claim_id"],
            "to_agent_id": next_hop.agent_id,
            "nonce": nonce,
            "at": at,
            "signature": sig,
        },
    )
    assigned.raise_for_status()
    after = assigned.json()["claim"]
    assert after["holder_agent_id"] == next_hop.agent_id
    assert len(after["lineage"]) == 1
    print("assigned to", next_hop.agent_id[:20] + "…")

    redeemed = tc.post("/node/claims/redeem", json={"claim_id": claim["claim_id"]})
    redeemed.raise_for_status()
    assert redeemed.json()["claim"]["status"] == "spent"
    print("redeemed status=spent")

    manifest = tc.get("/.well-known/novapanda.json").json()
    profiles = manifest.get("profiles") or manifest.get("features", {}).get("profiles") or []
    assert "NP-CLAIM-XFER" in profiles
    print("manifest profiles include NP-CLAIM-XFER")
    print("\nOK: NP-CLAIM-XFER production path")


if __name__ == "__main__":
    main()
