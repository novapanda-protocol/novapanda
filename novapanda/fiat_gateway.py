"""法币 HTTP 网关客户端（对接持牌支付/清算伙伴的 authorize/capture/void 语义）。"""

from __future__ import annotations

import os
from typing import Optional, Protocol, runtime_checkable

import httpx

from .http_gateway_base import HttpGatewayClient


@runtime_checkable
class PaymentGatewayClient(Protocol):
    def authorize(self, exchange_id: str, amount: int, currency: str) -> str: ...
    def capture(self, ref: str) -> dict: ...
    def void(self, ref: str) -> dict: ...


class HttpFiatGateway(HttpGatewayClient):
    """与 x402/AP2 同形 REST；真实部署时 base URL 指向持牌伙伴 sandbox/生产 API。"""

    def __init__(
        self,
        base_url: str,
        *,
        http: Optional[httpx.Client] = None,
        api_key: Optional[str] = None,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            base_url,
            http=http,
            api_key=api_key,
            max_retries=max_retries,
            rail_name="fiat",
        )


def make_fiat_gateway(
    *,
    base_url: str,
    api_key: Optional[str] = None,
    http: Optional[httpx.Client] = None,
    provider: Optional[str] = None,
) -> PaymentGatewayClient:
    """generic → HttpFiatGateway(/authorize)；stripe → PaymentIntent 适配。"""
    kind = (provider or os.environ.get("NOVAPANDA_FIAT_PROVIDER", "generic")).lower()
    if kind == "stripe":
        from .stripe_gateway import StripeGateway

        return StripeGateway(
            base_url or "https://api.stripe.com/v1",
            http=http,
            api_key=api_key,
        )
    return HttpFiatGateway(base_url, http=http, api_key=api_key)
