"""交换条款摘要与 contract 双签。

双方 MUST 对同一 `terms_hash` 各签一次 `contract_ack`，节点验签通过后
才从 PROPOSED 进入 CONTRACTED——这是陌生人交换的条款锚点。
"""

from __future__ import annotations

from typing import Any

from .canonical import canonical_bytes
from .hashing import sha256_hex
from .identity import Identity, verify


def terms_fields(
    *,
    exchange_id: str,
    client: str,
    provider: str,
    resource_type: str,
    quantity: int,
    rule_id: str,
    price: dict,
    timeouts: dict,
    nonce: str,
    idempotency_key: str,
) -> dict:
    return {
        "exchange_id": exchange_id,
        "client": client,
        "provider": provider,
        "resource_type": resource_type,
        "quantity": quantity,
        "rule_id": rule_id,
        "price": price,
        "timeouts": timeouts,
        "nonce": nonce,
        "idempotency_key": idempotency_key,
    }


def terms_hash_from_exchange(ex: Any) -> str:
    return sha256_hex(canonical_bytes(terms_fields(
        exchange_id=ex.exchange_id,
        client=ex.client,
        provider=ex.provider,
        resource_type=ex.resource_type,
        quantity=ex.quantity,
        rule_id=ex.rule_id,
        price=ex.price,
        timeouts=ex.timeouts,
        nonce=ex.nonce,
        idempotency_key=ex.idempotency_key,
    )))


def terms_hash_from_dict(ex: dict) -> str:
    return sha256_hex(canonical_bytes(terms_fields(
        exchange_id=ex["exchange_id"],
        client=ex["client"],
        provider=ex["provider"],
        resource_type=ex["resource_type"],
        quantity=ex["quantity"],
        rule_id=ex["rule_id"],
        price=ex["price"],
        timeouts=ex.get("timeouts") or {},
        nonce=ex["nonce"],
        idempotency_key=ex["idempotency_key"],
    )))


def contract_ack_bytes(*, terms_hash: str, exchange_id: str) -> bytes:
    return canonical_bytes({
        "action": "contract_ack",
        "exchange_id": exchange_id,
        "terms_hash": terms_hash,
    })


def sign_contract_ack(identity: Identity, ex: Any) -> str:
    th = ex.terms_hash if hasattr(ex, "terms_hash") else ex["terms_hash"]
    eid = ex.exchange_id if hasattr(ex, "exchange_id") else ex["exchange_id"]
    return identity.sign(contract_ack_bytes(terms_hash=th, exchange_id=eid))


def verify_contract_ack(agent_id: str, signature: str, *, terms_hash: str,
                        exchange_id: str) -> bool:
    return verify(agent_id, signature,
                  contract_ack_bytes(terms_hash=terms_hash, exchange_id=exchange_id))
