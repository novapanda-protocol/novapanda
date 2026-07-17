"""链下挂牌缓存与服务注册表（发现层，不进 CORE SM）。"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .types import ListingCommitment, ListingStatus, MatchQuery, ServiceListing


class InMemoryListingCache:
    def __init__(self) -> None:
        self._by_id: dict[str, ServiceListing] = {}

    def upsert(self, listing: ServiceListing) -> None:
        self._by_id[listing.listing_id] = listing

    def get(self, listing_id: str) -> Optional[ServiceListing]:
        return self._by_id.get(listing_id)

    def delete(self, listing_id: str) -> None:
        self._by_id.pop(listing_id, None)

    def find_by_resource(
        self,
        resource_type: str,
        *,
        tags: tuple[str, ...] = (),
        limit: int = 50,
    ) -> list[ServiceListing]:
        req = set(tags)
        out: list[ServiceListing] = []
        for listing in self._by_id.values():
            if listing.resource_type != resource_type:
                continue
            if listing.status != ListingStatus.ACTIVE:
                continue
            if req and not req.issubset(set(listing.capability_tags)):
                continue
            out.append(listing)
            if len(out) >= limit:
                break
        return out


class InMemoryOnChainListingIndex:
    """原型链上索引：内存 commitment（生产换 EVM/Solana 合约）。"""

    def __init__(self) -> None:
        self._items: dict[str, ListingCommitment] = {}

    def publish(self, commitment: ListingCommitment) -> str:
        self._items[commitment.listing_id] = commitment
        return f"anchor:{commitment.listing_id}:{commitment.content_hash[:16]}"

    def get(self, listing_id: str) -> Optional[ListingCommitment]:
        return self._items.get(listing_id)

    def revoke(self, listing_id: str, *, by_agent_id: str) -> None:
        cur = self._items.get(listing_id)
        if cur is None:
            return
        if cur.agent_id != by_agent_id:
            raise PermissionError("only listing owner may revoke on-chain commitment")
        del self._items[listing_id]


class InMemoryServiceRegistry:
    """轻量 Registry：缓存为主，可选同步 commitment 到链上索引。"""

    def __init__(
        self,
        cache: Optional[InMemoryListingCache] = None,
        chain_index: Optional[InMemoryOnChainListingIndex] = None,
        *,
        now_ts: Optional[float] = None,
    ) -> None:
        self.cache = cache or InMemoryListingCache()
        self.chain_index = chain_index
        self._now_ts = now_ts

    def register(self, listing: ServiceListing) -> ServiceListing:
        if listing.status != ListingStatus.ACTIVE:
            listing = replace(listing, status=ListingStatus.ACTIVE)
        self.cache.upsert(listing)
        self._maybe_publish(listing)
        return listing

    def update(self, listing: ServiceListing) -> ServiceListing:
        if self.cache.get(listing.listing_id) is None:
            raise KeyError(listing.listing_id)
        self.cache.upsert(listing)
        self._maybe_publish(listing)
        return listing

    def revoke(self, listing_id: str, *, by_agent_id: str) -> None:
        cur = self.cache.get(listing_id)
        if cur is None:
            return
        if cur.agent_id != by_agent_id:
            raise PermissionError("only listing owner may revoke")
        self.cache.upsert(replace(cur, status=ListingStatus.REVOKED))
        if self.chain_index is not None:
            try:
                self.chain_index.revoke(listing_id, by_agent_id=by_agent_id)
            except KeyError:
                pass

    def get(self, listing_id: str) -> Optional[ServiceListing]:
        return self.cache.get(listing_id)

    def discover(self, query: MatchQuery) -> list[ServiceListing]:
        found = self.cache.find_by_resource(
            query.resource_type,
            tags=query.required_tags,
            limit=max(query.limit * 5, 50),
        )
        out: list[ServiceListing] = []
        for listing in found:
            if listing.price.currency != query.max_price.currency:
                continue
            if listing.price.amount > query.max_price.amount:
                continue
            if listing.sla.max_response_ms > query.max_response_ms:
                continue
            out.append(listing)
        return out[: max(query.limit * 3, query.limit)]

    def _maybe_publish(self, listing: ServiceListing) -> None:
        if self.chain_index is None or not listing.content_hash:
            return
        import time

        now = self._now_ts if self._now_ts is not None else time.time()
        self.chain_index.publish(
            ListingCommitment(
                listing_id=listing.listing_id,
                agent_id=listing.agent_id,
                content_hash=listing.content_hash,
                expires_at_ts=now + listing.ttl_sec,
            )
        )
