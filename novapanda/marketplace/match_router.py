"""参数化撮合 MatchRouter：价格 × SLA × 声誉 × 标签（无自然语言）。

``total = w_price·P + w_sla·S + w_rep·R + w_tag·T − risk_penalty``

各分量 ∈ [0,1]；硬约束不满足的挂牌直接剔除（不进 ranked）。
不调用 ExchangeEngine / state_machine。
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import (
    ListingStatus,
    MatchDecision,
    MatchQuery,
    MatchScoreBreakdown,
    ProviderCandidate,
    ReputationView,
    ServiceListing,
)


@dataclass(frozen=True)
class MatchWeights:
    """多维权重（和不必为 1；实现会按和归一化，便于调参）。"""

    price: float = 0.35
    sla: float = 0.25
    reputation: float = 0.30
    tags: float = 0.10

    def normalized(self) -> "MatchWeights":
        s = self.price + self.sla + self.reputation + self.tags
        if s <= 0:
            raise ValueError("MatchWeights 之和必须 > 0")
        return MatchWeights(
            price=self.price / s,
            sla=self.sla / s,
            reputation=self.reputation / s,
            tags=self.tags / s,
        )


@dataclass
class WeightedMatchRouter:
    """默认撮合器：可解释 breakdown，winner = ranked[0]。"""

    weights: MatchWeights = MatchWeights()
    # 无声誉历史时的中性分（避免新来者永远排不到）
    cold_reputation: float = 0.5

    def route(
        self,
        query: MatchQuery,
        listings: list[ServiceListing],
        views: dict[str, ReputationView],
    ) -> MatchDecision:
        w = self.weights.normalized()
        ranked: list[ProviderCandidate] = []
        skip_reasons: list[str] = []

        for listing in listings:
            ok, reason = self._hard_filters(query, listing, views.get(listing.agent_id))
            if not ok:
                skip_reasons.append(f"{listing.listing_id}:{reason}")
                continue
            view = views.get(listing.agent_id) or _empty_view(listing.agent_id)
            breakdown = self._score(query, listing, view, w)
            ranked.append(
                ProviderCandidate(listing=listing, reputation=view, breakdown=breakdown)
            )

        ranked.sort(key=lambda c: c.breakdown.total, reverse=True)
        if query.limit > 0:
            ranked = ranked[: query.limit]

        winner = ranked[0] if ranked else None
        if winner is None:
            reason = "no eligible providers"
            if skip_reasons:
                reason += f" (filtered: {len(skip_reasons)})"
        else:
            reason = (
                f"winner={winner.listing.agent_id} total={winner.breakdown.total:.4f}"
            )

        return MatchDecision(
            query=query,
            ranked=tuple(ranked),
            winner=winner,
            reason=reason,
        )

    def _hard_filters(
        self,
        query: MatchQuery,
        listing: ServiceListing,
        view: ReputationView | None,
    ) -> tuple[bool, str]:
        if listing.status != ListingStatus.ACTIVE:
            return False, "inactive"
        if listing.resource_type != query.resource_type:
            return False, "resource_type"
        if listing.price.currency != query.max_price.currency:
            return False, "currency"
        if listing.price.amount > query.max_price.amount:
            return False, "price_cap"
        if listing.sla.max_response_ms > query.max_response_ms:
            return False, "sla_latency"
        req = set(query.required_tags)
        if req and not req.issubset(set(listing.capability_tags)):
            return False, "required_tags"
        eff = _effective_rep(view, self.cold_reputation)
        if eff < query.min_reputation:
            return False, "min_reputation"
        return True, ""

    def _score(
        self,
        query: MatchQuery,
        listing: ServiceListing,
        view: ReputationView,
        w: MatchWeights,
    ) -> MatchScoreBreakdown:
        # 价格：越便宜越高；已通过 hard filter，amount ∈ (0, max]
        max_p = max(1, query.max_price.amount)
        price_score = 1.0 - (listing.price.amount / max_p)

        # SLA：响应越快越高
        max_ms = max(1, query.max_response_ms)
        sla_score = 1.0 - (listing.sla.max_response_ms / max_ms)

        rep_score = _effective_rep(view, self.cold_reputation)

        preferred = query.preferred_tags
        if not preferred:
            tag_score = 1.0
        else:
            have = set(listing.capability_tags)
            hit = sum(1 for t in preferred if t in have)
            tag_score = hit / len(preferred)

        risk_penalty = float(view.risk_penalty or 0.0)
        total = (
            w.price * price_score
            + w.sla * sla_score
            + w.reputation * rep_score
            + w.tags * tag_score
            - risk_penalty
        )
        total = max(0.0, min(1.0, round(total, 4)))

        return MatchScoreBreakdown(
            total=total,
            price_score=round(price_score, 4),
            sla_score=round(sla_score, 4),
            reputation_score=round(rep_score, 4),
            tag_score=round(tag_score, 4),
            risk_penalty=round(risk_penalty, 4),
        )


def _effective_rep(view: ReputationView | None, cold: float) -> float:
    if view is None:
        return cold
    if view.effective_score is not None:
        return float(view.effective_score)
    if view.score is not None:
        return float(view.score)
    return cold


def _empty_view(agent_id: str) -> ReputationView:
    return ReputationView(
        agent_id=agent_id,
        score=None,
        entry_count=0,
        settled_count=0,
        rejected_count=0,
    )
