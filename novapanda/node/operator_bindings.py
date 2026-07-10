"""Operator ↔ Agent 绑定（UC-31 · claim 验签）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..canonical import canonical_bytes
from ..identity import verify


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def operator_claim_payload(
    *,
    agent_id: str,
    operator_id: str,
    node_id: str,
    issued_at: str,
) -> dict[str, Any]:
    return {
        "type": "novapanda.operator_claim",
        "agent_id": agent_id,
        "operator_id": operator_id,
        "node_id": node_id,
        "issued_at": issued_at,
    }


def operator_claim_bytes(payload: dict[str, Any]) -> bytes:
    return canonical_bytes(payload)


@dataclass
class AgentBinding:
    operator_id: str
    agent_id: str
    bound_at: str
    label: str = ""
    claim_sig: str = ""
    issued_at: str = ""


@dataclass
class OperatorBindingRegistry:
    _bindings: list[AgentBinding] = field(default_factory=list)

    def build_claim_payload(
        self,
        *,
        agent_id: str,
        operator_id: str,
        node_id: str,
        issued_at: Optional[str] = None,
    ) -> dict[str, Any]:
        if not agent_id.startswith("ed25519:"):
            raise ValueError("invalid_agent_id")
        ts = issued_at or _now()
        return operator_claim_payload(
            agent_id=agent_id,
            operator_id=operator_id,
            node_id=node_id,
            issued_at=ts,
        )

    def bind(
        self,
        *,
        operator_id: str,
        agent_id: str,
        node_id: str,
        signature: str,
        issued_at: str,
        label: str = "",
    ) -> AgentBinding:
        if not agent_id.startswith("ed25519:"):
            raise ValueError("invalid_agent_id")
        if not signature:
            raise ValueError("signature_required")
        if not issued_at:
            raise ValueError("issued_at_required")
        payload = operator_claim_payload(
            agent_id=agent_id,
            operator_id=operator_id,
            node_id=node_id,
            issued_at=issued_at,
        )
        if not verify(agent_id, signature, operator_claim_bytes(payload)):
            raise ValueError("invalid_claim_signature")
        for b in self._bindings:
            if b.operator_id == operator_id and b.agent_id == agent_id:
                b.claim_sig = signature
                b.issued_at = issued_at
                b.label = label.strip() or b.label
                return b
        rec = AgentBinding(
            operator_id=operator_id,
            agent_id=agent_id,
            bound_at=_now(),
            label=label.strip(),
            claim_sig=signature,
            issued_at=issued_at,
        )
        self._bindings.append(rec)
        return rec

    def unbind(self, *, operator_id: str, agent_id: str) -> bool:
        before = len(self._bindings)
        self._bindings = [
            b for b in self._bindings
            if not (b.operator_id == operator_id and b.agent_id == agent_id)
        ]
        return len(self._bindings) < before

    def list_for_operator(self, operator_id: str) -> list[AgentBinding]:
        return [b for b in self._bindings if b.operator_id == operator_id]

    def agent_ids_for_operator(self, operator_id: str) -> list[str]:
        return [b.agent_id for b in self.list_for_operator(operator_id)]

    def public(self, rec: AgentBinding) -> dict[str, Any]:
        return {
            "operator_id": rec.operator_id,
            "agent_id": rec.agent_id,
            "bound_at": rec.bound_at,
            "label": rec.label,
            "issued_at": rec.issued_at,
            "verified": bool(rec.claim_sig),
        }

    def clear_for_operator(self, operator_id: str) -> int:
        before = len(self._bindings)
        self._bindings = [b for b in self._bindings if b.operator_id != operator_id]
        return before - len(self._bindings)
