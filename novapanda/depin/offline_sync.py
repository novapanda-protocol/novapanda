"""离线签名凭证队列：断网生成 → 复网幂等 Sink（不改 TRANSITIONS）。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from novapanda.marketplace.types import ExchangeTerminalSnapshot

from .pod_tpm import simulate_tpm_sign


@dataclass(frozen=True)
class OfflineSignedCredential:
    """无网环境下硬件 Agent 本地签发的挂起凭证。"""

    exchange_id: str
    device_id: str
    payload: dict[str, Any]
    tpm_signature: str
    created_at: float
    client: str = ""
    provider: str = ""
    resource_type: str = "depin.physical"
    price_amount: int = 0
    price_currency: str = "USD"
    vdc_id: Optional[str] = None


@dataclass
class OfflineCredentialQueue:
    """断网挂起队列；复网后向 MarketplaceTerminalSink 幂等投递。

    不调用 ``assert_transition``——仅旁路观察者路径。
    """

    device_id: str
    tpm_secret: str = "tpm-sim"
    _pending: list[OfflineSignedCredential] = field(default_factory=list)
    _synced_ids: set[str] = field(default_factory=set)
    network_up: bool = True

    def partition(self) -> None:
        """模拟网络分区（离线）。"""
        self.network_up = False

    def restore(self) -> None:
        """网络恢复。"""
        self.network_up = True

    def issue_offline(
        self,
        *,
        exchange_id: str,
        payload: dict[str, Any],
        client: str = "",
        provider: str = "",
        resource_type: str = "depin.edge.compute",
        price_amount: int = 0,
        price_currency: str = "USD",
        vdc_id: Optional[str] = None,
        now_ts: Optional[float] = None,
    ) -> OfflineSignedCredential:
        """无网签发：本地 TPM 签名，入队等待 Sink。"""
        if self.network_up:
            # 允许在线也签发（演练一致）；标记仍可 flush
            pass
        sig = simulate_tpm_sign(self.device_id, payload, secret=self.tpm_secret)
        cred = OfflineSignedCredential(
            exchange_id=exchange_id,
            device_id=self.device_id,
            payload=dict(payload),
            tpm_signature=sig,
            created_at=now_ts if now_ts is not None else time.time(),
            client=client,
            provider=provider,
            resource_type=resource_type,
            price_amount=price_amount,
            price_currency=price_currency,
            vdc_id=vdc_id,
        )
        self._pending.append(cred)
        return cred

    def pending_count(self) -> int:
        return sum(1 for c in self._pending if c.exchange_id not in self._synced_ids)

    def flush_to_sink(self, sink: Any) -> list[str]:
        """复网后异步幂等写入 Sink；已同步 id 跳过。"""
        if not self.network_up:
            return []
        flushed: list[str] = []
        for cred in list(self._pending):
            if cred.exchange_id in self._synced_ids:
                continue
            snap = ExchangeTerminalSnapshot(
                exchange_id=cred.exchange_id,
                state="SETTLED",
                client=cred.client or "ed25519:offline-client",
                provider=cred.provider or f"device:{cred.device_id}",
                resource_type=cred.resource_type,
                quantity=1,
                vdc_id=cred.vdc_id or f"vdc-offline-{cred.exchange_id[:12]}",
                price_amount=cred.price_amount,
                price_currency=cred.price_currency,
                outcome_hint="settled",
            )
            # Sink 自身幂等；重复 flush 安全
            if hasattr(sink, "on_terminal"):
                sink.on_terminal(snap)
            elif callable(sink):
                sink(snap)
            self._synced_ids.add(cred.exchange_id)
            flushed.append(cred.exchange_id)
        return flushed

    def attach_runner_hook(self, runner: Any) -> None:
        """挂到 RealExchangeRunner.on_leg_started：离线时只入队，在线透传。"""
        prev = getattr(runner, "on_leg_started", None)

        def _hook(info: dict) -> None:
            if not self.network_up:
                eid = str(info.get("exchange_id") or "")
                if eid:
                    self.issue_offline(
                        exchange_id=eid,
                        payload={
                            "status": "offline_pending",
                            "leg": info.get("state"),
                        },
                        vdc_id=info.get("vdc_id"),
                        price_amount=0,
                    )
                return
            if prev:
                prev(info)

        runner.on_leg_started = _hook  # type: ignore[method-assign]
