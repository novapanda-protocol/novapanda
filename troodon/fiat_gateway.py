"""法币 HTTP 网关客户端（对接持牌支付/清算伙伴的 authorize/capture/void 语义）。"""

from __future__ import annotations

from typing import Optional

import httpx

from .http_gateway_base import HttpGatewayClient


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
