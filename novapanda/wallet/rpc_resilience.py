"""RPC Gas 估算：重试 · 超时 · fallback，避免供应链 DAG 被链阻塞。"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from typing import Any, Optional

from .types import GasQuote, TransferRequest


@dataclass
class ResilientEstimateGas:
    """包装任意带 ``estimate_gas(from_address, req)`` 的适配器。"""

    adapter: Any
    max_retries: int = 3
    timeout_sec: float = 4.0
    fallback_gas: int = 21_000
    backoff_sec: float = 0.05

    def estimate_gas(self, from_address: str, req: TransferRequest) -> GasQuote:
        last_exc: Optional[BaseException] = None
        for attempt in range(max(1, self.max_retries)):
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(self.adapter.__class__.estimate_gas, self.adapter, from_address, req)
                    # 若已被替换成 bound method，直接调底层
                    try:
                        quote = fut.result(timeout=self.timeout_sec)
                    except FuturesTimeout:
                        # 直接调原始实现可能已被覆盖；用 _raw
                        raise TimeoutError("estimate_gas timeout")
                if quote is not None:
                    return quote
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(self.backoff_sec * (attempt + 1))

        # fallback：不抛，带标记，防止 DAG 死锁
        chain_id = getattr(getattr(self.adapter, "chain", None), "chain_id", "unknown")
        native = getattr(self.adapter, "native_symbol", "ETH")
        return GasQuote(
            chain_id=chain_id,
            native_gas_estimate=self.fallback_gas,
            native_symbol=native,
            paymaster_available=False,
            degraded=True,
        )


def with_resilient_estimate_gas(adapter: Any, **kwargs: Any) -> Any:
    """就地包装 adapter.estimate_gas。"""
    # 保留未包装前的实现
    raw = adapter.__class__.estimate_gas

    def _raw(from_address: str, req: TransferRequest) -> GasQuote:
        return raw(adapter, from_address, req)

    resilient = ResilientEstimateGas(adapter=adapter, **kwargs)

    def _wrapped(from_address: str, req: TransferRequest) -> GasQuote:
        last_exc: Optional[BaseException] = None
        for attempt in range(max(1, resilient.max_retries)):
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(_raw, from_address, req)
                    return fut.result(timeout=resilient.timeout_sec)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(resilient.backoff_sec * (attempt + 1))
        chain_id = getattr(getattr(adapter, "chain", None), "chain_id", "unknown")
        native = getattr(adapter, "native_symbol", "ETH")
        _ = last_exc
        return GasQuote(
            chain_id=chain_id,
            native_gas_estimate=resilient.fallback_gas,
            native_symbol=native,
            paymaster_available=False,
            degraded=True,
        )

    adapter.estimate_gas = _wrapped  # type: ignore[method-assign]
    return adapter
