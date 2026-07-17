"""子任务拍卖：MatchRouter 筛选 + 询价 + 声誉加权决标。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from novapanda.marketplace.match_router import MatchWeights, WeightedMatchRouter
from novapanda.marketplace.protocols import MatchRouter, ScoreEngine, ServiceRegistry
from novapanda.marketplace.types import (
    MatchQuery,
    MatchScoreBreakdown,
    PriceQuote,
    ServiceListing,
)

from .pricing import DynamicPricingEngine
from .protocols import BidProvider, PricingEngine
from .types import (
    AuctionResult,
    Award,
    Bid,
    BidInvitation,
    PriceQuoteSnapshot,
    PricingInput,
    SubTask,
    SubTaskGraph,
    TaskSpec,
)


@dataclass
class LocalPricingBidProvider:
    """用 PricingEngine 为每个候选 listing 生成报价（模拟对手盘响应）。"""

    pricing: PricingEngine
    load_ratio: float = 0.3
    score_engine: Optional[ScoreEngine] = None

    def bid(
        self, invitation: BidInvitation, agent_id: str, listing_id: Optional[str]
    ) -> Optional[Bid]:
        rep = 0.5
        if self.score_engine is not None:
            view = self.score_engine.view(agent_id)
            if view.effective_score is not None:
                rep = float(view.effective_score)
            elif view.score is not None:
                rep = float(view.score)
        snap = self.pricing.quote(
            PricingInput(
                resource_type=invitation.resource_type,
                market_benchmark=invitation.max_price,
                load_ratio=self.load_ratio,
                token_estimate=invitation.token_estimate,
                step_estimate=invitation.step_estimate,
                effective_reputation=rep,
                max_price=invitation.max_price,
            )
        )
        if snap.price.amount > invitation.max_price.amount:
            return None
        if snap.sla.max_response_ms > invitation.max_response_ms:
            return None
        return Bid(
            sub_id=invitation.sub_id,
            agent_id=agent_id,
            listing_id=listing_id,
            quote=snap,
            effective_reputation=rep,
        )


@dataclass
class MarketplaceAuctioneer:
    """联动 Registry 发现 + MatchRouter + BidProvider + ScoreEngine。"""

    registry: ServiceRegistry
    score_engine: ScoreEngine
    bid_provider: BidProvider
    router: MatchRouter = field(default_factory=WeightedMatchRouter)
    weights: MatchWeights = field(default_factory=MatchWeights)

    def hold_auction(self, graph: SubTaskGraph, *, spec: TaskSpec) -> AuctionResult:
        awards: list[Award] = []
        unfilled: list[str] = []
        for sub in graph.tasks:
            award = self._auction_one(sub, spec)
            if award is None:
                unfilled.append(sub.sub_id)
            else:
                awards.append(award)
        reason = "ok" if not unfilled else f"unfilled={len(unfilled)}"
        return AuctionResult(
            goal_id=graph.goal_id,
            awards=tuple(awards),
            unfilled=tuple(unfilled),
            reason=reason,
        )

    def _auction_one(self, sub: SubTask, spec: TaskSpec) -> Optional[Award]:
        query = MatchQuery(
            resource_type=sub.resource_type,
            quantity=1,
            max_price=spec.budget,
            max_response_ms=spec.max_response_ms,
            required_tags=sub.required_tags or spec.required_tags,
            limit=20,
        )
        listings = self.registry.discover(query)
        if not listings:
            return None
        views = self.score_engine.views([lst.agent_id for lst in listings])
        decision = self.router.route(query, listings, views)
        if not decision.ranked:
            return None

        invitation = BidInvitation(
            sub_id=sub.sub_id,
            resource_type=sub.resource_type,
            token_estimate=sub.token_estimate,
            step_estimate=sub.step_estimate,
            max_price=spec.budget,
            max_response_ms=spec.max_response_ms,
            required_tags=sub.required_tags,
        )
        bids: list[tuple[Bid, ServiceListing]] = []
        for cand in decision.ranked:
            bid = self.bid_provider.bid(
                invitation, cand.listing.agent_id, cand.listing.listing_id
            )
            if bid is not None:
                bids.append((bid, cand.listing))
        if not bids:
            return None

        scored: list[tuple[float, Bid, MatchScoreBreakdown]] = []
        w = self.weights.normalized()
        for bid, listing in bids:
            bd = self._score_bid(bid, listing, spec)
            total = (
                w.price * bd.price_score
                + w.reputation * bd.reputation_score
                + w.sla * bd.sla_score
                + w.tags * bd.tag_score
                - bd.risk_penalty
            )
            total = max(0.0, min(1.0, round(total, 4)))
            scored.append(
                (
                    total,
                    bid,
                    MatchScoreBreakdown(
                        total=total,
                        price_score=bd.price_score,
                        sla_score=bd.sla_score,
                        reputation_score=bd.reputation_score,
                        tag_score=bd.tag_score,
                        risk_penalty=bd.risk_penalty,
                    ),
                )
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        best_total, best_bid, best_bd = scored[0]
        runners = tuple(b for _, b, _ in scored[1:3])
        return Award(
            sub_id=sub.sub_id,
            winner=best_bid,
            breakdown=best_bd,
            runners_up=runners,
        )

    def _score_bid(
        self, bid: Bid, listing: ServiceListing, spec: TaskSpec
    ) -> MatchScoreBreakdown:
        max_p = max(1, spec.budget.amount)
        price_score = 1.0 - (bid.quote.price.amount / max_p)
        max_ms = max(1, spec.max_response_ms)
        sla_score = 1.0 - (bid.quote.sla.max_response_ms / max_ms)
        rep = bid.effective_reputation
        tags = set(listing.capability_tags)
        req = set(spec.required_tags)
        tag_score = 1.0 if not req else (1.0 if req.issubset(tags) else 0.0)
        return MatchScoreBreakdown(
            total=0.0,
            price_score=round(max(0.0, price_score), 4),
            sla_score=round(max(0.0, sla_score), 4),
            reputation_score=round(rep, 4),
            tag_score=tag_score,
            risk_penalty=0.0,
        )


def default_auctioneer(
    registry: ServiceRegistry,
    score_engine: ScoreEngine,
    *,
    load_ratio: float = 0.3,
) -> MarketplaceAuctioneer:
    pricing: PricingEngine = DynamicPricingEngine()
    return MarketplaceAuctioneer(
        registry=registry,
        score_engine=score_engine,
        bid_provider=LocalPricingBidProvider(
            pricing=pricing, load_ratio=load_ratio, score_engine=score_engine
        ),
    )
