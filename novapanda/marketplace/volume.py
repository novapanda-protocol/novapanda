"""成交名义金额侧车索引（声誉 entry 无 amount 字段时的旁路）。

不进 CORE / 不进 reputation-entry schema；由 Sink 在终态时写入，
供 ScoreEngine 做「金额衰减」加权。
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class VolumeIndex(Protocol):
    def record(self, exchange_id: str, amount: int, currency: str) -> None: ...

    def notional(self, exchange_id: str) -> Optional[int]: ...


class InMemoryVolumeIndex:
    """内存名义金额表：exchange_id → amount（同币种假定由上层过滤）。"""

    def __init__(self) -> None:
        self._amounts: dict[str, int] = {}
        self._currency: dict[str, str] = {}

    def record(self, exchange_id: str, amount: int, currency: str) -> None:
        if amount < 0:
            raise ValueError("amount 不能为负")
        self._amounts[exchange_id] = amount
        self._currency[exchange_id] = currency

    def notional(self, exchange_id: str) -> Optional[int]:
        return self._amounts.get(exchange_id)
