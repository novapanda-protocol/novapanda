"""跨节点 Listing 联邦：导出 / 校验 / 导入挂牌包（旁路，不进 CORE）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from novapanda.canonical import canonical_bytes
from novapanda.hashing import sha256_hex
from novapanda.identity import Identity

from .protocols import ServiceRegistry
from .types import ListingStatus, PriceQuote, ServiceListing, SlaOffer

BUNDLE_VERSION = "0.1-listings"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def listing_to_dict(listing: ServiceListing) -> dict:
    return {
        "listing_id": listing.listing_id,
        "agent_id": listing.agent_id,
        "resource_type": listing.resource_type,
        "capability_tags": list(listing.capability_tags),
        "sla": {
            "max_response_ms": listing.sla.max_response_ms,
            "min_throughput_qps": listing.sla.min_throughput_qps,
            "availability_bips": listing.sla.availability_bips,
            "verify_backend_hint": listing.sla.verify_backend_hint,
        },
        "price": {
            "amount": listing.price.amount,
            "currency": listing.price.currency,
            "unit": listing.price.unit,
        },
        "endpoints": dict(listing.endpoints),
        "status": listing.status.value,
        "rule_id_hint": listing.rule_id_hint,
        "content_hash": listing.content_hash,
        "ttl_sec": listing.ttl_sec,
        "metadata": dict(listing.metadata),
    }


def listing_from_dict(d: dict) -> ServiceListing:
    sla = d.get("sla") or {}
    price = d.get("price") or {}
    return ServiceListing(
        listing_id=d["listing_id"],
        agent_id=d["agent_id"],
        resource_type=d["resource_type"],
        capability_tags=tuple(d.get("capability_tags") or ()),
        sla=SlaOffer(
            max_response_ms=int(sla.get("max_response_ms") or 5000),
            min_throughput_qps=int(sla.get("min_throughput_qps") or 0),
            availability_bips=int(sla.get("availability_bips") or 9900),
            verify_backend_hint=sla.get("verify_backend_hint"),
        ),
        price=PriceQuote(
            amount=int(price["amount"]),
            currency=str(price.get("currency") or "USD"),
            unit=str(price.get("unit") or "per_exchange"),
        ),
        endpoints=dict(d.get("endpoints") or {}),
        status=ListingStatus(d.get("status") or "active"),
        rule_id_hint=d.get("rule_id_hint"),
        content_hash=d.get("content_hash"),
        ttl_sec=int(d.get("ttl_sec") or 3600),
        metadata=dict(d.get("metadata") or {}),
    )


def build_listing_bundle(
    *,
    source_node_id: str,
    listings: list[ServiceListing],
    node_identity: Optional[Identity] = None,
) -> dict:
    body = {
        "bundle_version": BUNDLE_VERSION,
        "kind": "listing_federation",
        "source_node_id": source_node_id,
        "exported_at": _now_iso(),
        "listings": [listing_to_dict(x) for x in listings if x.status == ListingStatus.ACTIVE],
    }
    body["bundle_hash"] = "sha256:" + sha256_hex(canonical_bytes(
        {k: v for k, v in body.items() if k != "signature"}
    ))
    if node_identity is not None:
        body["signature"] = node_identity.sign(
            canonical_bytes({k: v for k, v in body.items() if k != "signature"})
        )
    return body


def validate_listing_bundle(bundle: dict) -> list[str]:
    errs: list[str] = []
    if bundle.get("kind") != "listing_federation":
        errs.append("kind must be listing_federation")
    if bundle.get("bundle_version") != BUNDLE_VERSION:
        errs.append(f"unsupported bundle_version: {bundle.get('bundle_version')}")
    if not bundle.get("source_node_id"):
        errs.append("missing source_node_id")
    listings = bundle.get("listings")
    if not isinstance(listings, list):
        errs.append("listings must be array")
        return errs
    for i, item in enumerate(listings):
        try:
            listing_from_dict(item)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"listings[{i}]: {exc}")
    return errs


def import_listing_bundle(
    registry: ServiceRegistry,
    bundle: dict,
    *,
    mirror_prefix: bool = True,
) -> list[ServiceListing]:
    """导入外节点挂牌；可选改写 listing_id 防冲突。"""
    errs = validate_listing_bundle(bundle)
    if errs:
        raise ValueError("; ".join(errs))
    source = bundle["source_node_id"]
    imported: list[ServiceListing] = []
    for item in bundle["listings"]:
        listing = listing_from_dict(item)
        meta = dict(listing.metadata)
        meta["import_kind"] = "mirror"
        meta["source_node_id"] = source
        lid = listing.listing_id
        if mirror_prefix:
            lid = f"fed:{source[-12:]}:{listing.listing_id}"
        listing = ServiceListing(
            listing_id=lid,
            agent_id=listing.agent_id,
            resource_type=listing.resource_type,
            capability_tags=listing.capability_tags,
            sla=listing.sla,
            price=listing.price,
            endpoints=listing.endpoints,
            status=ListingStatus.ACTIVE,
            rule_id_hint=listing.rule_id_hint,
            content_hash=listing.content_hash,
            ttl_sec=listing.ttl_sec,
            metadata=meta,
        )
        registry.register(listing)
        imported.append(listing)
    return imported
