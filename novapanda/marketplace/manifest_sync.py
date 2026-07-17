"""Agent Manifest ``capabilities`` → ``ServiceListing`` 投影（NP-REP）。"""

from __future__ import annotations

from typing import Any, Optional

from novapanda.hashing import sha256_hex
from novapanda.manifest import manifest_agent_id, verify_agent_manifest

from .protocols import ServiceRegistry
from .types import ListingStatus, PriceQuote, ServiceListing, SlaOffer


def listing_id_for(agent_id: str, resource_type: str, rule_id: Optional[str]) -> str:
    rid = rule_id or "_"
    return f"lst-{sha256_hex(f'{agent_id}|{resource_type}|{rid}'.encode())[:16]}"


def content_hash_for(listing_fields: dict) -> str:
    from novapanda.canonical import canonical_bytes

    return "sha256:" + sha256_hex(canonical_bytes(listing_fields))


def listings_from_agent_manifest(
    manifest: dict,
    *,
    default_sla_ms: int = 5_000,
    default_price: Optional[PriceQuote] = None,
    exchange_endpoint: Optional[str] = None,
) -> list[ServiceListing]:
    """从已验签（或调用方自证）的 Agent Manifest 投影挂牌列表。

    能力条目约定（与现有 C7 示例对齐）::

        {"resource_type": "...", "rules": ["R1"], "price": {"amount": 100, "currency": "USD"},
         "tags": ["ocr"], "sla_ms": 200}
    """
    if not verify_agent_manifest(manifest):
        raise ValueError("agent manifest 验签失败，拒绝投影挂牌")

    agent_id = manifest_agent_id(manifest)
    endpoints = dict(manifest.get("endpoints") or {})
    if exchange_endpoint:
        endpoints["exchange"] = exchange_endpoint
    elif "exchange" not in endpoints:
        endpoints["exchange"] = ""

    fallback_price = default_price or PriceQuote(amount=0, currency="USD")
    out: list[ServiceListing] = []
    for cap in manifest.get("capabilities") or []:
        if not isinstance(cap, dict):
            continue
        resource_type = cap.get("resource_type")
        if not resource_type:
            continue
        rules = cap.get("rules") or []
        rule_id = rules[0] if rules else None
        price_raw = cap.get("price") or {}
        if isinstance(price_raw, dict) and "amount" in price_raw:
            price = PriceQuote(
                amount=int(price_raw["amount"]),
                currency=str(price_raw.get("currency") or fallback_price.currency),
            )
        else:
            price = fallback_price
        tags = tuple(cap.get("tags") or ())
        sla_ms = int(cap.get("sla_ms") or default_sla_ms)
        lid = listing_id_for(agent_id, resource_type, rule_id)
        fields = {
            "listing_id": lid,
            "agent_id": agent_id,
            "resource_type": resource_type,
            "rule_id_hint": rule_id,
            "price": {"amount": price.amount, "currency": price.currency},
            "sla_ms": sla_ms,
            "tags": list(tags),
        }
        out.append(
            ServiceListing(
                listing_id=lid,
                agent_id=agent_id,
                resource_type=resource_type,
                capability_tags=tags,
                sla=SlaOffer(max_response_ms=sla_ms),
                price=price,
                endpoints=endpoints,
                status=ListingStatus.ACTIVE,
                rule_id_hint=rule_id,
                content_hash=content_hash_for(fields),
                metadata={"source": "agent_manifest"},
            )
        )
    return out


def sync_manifest_to_registry(
    registry: ServiceRegistry,
    manifest: dict,
    **kwargs: Any,
) -> list[ServiceListing]:
    """投影并 ``register`` 到 Registry；返回写入的挂牌。"""
    listings = listings_from_agent_manifest(manifest, **kwargs)
    for listing in listings:
        registry.register(listing)
    return listings
