"""多轨结算注册表 · NP-SETTLE P1（RailRegistry + Manifest 多轨宣告）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from .settlement import SettlementAdapter, assert_settlement_env_gate

if TYPE_CHECKING:
    from .config import NodeConfig

KNOWN_RAIL_NAMES = frozenset({"mock", "sandbox", "x402", "ap2", "fiat"})

# 微支付档默认阈值（最小货币单位，如 USD 分）
DEFAULT_MICRO_MAX = 1_000
DEFAULT_MACRO_MIN = 100_000

# 微支付路由优先级（链上 / Agent 支付优先于法币/mock）
MICRO_RAIL_PRIORITY: tuple[str, ...] = (
    "x402",
    "ap2",
    "mock",
    "fiat",
    "fiat-s1-sandbox",
)

# 大额档优先持牌/法币轨
MACRO_RAIL_PRIORITY: tuple[str, ...] = (
    "fiat-s1-sandbox",
    "fiat",
    "ap2",
    "mock",
    "x402",
)


def micro_thresholds() -> tuple[int, int]:
    """NOVAPANDA_MICRO_MAX / NOVAPANDA_MACRO_MIN（最小货币单位）。"""
    micro_raw = os.environ.get("NOVAPANDA_MICRO_MAX")
    macro_raw = os.environ.get("NOVAPANDA_MACRO_MIN")
    micro_max = int(micro_raw) if micro_raw is not None else DEFAULT_MICRO_MAX
    macro_min = int(macro_raw) if macro_raw is not None else DEFAULT_MACRO_MIN
    return micro_max, macro_min


def infer_amount_class(
    amount: int,
    *,
    micro_max: Optional[int] = None,
    macro_min: Optional[int] = None,
) -> str:
    if amount < 0:
        raise ValueError("amount 不能为负")
    if micro_max is None or macro_min is None:
        micro_max, macro_min = micro_thresholds()
    if amount <= micro_max:
        return "micro"
    if amount >= macro_min:
        return "macro"
    return "standard"


def amount_in_micropay_range(rail: dict[str, Any], amount: int) -> bool:
    mp = rail.get("micropay")
    if not mp:
        return True
    mn = int(mp.get("min_unit", 0))
    mx = mp.get("max_unit")
    if amount < mn:
        return False
    if mx is not None and amount > int(mx):
        return False
    return True


def _rank_candidates(
    candidates: list[dict[str, Any]],
    *,
    amount_class: str,
    preferred: list[str],
) -> list[dict[str, Any]]:
    if preferred:
        order = {rid: i for i, rid in enumerate(preferred)}
        return sorted(candidates, key=lambda r: order.get(str(r.get("id")), 999))
    if amount_class == "micro":
        priority = {rid: i for i, rid in enumerate(MICRO_RAIL_PRIORITY)}
        return sorted(
            candidates,
            key=lambda r: priority.get(str(r.get("id")), len(MICRO_RAIL_PRIORITY)),
        )
    if amount_class == "macro":
        priority = {rid: i for i, rid in enumerate(MACRO_RAIL_PRIORITY)}
        return sorted(
            candidates,
            key=lambda r: priority.get(str(r.get("id")), len(MACRO_RAIL_PRIORITY)),
        )
    return candidates


@dataclass(frozen=True)
class RailEntry:
    """一条可宣告轨：适配器实例 + 公开 Manifest 元数据（无密钥）。"""

    key: str
    rail_id: str
    adapter: SettlementAdapter
    meta: dict[str, Any]


class SettlementBindingError(Exception):
    """轨协商失败（交集为空且 fallback=reject）。"""

    code = "E_RAIL_MISMATCH"


class RailRegistry:
    """节点级多轨注册表；活跃轨供 ExchangeEngine 调用。"""

    def __init__(self, entries: list[RailEntry], *, active_key: str) -> None:
        if not entries:
            raise ValueError("RailRegistry 至少需一条轨")
        keys = {e.key for e in entries}
        if active_key not in keys:
            raise ValueError(f"active_key {active_key!r} 不在已注册轨 {sorted(keys)}")
        self._entries = {e.key: e for e in entries}
        self._order = [e.key for e in entries]
        self.active_key = active_key

    @property
    def active_adapter(self) -> SettlementAdapter:
        return self._entries[self.active_key].adapter

    @property
    def active_rail_id(self) -> str:
        return self._entries[self.active_key].rail_id

    def adapter_for_rail_id(self, rail_id: str) -> SettlementAdapter:
        for entry in self._entries.values():
            if entry.rail_id == rail_id:
                return entry.adapter
        raise KeyError(f"未注册 rail_id: {rail_id!r}")

    def get(self, key: str) -> SettlementAdapter:
        return self._entries[key].adapter

    def list_keys(self) -> list[str]:
        return list(self._order)

    def manifest_rails(self) -> list[dict[str, Any]]:
        return [dict(self._entries[k].meta) for k in self._order]

    def manifest_block(self) -> dict[str, Any]:
        micro_max, macro_min = micro_thresholds()
        return {
            "default_rail": self.active_rail_id,
            "rails": self.manifest_rails(),
            "routing": {
                "micro_max": micro_max,
                "macro_min": macro_min,
                "micro_priority": list(MICRO_RAIL_PRIORITY),
                "macro_priority": list(MACRO_RAIL_PRIORITY),
            },
        }

    def quote(
        self,
        amount: int,
        currency: str,
        *,
        preferred_rails: Optional[list[str]] = None,
        client_rails: Optional[list[str]] = None,
        provider_rails: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        return quote_settlement(
            amount=amount,
            currency=currency,
            node_rails=self.manifest_rails(),
            preferred_rails=preferred_rails,
            client_rails=client_rails,
            provider_rails=provider_rails,
        )


def _settlement_env() -> str | None:
    return os.environ.get("NOVAPANDA_SETTLEMENT_ENV") or os.environ.get("SETTLEMENT_ENV")


def _meta_from_adapter(key: str, adapter: SettlementAdapter) -> dict[str, Any]:
    if hasattr(adapter, "manifest_rail"):
        return dict(adapter.manifest_rail())
    rail_id = getattr(adapter, "rail", key)
    settlement_name = type(adapter).__name__.replace("Settlement", "").lower() or key
    environment = getattr(
        adapter, "environment", "mock" if settlement_name == "mock" else "production"
    )
    meta: dict[str, Any] = {
        "id": rail_id,
        "family": _family_for_key(key),
        "currencies": _default_currencies(key),
        "finality": "instant" if key == "mock" else ("onchain" if key == "x402" else "t+1"),
        "licensed": bool(getattr(adapter, "licensed", False)),
        "environment": environment,
        "amount_class": _default_amount_classes(key),
    }
    partner = getattr(adapter, "partner", None)
    if partner:
        meta["partner"] = partner
    if key == "x402":
        meta["networks"] = ["base"]
        meta["micropay"] = {"min_unit": 1, "max_unit": 100_000}
    return meta


def _family_for_key(key: str) -> str:
    return {
        "mock": "trial",
        "sandbox": "fiat",
        "fiat": "fiat",
        "x402": "chain",
        "ap2": "agent-pay",
    }.get(key, "trial")


def _default_currencies(key: str) -> list[str]:
    return {
        "x402": ["USDC"],
        "ap2": ["EUR"],
        "sandbox": ["USD", "EUR"],
    }.get(key, ["USD"])


def _default_amount_classes(key: str) -> list[str]:
    if key == "x402":
        return ["micro", "standard"]
    if key in ("fiat", "sandbox", "ap2"):
        return ["standard", "macro"]
    return ["micro", "standard", "macro"]


def _make_adapter_for_key(cfg: NodeConfig, key: str, *, allow_stub: bool = False) -> SettlementAdapter:
    from .ap2_gateway import HttpAP2Gateway
    from .fiat_gateway import HttpFiatGateway
    from .settlement import (
        AP2Settlement,
        FakeGateway,
        FiatSettlement,
        MockSettlement,
        SandboxSettlement,
        X402Settlement,
    )
    from .x402_gateway import HttpX402Gateway

    settlement_env = _settlement_env()
    if allow_stub and key not in ("mock", "sandbox"):
        settlement_env = settlement_env or "dev"
    assert_settlement_env_gate(settlement_name=key, settlement_env=settlement_env)

    if key == "mock":
        return MockSettlement()
    if key == "sandbox":
        partner = os.environ.get("NOVAPANDA_SANDBOX_PARTNER", "sandbox-stub")
        if cfg.fiat_gateway_url:
            from .fiat_gateway import make_fiat_gateway
            from .settlement import S1HttpSandboxSettlement

            if os.environ.get("NOVAPANDA_FIAT_PROVIDER", "").lower() == "stripe":
                partner = os.environ.get("NOVAPANDA_SANDBOX_PARTNER", "stripe-sandbox")
            gw = make_fiat_gateway(
                base_url=cfg.fiat_gateway_url,
                api_key=cfg.fiat_api_key,
            )
            return S1HttpSandboxSettlement(gw, partner=partner)
        return SandboxSettlement(partner=partner)
    if key == "x402":
        if cfg.x402_gateway_url:
            return X402Settlement(
                HttpX402Gateway(cfg.x402_gateway_url, api_key=cfg.x402_api_key)
            )
        if allow_stub:
            return X402Settlement(FakeGateway())
        raise ValueError("NOVAPANDA_SETTLEMENT=x402 时必须设置 NOVAPANDA_X402_URL")
    if key == "ap2":
        if cfg.ap2_gateway_url:
            return AP2Settlement(
                HttpAP2Gateway(cfg.ap2_gateway_url, api_key=cfg.ap2_api_key)
            )
        if allow_stub:
            return AP2Settlement(FakeGateway())
        raise ValueError("NOVAPANDA_SETTLEMENT=ap2 时必须设置 NOVAPANDA_AP2_URL")
    if key == "fiat":
        if cfg.fiat_gateway_url:
            return FiatSettlement(
                HttpFiatGateway(cfg.fiat_gateway_url, api_key=cfg.fiat_api_key)
            )
        if allow_stub:
            return FiatSettlement(FakeGateway())
        raise ValueError("NOVAPANDA_SETTLEMENT=fiat 时必须设置 NOVAPANDA_FIAT_URL")
    raise ValueError(f"未知轨名 {key!r}；支持: {sorted(KNOWN_RAIL_NAMES)}")


def build_rail_registry(cfg: NodeConfig) -> RailRegistry:
    """从 NodeConfig 构建注册表；无 NOVAPANDA_RAILS 时退化为单轨。"""
    keys = cfg.settlement_rails
    if not keys:
        key = cfg.settlement.strip().lower()
        if key not in KNOWN_RAIL_NAMES:
            raise ValueError(f"未知 NOVAPANDA_SETTLEMENT: {key}")
        adapter = _make_adapter_for_key(cfg, key, allow_stub=False)
        entry = RailEntry(key=key, rail_id=_meta_from_adapter(key, adapter)["id"], adapter=adapter, meta=_meta_from_adapter(key, adapter))
        return RailRegistry([entry], active_key=key)

    seen: set[str] = set()
    entries: list[RailEntry] = []
    for raw in keys:
        key = raw.strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        if key not in KNOWN_RAIL_NAMES:
            raise ValueError(f"NOVAPANDA_RAILS 含未知轨 {key!r}")
        seen.add(key)
        adapter = _make_adapter_for_key(cfg, key, allow_stub=True)
        meta = _meta_from_adapter(key, adapter)
        if key in ("x402", "ap2", "fiat") and not _has_gateway_url(cfg, key):
            meta = {**meta, "environment": "dev", "note": "stub gateway — configure URL for production rail"}
        entries.append(
            RailEntry(key=key, rail_id=meta["id"], adapter=adapter, meta=meta)
        )
    if not entries:
        raise ValueError("NOVAPANDA_RAILS 解析后为空")

    active = (cfg.default_rail or cfg.settlement or entries[0].key).strip().lower()
    if active not in seen:
        active = entries[0].key
    return RailRegistry(entries, active_key=active)


def _has_gateway_url(cfg: NodeConfig, key: str) -> bool:
    if key == "x402":
        return bool(cfg.x402_gateway_url)
    if key == "ap2":
        return bool(cfg.ap2_gateway_url)
    if key == "fiat":
        return bool(cfg.fiat_gateway_url)
    return False


def negotiate_rail(
    *,
    terms: dict[str, Any],
    node_rails: list[dict[str, Any]],
    amount: Optional[int] = None,
    client_rails: Optional[list[str]] = None,
    provider_rails: Optional[list[str]] = None,
) -> Optional[str]:
    """按条款与 Manifest 交集选轨 id；可据 amount 推断 amount_class（P3）。"""
    currency = (terms.get("currency") or "").upper()
    amount_class = terms.get("amount_class")
    if amount_class is None and amount is not None:
        amount_class = infer_amount_class(int(amount))
    amount_class = amount_class or "standard"
    preferred = [str(r) for r in (terms.get("preferred_rails") or [])]
    node_ids = {str(r.get("id")) for r in node_rails}

    def _ok(rail: dict[str, Any]) -> bool:
        rid = str(rail.get("id"))
        if rid not in node_ids:
            return False
        currencies = [str(c).upper() for c in rail.get("currencies") or []]
        if currency and currencies and currency not in currencies:
            return False
        classes = rail.get("amount_class") or []
        if classes and amount_class not in classes:
            return False
        if amount is not None and not amount_in_micropay_range(rail, int(amount)):
            return False
        return True

    candidates = [r for r in node_rails if _ok(r)]
    if not candidates:
        return None

    caps_client = set(client_rails or node_ids)
    caps_provider = set(provider_rails or node_ids)
    candidates = [
        r
        for r in candidates
        if str(r.get("id")) in caps_client and str(r.get("id")) in caps_provider
    ]
    if not candidates:
        return None

    ranked = _rank_candidates(candidates, amount_class=amount_class, preferred=preferred)
    return str(ranked[0]["id"])


def quote_settlement(
    *,
    amount: int,
    currency: str,
    node_rails: list[dict[str, Any]],
    preferred_rails: Optional[list[str]] = None,
    client_rails: Optional[list[str]] = None,
    provider_rails: Optional[list[str]] = None,
) -> dict[str, Any]:
    """P3：各轨报价探测（费用为 stub；eligible 可观测）。"""
    if amount < 0:
        raise ValueError("amount 不能为负")
    cur = currency.upper()
    amount_class = infer_amount_class(amount)
    terms = {
        "currency": cur,
        "amount_class": amount_class,
        "preferred_rails": preferred_rails or [],
    }
    caps_c = client_rails
    caps_p = provider_rails
    node_ids = {str(r.get("id")) for r in node_rails}

    quotes: list[dict[str, Any]] = []
    for rail in node_rails:
        rid = str(rail.get("id"))
        eligible = negotiate_rail(
            terms={**terms, "preferred_rails": [rid]},
            node_rails=node_rails,
            amount=amount,
            client_rails=caps_c or [rid],
            provider_rails=caps_p or [rid],
        ) == rid
        if not eligible:
            reason = _ineligible_reason(rail, amount=amount, currency=cur, amount_class=amount_class)
        else:
            reason = None
        quotes.append(
            {
                "rail": rid,
                "currency": cur,
                "amount": amount,
                "amount_class": amount_class,
                "family": rail.get("family"),
                "finality": rail.get("finality"),
                "environment": rail.get("environment"),
                "eligible": eligible,
                "fee_estimate": None,
                "note": "stub quote — configure live gateway for fees" if eligible else reason,
            }
        )

    recommended = negotiate_rail(
        terms=terms,
        node_rails=node_rails,
        amount=amount,
        client_rails=caps_c,
        provider_rails=caps_p,
    )
    return {
        "amount": amount,
        "currency": cur,
        "amount_class": amount_class,
        "quotes": quotes,
        "recommended_rail": recommended,
        "routing": {
            "micro_max": micro_thresholds()[0],
            "macro_min": micro_thresholds()[1],
        },
    }


def _ineligible_reason(
    rail: dict[str, Any],
    *,
    amount: int,
    currency: str,
    amount_class: str,
) -> str:
    currencies = [str(c).upper() for c in rail.get("currencies") or []]
    if currencies and currency not in currencies:
        return f"currency {currency} not supported"
    classes = rail.get("amount_class") or []
    if classes and amount_class not in classes:
        return f"amount_class {amount_class} not supported"
    if not amount_in_micropay_range(rail, amount):
        return "amount outside micropay range"
    return "rail caps mismatch"


def preview_settlement_binding(
    *,
    amount: int,
    currency: str,
    settlement_terms: Optional[dict[str, Any]] = None,
    node_rails: list[dict[str, Any]],
    client_rails: Optional[list[str]] = None,
    provider_rails: Optional[list[str]] = None,
) -> dict[str, Any]:
    """P3：不创建 exchange，预览缔约后将锁定的 binding。"""
    price = {"amount": amount, "currency": currency}
    return finalize_settlement_binding(
        settlement_terms=settlement_terms,
        price=price,
        node_rails=node_rails,
        client_rails=client_rails,
        provider_rails=provider_rails,
    )


def finalize_settlement_binding(
    *,
    settlement_terms: Optional[dict[str, Any]],
    price: dict[str, Any],
    node_rails: list[dict[str, Any]],
    client_rails: Optional[list[str]] = None,
    provider_rails: Optional[list[str]] = None,
) -> dict[str, Any]:
    """缔约完成时锁定 settlement_binding（P2）。"""
    terms = dict(settlement_terms or {})
    if price.get("currency") and not terms.get("currency"):
        terms["currency"] = price["currency"]
    amt = price.get("amount")
    amount_i = int(amt) if isinstance(amt, (int, float)) else None
    if not terms.get("amount_class") and amount_i is not None:
        terms["amount_class"] = infer_amount_class(amount_i)
    terms.setdefault("amount_class", "standard")
    caps_client = client_rails or terms.pop("client_rails", None)
    caps_provider = provider_rails or terms.pop("provider_rails", None)
    rail_id = negotiate_rail(
        terms=terms,
        node_rails=node_rails,
        amount=amount_i,
        client_rails=caps_client,
        provider_rails=caps_provider,
    )
    if rail_id is None:
        fallback = str(terms.get("fallback") or "reject").lower()
        if fallback == "mock" and any(str(r.get("id")) == "mock" for r in node_rails):
            rail_id = "mock"
        else:
            raise SettlementBindingError("rail_mismatch: no compatible settlement rail")
    return {
        "rail": rail_id,
        "chosen_at": "contract",
        "currency": terms.get("currency"),
        "amount_class": terms.get("amount_class"),
        "preferred_rails": terms.get("preferred_rails"),
    }
