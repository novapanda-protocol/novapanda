"""场站 / 桩发现：本地目录 + 可选 marketplace discover（NP-REP）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .constants import DEFAULT_ENERGY_PRICE, ENERGY_RESOURCE, ENERGY_RULE
from .paths import atomic_write_json, ensure_dir, read_json


@dataclass
class StationRecord:
    station_id: str
    agent_id: str
    resource_type: str = ENERGY_RESOURCE
    rule_id_hint: str = ENERGY_RULE
    price_amount: int = DEFAULT_ENERGY_PRICE["amount"]
    price_currency: str = DEFAULT_ENERGY_PRICE["currency"]
    location_label: str = ""
    exchange_endpoint: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StationRecord":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


class StationDirectory:
    """本地场站目录（离线可用；不改 CORE）。"""

    def __init__(self, root: Path | str) -> None:
        self.root = ensure_dir(Path(root) / "stations")
        self._path = self.root / "catalog.json"
        if not self._path.is_file():
            atomic_write_json(self._path, {"stations": []})

    def _load(self) -> list[StationRecord]:
        data = read_json(self._path, {"stations": []})
        return [StationRecord.from_dict(s) for s in data.get("stations", [])]

    def _save(self, rows: list[StationRecord]) -> None:
        atomic_write_json(self._path, {"stations": [r.to_dict() for r in rows]})

    def upsert(self, station: StationRecord) -> StationRecord:
        rows = self._load()
        out: list[StationRecord] = []
        replaced = False
        for r in rows:
            if r.station_id == station.station_id:
                out.append(station)
                replaced = True
            else:
                out.append(r)
        if not replaced:
            out.append(station)
        self._save(out)
        return station

    def list_all(self) -> list[StationRecord]:
        return self._load()

    def find(
        self,
        *,
        resource_type: str = ENERGY_RESOURCE,
        max_amount: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> list[StationRecord]:
        out: list[StationRecord] = []
        for s in self._load():
            if s.resource_type != resource_type:
                continue
            if max_amount is not None and s.price_amount > max_amount:
                continue
            if tag and tag not in s.tags:
                continue
            out.append(s)
        out.sort(key=lambda x: x.price_amount)
        return out


class StationDiscovery:
    """合并本地目录与节点 marketplace（若开启）。"""

    def __init__(self, directory: StationDirectory, client: Any) -> None:
        self.directory = directory
        self.client = client

    def register_local(self, station: StationRecord) -> StationRecord:
        return self.directory.upsert(station)

    def discover(
        self,
        *,
        resource_type: str = ENERGY_RESOURCE,
        max_amount: int = 10_000,
        currency: str = "USD",
        prefer_marketplace: bool = True,
    ) -> dict[str, Any]:
        local = [
            {
                "source": "local_catalog",
                "station_id": s.station_id,
                "agent_id": s.agent_id,
                "resource_type": s.resource_type,
                "rule_id_hint": s.rule_id_hint,
                "price": {"amount": s.price_amount, "currency": s.price_currency},
                "location_label": s.location_label,
                "tags": list(s.tags),
                "endpoints": {"exchange": s.exchange_endpoint} if s.exchange_endpoint else {},
            }
            for s in self.directory.find(
                resource_type=resource_type, max_amount=max_amount,
            )
        ]
        market: dict[str, Any] = {"available": False, "ranked": [], "winner": None}
        if prefer_marketplace:
            try:
                r = self.client._http.get(
                    "/marketplace/discover",
                    params={
                        "resource_type": resource_type,
                        "max_amount": max_amount,
                        "currency": currency,
                        "tags": "energy,charging",
                        "limit": 10,
                    },
                )
                if r.status_code == 200:
                    body = r.json()
                    # marketplace 关闭时常返回 code
                    if body.get("profile") == "NP-REP" or body.get("ranked") is not None:
                        market = {
                            "available": True,
                            "reason": body.get("reason"),
                            "winner": body.get("winner"),
                            "ranked": body.get("ranked") or [],
                        }
                    elif body.get("code"):
                        market = {
                            "available": False,
                            "reason": body.get("msg") or body.get("code"),
                            "ranked": [],
                            "winner": None,
                        }
            except Exception as exc:  # noqa: BLE001
                market = {"available": False, "reason": str(exc), "ranked": [], "winner": None}

        winner = None
        if market.get("available") and market.get("winner"):
            winner = {**market["winner"], "source": "marketplace"}
        elif local:
            winner = local[0]

        return {
            "resource_type": resource_type,
            "local": local,
            "marketplace": market,
            "winner": winner,
        }
