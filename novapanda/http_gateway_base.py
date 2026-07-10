"""HTTP 结算/网关客户端公共层：API Key、重试、超时。"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from .settlement import SettlementError


class HttpGatewayClient:
    """生产形 HTTP 网关基类（x402/AP2/fiat 共用）。"""

    def __init__(
        self,
        base_url: str,
        *,
        http: Optional[httpx.Client] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "Authorization",
        api_key_prefix: str = "Bearer ",
        timeout: float = 30.0,
        max_retries: int = 2,
        retry_backoff: float = 0.25,
        rail_name: str = "gateway",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.rail_name = rail_name
        self.max_retries = max(0, max_retries)
        self.retry_backoff = retry_backoff
        headers: dict[str, str] = {}
        if api_key:
            headers[api_key_header] = f"{api_key_prefix}{api_key}"
        self._extra_headers = headers
        if http is not None:
            self._http = http
        else:
            self._http = httpx.Client(
                base_url=self.base_url,
                timeout=timeout,
                headers=headers,
            )

    def _request_json(self, method: str, path: str, *, json: Optional[dict] = None) -> dict:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self._http.request(
                    method,
                    path,
                    json=json,
                    headers={**(self._extra_headers or {}), **self._trace_headers()},
                )
                if r.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (attempt + 1))
                    continue
                if r.status_code >= 400:
                    raise SettlementError(
                        f"{self.rail_name} {method} {path} 失败: {r.status_code} {r.text}"
                    )
                data = r.json()
                if not isinstance(data, dict):
                    raise SettlementError(f"{self.rail_name} 响应须为 object: {data!r}")
                return data
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (attempt + 1))
                    continue
                raise SettlementError(f"{self.rail_name} 网络错误: {exc}") from exc
        raise SettlementError(f"{self.rail_name} 请求失败: {last_exc}")

    def _trace_headers(self) -> dict[str, str]:
        from .trace import outbound_headers

        return outbound_headers()

    def authorize(self, exchange_id: str, amount: int, currency: str) -> str:
        data = self._request_json(
            "POST",
            "/authorize",
            json={"exchange_id": exchange_id, "amount": amount, "currency": currency},
        )
        ref = data.get("ref")
        if not ref:
            raise SettlementError(f"{self.rail_name} authorize 响应缺少 ref")
        return str(ref)

    def capture(self, ref: str) -> dict:
        return self._post_action("/capture", ref, "captured")

    def void(self, ref: str) -> dict:
        return self._post_action("/void", ref, "voided")

    def _post_action(self, path: str, ref: str, expected: str) -> dict:
        data = self._request_json("POST", path, json={"ref": ref})
        if data.get("status") != expected:
            raise SettlementError(f"{self.rail_name} {path} 状态异常: {data}")
        return {"handle": ref, "amount": data["amount"], "currency": data["currency"]}
