"""Stripe PaymentIntent 网关：authorize≈PI 确认至 requires_capture，capture/cancel≈结算。

测试：配合 `stripe_fake.create_stripe_fake_app()`；生产：`NOVAPANDA_FIAT_PROVIDER=stripe` +
`NOVAPANDA_FIAT_API_KEY=sk_test_…`（不进 git）。
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .settlement import SettlementError


class StripeGateway:
    """映射 NovaPanda escrow/settle/refund → Stripe PaymentIntent。"""

    rail_name = "stripe"

    def __init__(
        self,
        base_url: str = "https://api.stripe.com/v1",
        *,
        http: Optional[httpx.Client] = None,
        api_key: Optional[str] = None,
        test_payment_method: Optional[str] = None,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(0, max_retries)
        self.test_payment_method = (
            test_payment_method
            or os.environ.get("NOVAPANDA_STRIPE_TEST_PM")
            or "pm_card_visa"
        )
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if http is not None:
            self._http = http
        else:
            self._http = httpx.Client(base_url=self.base_url, timeout=30.0, headers=headers)

    def authorize(self, exchange_id: str, amount: int, currency: str) -> str:
        fields = {
            "amount": str(amount),
            "currency": currency.lower(),
            "capture_method": "manual",
            "confirm": "true",
            "payment_method": self.test_payment_method,
            "automatic_payment_methods[enabled]": "true",
            "automatic_payment_methods[allow_redirects]": "never",
            "metadata[exchange_id]": exchange_id,
        }
        data = self._request_form("POST", "/payment_intents", fields)
        pid = data.get("id")
        status = data.get("status")
        if not pid:
            raise SettlementError("stripe authorize 响应缺少 id")
        if status not in ("requires_capture", "succeeded"):
            raise SettlementError(f"stripe authorize 状态异常: {status}")
        return str(pid)

    def capture(self, ref: str) -> dict:
        data = self._request_form("POST", f"/payment_intents/{ref}/capture", {})
        if data.get("status") not in ("succeeded", "requires_capture"):
            raise SettlementError(f"stripe capture 状态异常: {data.get('status')}")
        return self._amount_fields(ref, data)

    def void(self, ref: str) -> dict:
        data = self._request_form("POST", f"/payment_intents/{ref}/cancel", {})
        if data.get("status") not in ("canceled", "cancelled"):
            raise SettlementError(f"stripe cancel 状态异常: {data.get('status')}")
        return self._amount_fields(ref, data)

    def _amount_fields(self, ref: str, data: dict[str, Any]) -> dict:
        amount = data.get("amount")
        currency = data.get("currency")
        if amount is None or not currency:
            raise SettlementError(f"stripe 响应缺少 amount/currency: {data!r}")
        return {"handle": ref, "amount": int(amount), "currency": str(currency).upper()}

    def _request_form(self, method: str, path: str, fields: dict[str, str]) -> dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self._http.request(method, path, data=fields)
                if r.status_code >= 500 and attempt < self.max_retries:
                    continue
                if r.status_code >= 400:
                    detail = r.text
                    try:
                        err = r.json()
                        if isinstance(err, dict) and "error" in err:
                            em = err["error"]
                            if isinstance(em, dict):
                                detail = em.get("message") or detail
                    except Exception:
                        pass
                    raise SettlementError(
                        f"stripe {method} {path} 失败: {r.status_code} {detail}"
                    )
                data = r.json()
                if not isinstance(data, dict):
                    raise SettlementError(f"stripe 响应须为 object: {data!r}")
                return data
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    continue
                raise SettlementError(f"stripe 网络错误: {exc}") from exc
        raise SettlementError(f"stripe 请求失败: {last_exc}")
