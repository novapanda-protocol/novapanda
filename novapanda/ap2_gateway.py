"""AP2 HTTP 支付网关客户端（与 x402 同形 REST，便于对接 Agent Payments Protocol 网关）。"""

from __future__ import annotations

from typing import Optional

import httpx

from .http_gateway_base import HttpGatewayClient


class HttpAP2Gateway(HttpGatewayClient):
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
            rail_name="ap2",
        )
