"""适配器接入面：把任意现有系统包装成 Troodon provider，最薄接入。

这是「泛化接入」的关键：行业 Agent / OpenClaw / 爱马仕等只需提供一个
`work_fn(request) -> deliverable` 函数，即可作为 provider 接入协议——
无需理解状态机或签名细节，VDC 的本地构造与签名由客户端完成（私钥不出本地）。
"""

from __future__ import annotations

from typing import Any, Callable

from .base import Client


class ProviderAdapter:
    def __init__(self, client: Client, work_fn: Callable[[dict], Any]) -> None:
        self.client = client
        self.work_fn = work_fn

    def fulfill(self, exchange_id: str) -> dict:
        """拉取交换需求 -> 调用外部系统产出交付物 -> 本地签名 VDC 并交付。"""
        ex = self.client.get_exchange(exchange_id)
        request = {
            "exchange_id": exchange_id,
            "resource_type": ex["resource_type"],
            "quantity": ex["quantity"],
            "rule_id": ex["rule_id"],
        }
        deliverable = self.work_fn(request)
        return self.client.deliver(exchange_id, deliverable)
