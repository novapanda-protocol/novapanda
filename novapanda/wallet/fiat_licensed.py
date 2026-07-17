"""持牌法币合规网关：对接 Stripe 形 PaymentIntent（pay / settle）。

- ``licensed=True``：声明走持牌伙伴通道（与 Stub 的 licensed=False 区分）
- 沙箱密钥仍可能 ``environment=sandbox``；业务层须同时看 licensed + environment
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from .manager import WalletError
from .types import (
    FiatPaymentRequest,
    FiatSettlementRequest,
    FiatStubReceipt,
)


@dataclass
class LicensedFiatComplianceGateway:
    """Stripe/Circle 形合规边界实现（HTTP 可注入；默认内存沙箱模拟）。

    生产：注入真实 ``payment_client``（需 ``authorize``/``capture``/``void`` 或等价）。
    """

    partner: str = "stripe"
    environment: str = "sandbox"  # sandbox | live
    licensed: bool = True
    # duck: authorize(exchange_id, amount, currency) -> ref; capture; void
    payment_client: Any = None
    _ledger: dict[str, dict] = field(default_factory=dict)

    def pay_with_fiat(self, req: FiatPaymentRequest) -> FiatStubReceipt:
        """法币入金：授权并（原型）标记目标资产待铸造/划拨。"""
        if not self.licensed:
            raise WalletError("licensed gateway misconfigured: licensed=False")
        ref = self._authorize(req.idempotency_key, req.amount_minor, req.currency)
        self._ledger[ref] = {
            "op": "pay_with_fiat",
            "agent_id": req.agent_id,
            "amount_minor": req.amount_minor,
            "currency": req.currency,
            "target": req.target_asset.symbol,
            "status": "authorized",
        }
        return FiatStubReceipt(
            operation="pay_with_fiat",
            status="accepted",
            licensed=True,
            partner=self.partner,
            detail=(
                f"{self.environment}: authorized {req.amount_minor} {req.currency} minor "
                f"→ {req.target_asset.symbol} on {req.target_asset.chain.chain_id}"
            ),
            ref=ref,
        )

    def settle_to_fiat(self, req: FiatSettlementRequest) -> FiatStubReceipt:
        """法币出金：捕获/结算到银行引用。"""
        if not self.licensed:
            raise WalletError("licensed gateway misconfigured: licensed=False")
        # 用 asset.amount 作为「链上已锁定」金额；currency 从 asset 链外映射为 USD
        ref = self._authorize(req.idempotency_key, req.amount, "usd")
        if self.payment_client is not None and hasattr(self.payment_client, "capture"):
            self.payment_client.capture(ref)
        elif ref in self._ledger:
            self._ledger[ref]["status"] = "captured"
        else:
            self._ledger[ref] = {
                "op": "settle_to_fiat",
                "agent_id": req.agent_id,
                "amount": req.amount,
                "bank_ref": req.bank_ref,
                "status": "captured",
            }
        return FiatStubReceipt(
            operation="settle_to_fiat",
            status="accepted",
            licensed=True,
            partner=self.partner,
            detail=(
                f"{self.environment}: settled {req.amount} {req.asset.symbol} "
                f"to bank_ref={req.bank_ref}"
            ),
            ref=ref,
        )

    def _authorize(self, idempotency_key: str, amount: int, currency: str) -> str:
        if self.payment_client is not None and hasattr(self.payment_client, "authorize"):
            return self.payment_client.authorize(idempotency_key, amount, currency)
        return f"{self.partner}_{self.environment}_{idempotency_key}"[:64] or (
            f"{self.partner}-" + uuid.uuid4().hex[:16]
        )


def make_fiat_compliance_gateway(
    *,
    mode: str = "stub",
    partner: str = "stripe",
    environment: str = "sandbox",
    payment_client: Any = None,
    api_key: Optional[str] = None,
    fiat_base_url: Optional[str] = None,
    http: Any = None,
) -> Any:
    """工厂：stub（未持牌）| licensed / stripe / circle（持牌）。

    ``mode=stripe`` 且未注入 ``payment_client`` 时，自动构造 ``StripeGateway``
    （读 ``NOVAPANDA_FIAT_API_KEY`` / ``NOVAPANDA_FIAT_URL``）。
    """
    import os

    from .manager import StubFiatComplianceGateway

    m = (mode or "stub").lower()
    if m in ("stub", "unlicensed"):
        return StubFiatComplianceGateway(partner=f"stub-{partner}")
    if m in ("licensed", "stripe", "circle"):
        client = payment_client
        if client is None and m == "stripe":
            from novapanda.stripe_gateway import StripeGateway

            key = api_key or os.environ.get("NOVAPANDA_FIAT_API_KEY")
            base = (
                fiat_base_url
                or os.environ.get("NOVAPANDA_FIAT_URL")
                or "https://api.stripe.com/v1"
            )
            client = StripeGateway(base_url=base, api_key=key, http=http)
        return LicensedFiatComplianceGateway(
            partner=partner if m == "licensed" else m,
            environment=environment,
            licensed=True,
            payment_client=client,
        )
    raise ValueError(f"unknown fiat compliance mode: {mode}")
