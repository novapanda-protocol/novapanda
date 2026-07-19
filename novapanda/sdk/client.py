"""NovaPanda SDK 客户端：在**本地**构造与签名 VDC，私钥从不上送节点。

降低接入难度的最薄一层：任何持有 agent 身份的程序都能用它完成交割；
它对节点而言是无状态的，节点只接收签名结果并校验。
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .. import vdc as V
from ..auth import sign_request
from ..terms import sign_contract_ack
from ..hashing import result_hash_of_json
from ..identity import Identity


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class NovaPandaClient:
    def __init__(self, base_url: str, identity: Identity, *, http: Optional[httpx.Client] = None):
        self.base_url = base_url.rstrip("/")
        self.identity = identity
        self._http = http or httpx.Client(base_url=self.base_url)

    @property
    def agent_id(self) -> str:
        return self.identity.agent_id

    def _post(self, path: str, json_body: Optional[dict] = None) -> dict:
        body = json.dumps(json_body or {}).encode("utf-8")
        nonce = secrets.token_hex(16)
        headers = {
            "Content-Type": "application/json",
            "X-Agent-Id": self.agent_id,
            "X-Nonce": nonce,
            "X-Signature": sign_request(self.identity, "POST", path, nonce, body),
        }
        r = self._http.post(path, content=body, headers=headers)
        r.raise_for_status()
        return r.json()

    def _get(self, path: str) -> dict:
        r = self._http.get(path)
        r.raise_for_status()
        return r.json()

    # --- client 侧 ---
    def propose(self, *, provider: str, resource_type: str, quantity: int,
                rule_id: str, price: dict, idempotency_key: str,
                timeouts: Optional[dict] = None,
                settlement: Optional[dict] = None) -> dict:
        body = {
            "client": self.agent_id, "provider": provider,
            "resource_type": resource_type, "quantity": quantity,
            "rule_id": rule_id, "price": price, "idempotency_key": idempotency_key,
            "timeouts": timeouts,
        }
        if settlement is not None:
            body["settlement"] = settlement
        return self._post("/exchanges", body)

    def contract(self, exchange_id: str) -> dict:
        ex = self.get_exchange(exchange_id)
        sig = sign_contract_ack(self.identity, ex)
        return self._post(f"/exchanges/{exchange_id}/contract", {"signature": sig})

    def escrow(self, exchange_id: str, *, amount: int, currency: str) -> dict:
        return self._post(f"/exchanges/{exchange_id}/escrow",
                          {"amount": amount, "currency": currency})

    def get_exchange(self, exchange_id: str) -> dict:
        return self._get(f"/exchanges/{exchange_id}")

    def verify(self, exchange_id: str) -> dict:
        return self._post(f"/exchanges/{exchange_id}/verify")

    def confirm(self, exchange_id: str) -> dict:
        """client 在本地为 provider 已签的 VDC 补 client_sig，再回传节点结算。"""
        ex = self.get_exchange(exchange_id)
        doc = ex["vdc"]
        if doc is None:
            raise RuntimeError("Exchange 尚无 VDC，无法 confirm")
        if doc["parties"]["client"] != self.agent_id:
            raise RuntimeError("当前身份不是该交换的 client")
        V.client_sign(doc, self.identity)
        return self._post(f"/exchanges/{exchange_id}/confirm", {"vdc": doc})

    def dispute(self, exchange_id: str, *, reason: str) -> dict:
        return self._post(f"/exchanges/{exchange_id}/dispute", {"reason": reason})

    def export_exchange(self, exchange_id: str) -> dict:
        """导出交换包。deliverable 仅当请求鉴权身份为当事方时由节点附带。"""
        return self._get(f"/exchanges/{exchange_id}/export")

    # --- provider 侧 ---
    def deliver(self, exchange_id: str, deliverable: Any, *,
                evidence_level: str = "dual_signed") -> dict:
        """provider 在本地构造并签名 VDC，再连同 deliverable 提交节点。"""
        ex = self.get_exchange(exchange_id)
        if ex["provider"] != self.agent_id:
            raise RuntimeError("当前身份不是该交换的 provider")
        doc = V.build_vdc(
            client=ex["client"], provider=ex["provider"],
            resource_type=ex["resource_type"], quantity=ex["quantity"],
            result_hash=result_hash_of_json(deliverable),
            rule_id=ex["rule_id"], evidence_level=evidence_level,
            started_at=_now_iso(), finished_at=_now_iso(),
            idempotency_key=ex["idempotency_key"], nonce=ex["nonce"],
            state="DELIVERED",
        )
        V.provider_sign(doc, self.identity)
        return self._post(f"/exchanges/{exchange_id}/deliver",
                          {"vdc": doc, "deliverable": deliverable})

    def reputation(self, agent_id: str) -> dict:
        return self._get(f"/reputation/{agent_id}")
