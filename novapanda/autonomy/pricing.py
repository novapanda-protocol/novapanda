"""动态定价引擎：市场基准 × 复杂度 × 负载 × 声誉折扣。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from novapanda.marketplace.types import PriceQuote, SlaOffer

from .types import PriceQuoteSnapshot, PricingInput


@dataclass
class PricingPolicy:
    token_ref: int = 1_000
    step_ref: int = 5
    alpha_tokens: float = 0.35
    beta_steps: float = 0.25
    lambda_load: float = 0.40
    mu_reputation: float = 0.15  # 高声誉略降价
    base_sla_ms: int = 2_000
    sla_ms_per_step: int = 500
    # DePIN 物理复杂度：电网负荷 + 排队长度
    gamma_grid: float = 0.45
    delta_queue: float = 0.20
    queue_ref: int = 5


@dataclass
class DynamicPricingEngine:
    """轻量定价；纯函数，无 IO。

    Agent Skill: use tool ``novapanda_quote_price`` with integer
    ``benchmark_amount`` and optional ``load_ratio`` / ``token_estimate``.
    DePIN chargers may pass ``grid_load_ratio`` + ``queue_length``.
    Output amounts are integers—never hex gas blobs.
    """

    policy: PricingPolicy = field(default_factory=PricingPolicy)

    def quote(self, inp: PricingInput) -> PriceQuoteSnapshot:
        """Return price + SLA + explainable factors for one bid.

        ``inp.market_benchmark.amount`` is an integer minor-unit price.
        """
        p = self.policy
        load = max(0.0, min(1.0, float(inp.load_ratio)))
        tokens = max(0, int(inp.token_estimate))
        steps = max(1, int(inp.step_estimate))
        grid = max(0.0, min(1.0, float(inp.grid_load_ratio)))
        queue = max(0, int(inp.queue_length))

        c = 1.0 + p.alpha_tokens * math.log1p(tokens / max(1, p.token_ref))
        c += p.beta_steps * (steps / max(1, p.step_ref))
        # 物理复杂度并入 c（电网 + 排队）
        c += p.gamma_grid * grid
        c += p.delta_queue * math.log1p(queue / max(1, p.queue_ref))
        load_f = 1.0 + p.lambda_load * load
        rep = inp.effective_reputation
        if rep is None:
            rep_f = 1.0
        else:
            rep = max(0.0, min(1.0, float(rep)))
            rep_f = 1.0 - p.mu_reputation * rep

        raw = inp.market_benchmark.amount * c * load_f * rep_f
        amount = int(round(raw))
        currency = inp.market_benchmark.currency

        if inp.min_price and inp.min_price.currency == currency:
            amount = max(amount, inp.min_price.amount)
        if inp.max_price and inp.max_price.currency == currency:
            amount = min(amount, inp.max_price.amount)
        amount = max(0, amount)

        sla_ms = p.base_sla_ms + p.sla_ms_per_step * steps
        # 排队拉长 SLA 预期
        sla_ms += int(300 * queue)
        snap = PriceQuoteSnapshot(
            price=PriceQuote(amount=amount, currency=currency),
            sla=SlaOffer(max_response_ms=sla_ms),
            complexity_factor=round(c, 4),
            load_factor=round(load_f, 4),
            reputation_factor=round(rep_f, 4),
            rationale=(
                f"benchmark={inp.market_benchmark.amount}×c={c:.3f}"
                f"×load={load_f:.3f}×rep={rep_f:.3f}"
                f"|grid={grid:.2f}|queue={queue}"
            ),
        )
        return snap
