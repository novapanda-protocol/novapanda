"""结算适配器：协议对资金/价值流转**不可知**。

结算是可插拔旁路（Mock / x402 / AP2 / 法币持牌伙伴），任何人可换实现，
协议本身永不托管资金、永不收取协议费——这是中立性的硬约束。
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Protocol


class SettlementError(Exception):
    pass


class SettlementAdapter(ABC):
    @abstractmethod
    def escrow(self, exchange_id: str, amount: int, currency: str) -> str:
        """冻结资金，返回 escrow handle。"""

    @abstractmethod
    def settle(self, handle: str) -> dict:
        """将冻结资金交付给 provider。"""

    @abstractmethod
    def refund(self, handle: str) -> dict:
        """退款给 client。"""


class MockSettlement(SettlementAdapter):
    """纯内存模拟：用于模拟舱与测试，不接触任何真实资金。"""

    def __init__(self) -> None:
        self._holds: dict[str, dict] = {}

    def escrow(self, exchange_id: str, amount: int, currency: str) -> str:
        if amount < 0:
            raise SettlementError("escrow amount 不能为负")
        handle = "mock-escrow-" + uuid.uuid4().hex[:12]
        self._holds[handle] = {
            "exchange_id": exchange_id,
            "amount": amount,
            "currency": currency,
            "status": "held",
        }
        return handle

    def _receipt(self, handle: str, h: dict) -> dict:
        return {"handle": handle, "status": h["status"],
                "amount": h["amount"], "currency": h["currency"]}

    def _transition(self, handle: str, target: str) -> dict:
        """幂等：已是 target 直接返回回执；从 held 推进；冲突（已是另一终态）报错。

        幂等性是 capture-before-execute 的前提：崩溃后重放同一动作必须安全。
        """
        h = self._holds.get(handle)
        if h is None:
            raise SettlementError(f"未知 escrow handle: {handle}")
        if h["status"] == target:
            return self._receipt(handle, h)
        if h["status"] != "held":
            raise SettlementError(f"escrow 状态冲突：{h['status']} -> {target}")
        h["status"] = target
        return self._receipt(handle, h)

    def settle(self, handle: str) -> dict:
        return self._transition(handle, "settled")

    def refund(self, handle: str) -> dict:
        return self._transition(handle, "refunded")

    def status(self, handle: str) -> str:
        return self._holds[handle]["status"]


class PaymentGateway(Protocol):
    """支付网关抽象：把"授权 -> 捕获 -> 撤销"三步交给真实支付轨道实现。"""

    def authorize(self, exchange_id: str, amount: int, currency: str) -> str: ...
    def capture(self, ref: str) -> dict: ...
    def void(self, ref: str) -> dict: ...


class GatewaySettlement(SettlementAdapter):
    """把任意 PaymentGateway 适配为结算适配器。

    协议层语义统一为 escrow/settle/refund；具体轨道差异（x402/AP2/法币）封装在 gateway 内。
    这正是「协议对资金不可知、结算可被替换」的落地：换 rail 只需换 gateway。
    """

    rail = "generic"

    def __init__(self, gateway: PaymentGateway) -> None:
        self.gateway = gateway

    def escrow(self, exchange_id: str, amount: int, currency: str) -> str:
        if amount < 0:
            raise SettlementError("escrow amount 不能为负")
        return self.gateway.authorize(exchange_id, amount, currency)

    def settle(self, handle: str) -> dict:
        return {"rail": self.rail, "status": "settled", **self.gateway.capture(handle)}

    def refund(self, handle: str) -> dict:
        return {"rail": self.rail, "status": "refunded", **self.gateway.void(handle)}


class X402Settlement(GatewaySettlement):
    """x402 适配器：escrow≈对 402 Payment-Required 的支付授权，settle≈capture，refund≈void。

    具体 HTTP 402 挑战/凭据交换由注入的 gateway 完成；本类只做协议语义映射。
    """

    rail = "x402"


class AP2Settlement(GatewaySettlement):
    """AP2（Agent Payments Protocol）适配器：escrow≈按支付授权书建立授权，settle≈capture，refund≈退款。"""

    rail = "ap2"


class FiatSettlement(GatewaySettlement):
    """法币持牌伙伴适配器：escrow≈预授权/冻结，settle≈capture，refund≈void/refund。

    协议层不碰 KYC/AML/牌照；这些由网关/伙伴承担。
    """

    rail = "fiat"


class FakeGateway:
    """内存版支付网关：用于开发/测试 GatewaySettlement，幂等、安全可重放。"""

    def __init__(self) -> None:
        self._refs: dict[str, dict] = {}

    def authorize(self, exchange_id: str, amount: int, currency: str) -> str:
        ref = "auth-" + uuid.uuid4().hex[:12]
        self._refs[ref] = {"exchange_id": exchange_id, "amount": amount,
                           "currency": currency, "state": "authorized"}
        return ref

    def _move(self, ref: str, target: str) -> dict:
        r = self._refs.get(ref)
        if r is None:
            raise SettlementError(f"未知 ref: {ref}")
        if r["state"] not in (target, "authorized"):
            raise SettlementError(f"ref 状态冲突：{r['state']} -> {target}")
        r["state"] = target
        return {"handle": ref, "amount": r["amount"], "currency": r["currency"]}

    def capture(self, ref: str) -> dict:
        return self._move(ref, "captured")

    def void(self, ref: str) -> dict:
        return self._move(ref, "voided")

    def state(self, ref: str) -> str:
        return self._refs[ref]["state"]
