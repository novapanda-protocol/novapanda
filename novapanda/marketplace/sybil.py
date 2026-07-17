"""女巫图：时间窗 + 边权衰减。

- ``window_sec``：只保留窗口内的尘埃边
- ``half_life_sec``：边权按年龄指数衰减，旧边对聚类贡献变小
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .risk import InMemoryRiskSignalStore
from .types import ExchangeTerminalSnapshot, RiskSignal


@dataclass
class SybilGraphPolicy:
    dust_amount: int = 10
    min_cluster_size: int = 3
    min_edges_in_cluster: float = 3.0  # 衰减后可为浮点权重和
    severity: float = 0.55
    window_sec: float = 86_400.0  # 24h
    half_life_sec: float = 21_600.0  # 6h


@dataclass
class _EdgeEvent:
    a: str
    b: str
    ts: float
    amount: int


@dataclass
class SybilGraphDetector:
    """观察终态边，带时间窗与衰减的连通分量检测。"""

    risk: InMemoryRiskSignalStore
    policy: SybilGraphPolicy = field(default_factory=SybilGraphPolicy)
    _events: list[_EdgeEvent] = field(default_factory=list)
    _marked_clusters: set[str] = field(default_factory=set)

    def observe(self, snap: ExchangeTerminalSnapshot, *, now_ts: Optional[float] = None) -> None:
        if (snap.outcome_hint or "").lower() != "settled" and snap.state != "SETTLED":
            return
        if snap.price_amount > self.policy.dust_amount:
            return
        a, b = snap.client, snap.provider
        if a == b:
            return
        ts = now_ts if now_ts is not None else time.time()
        lo, hi = (a, b) if a <= b else (b, a)
        self._events.append(_EdgeEvent(a=lo, b=hi, ts=ts, amount=snap.price_amount))
        self._prune(ts)

    def detect_clusters(self, *, now_ts: Optional[float] = None) -> list[list[str]]:
        now = now_ts if now_ts is not None else time.time()
        self._prune(now)
        adj: dict[str, set[str]] = defaultdict(set)
        weights: dict[tuple[str, str], float] = defaultdict(float)
        for ev in self._events:
            w = self._decay_weight(ev.ts, now)
            if w <= 0:
                continue
            adj[ev.a].add(ev.b)
            adj[ev.b].add(ev.a)
            weights[(ev.a, ev.b)] += w

        seen: set[str] = set()
        clusters: list[list[str]] = []
        for node in list(adj.keys()):
            if node in seen:
                continue
            comp = self._component(node, adj)
            seen.update(comp)
            if len(comp) < self.policy.min_cluster_size:
                continue
            edge_w = 0.0
            for i, u in enumerate(comp):
                for v in comp[i + 1 :]:
                    key = (u, v) if u <= v else (v, u)
                    edge_w += weights.get(key, 0.0)
            if edge_w >= self.policy.min_edges_in_cluster:
                clusters.append(sorted(comp))
        return clusters

    def detect_and_mark(self, *, now_ts: Optional[float] = None) -> list[RiskSignal]:
        out: list[RiskSignal] = []
        for members in self.detect_clusters(now_ts=now_ts):
            cid = "auto-sybil-" + "-".join(m[-8:] for m in members[:3])
            if cid in self._marked_clusters:
                continue
            self._marked_clusters.add(cid)
            out.extend(
                self.risk.mark_sybil_cluster(
                    members,
                    severity=self.policy.severity,
                    cluster_id=cid,
                )
            )
        return out

    def _decay_weight(self, event_ts: float, now: float) -> float:
        age = max(0.0, now - event_ts)
        if age > self.policy.window_sec:
            return 0.0
        hl = max(1.0, self.policy.half_life_sec)
        return math.pow(0.5, age / hl)

    def _prune(self, now: float) -> None:
        cutoff = now - self.policy.window_sec
        self._events = [e for e in self._events if e.ts >= cutoff]

    def _component(self, start: str, adj: dict[str, set[str]]) -> list[str]:
        stack = [start]
        seen = {start}
        while stack:
            u = stack.pop()
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return list(seen)
