"""DID 文档注册表：resolve 时验签并返回 verificationMethod。"""

from __future__ import annotations

from typing import Optional

from .did import did_to_agent_id, validate_did_document


class DidRegistry:
    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}

    def register(self, document: dict) -> dict:
        errors = validate_did_document(document)
        if errors:
            raise ValueError("; ".join(errors))
        did = document["id"]
        self._docs[did] = document
        return {"did": did, "agent_id": did_to_agent_id(did), "registered": True}

    def get(self, did: str) -> Optional[dict]:
        return self._docs.get(did)

    def resolve(self, did: str) -> dict:
        doc = self._docs.get(did)
        agent_id = did_to_agent_id(did)
        if doc is None:
            return {
                "did": did,
                "agent_id": agent_id,
                "document": None,
                "public_key_b64url": None,
                "resolved_via": "id_mapping",
            }
        vm = doc["verificationMethod"][0]
        return {
            "did": did,
            "agent_id": agent_id,
            "document": doc,
            "public_key_b64url": vm.get("publicKeyBase64url"),
            "resolved_via": "document",
        }
