"""x402 HTTP 支付网关客户端：对接外部 402 结算服务。

约定 REST API（参考实现 / 测试 fake server 共用）：
  POST {base}/authorize  body: {exchange_id, amount, currency}  -> {ref}
  POST {base}/capture    body: {ref}                            -> {amount, currency, status}
  POST {base}/void       body: {ref}                            -> {amount, currency, status}
"""

from __future__ import annotations

from typing import Optional

import httpx

from .http_gateway_base import HttpGatewayClient


class HttpX402Gateway(HttpGatewayClient):
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
            rail_name="x402",
        )
