"""具身 / DePIN 报价：按挂牌 metadata 注入电网负荷与排队长度。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from novapanda.autonomy.protocols import PricingEngine
from novapanda.autonomy.types import Bid, BidInvitation, PriceQuoteSnapshot, PricingInput
from novapanda.marketplace.protocols import ScoreEngine


@dataclass
class PhysicalListingBidProvider:
    """充电桩 / 物理资源投标：从 listing 物理表读取 grid/queue。"""

    pricing: PricingEngine
    # listing_id → {grid_load_ratio, queue_length, load_ratio}
    physics_by_listing: dict[str, dict] = field(default_factory=dict)
    score_engine: Optional[ScoreEngine] = None
    default_load_ratio: float = 0.2

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
        phys = self.physics_by_listing.get(listing_id or "", {})
        snap: PriceQuoteSnapshot = self.pricing.quote(
            PricingInput(
                resource_type=invitation.resource_type,
                market_benchmark=invitation.max_price,
                load_ratio=float(phys.get("load_ratio", self.default_load_ratio)),
                token_estimate=invitation.token_estimate,
                step_estimate=invitation.step_estimate,
                effective_reputation=rep,
                max_price=invitation.max_price,
                grid_load_ratio=float(phys.get("grid_load_ratio", 0.0)),
                queue_length=int(phys.get("queue_length", 0)),
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
