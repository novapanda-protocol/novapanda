"""统一操作注册表：所有接入面的唯一真相来源。

每个 Operation 描述一个协议动作（名称 + 描述 + 入参 JSON Schema + 处理器）。
处理器把入参翻译为对一个「交割客户端」（鸭子类型：具备 propose/contract/.../deliver/confirm 等方法）的调用。
接入面只负责把各自协议的调用映射到这里——不得新增或改变语义。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# 客户端鸭子类型：novapanda.sdk.NovaPandaClient 即满足；未来也可换成进程内 facade。
Client = Any


@dataclass(frozen=True)
class Operation:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[Client, dict], Any]


def _propose(c: Client, a: dict) -> Any:
    return c.propose(
        provider=a["provider"], resource_type=a["resource_type"],
        quantity=a["quantity"], rule_id=a["rule_id"], price=a["price"],
        idempotency_key=a["idempotency_key"], timeouts=a.get("timeouts"),
    )


def _contract(c: Client, a: dict) -> Any:
    return c.contract(a["exchange_id"])


def _escrow(c: Client, a: dict) -> Any:
    return c.escrow(a["exchange_id"], amount=a["amount"], currency=a["currency"])


def _deliver(c: Client, a: dict) -> Any:
    return c.deliver(a["exchange_id"], a["deliverable"])


def _verify(c: Client, a: dict) -> Any:
    return c.verify(a["exchange_id"])


def _confirm(c: Client, a: dict) -> Any:
    return c.confirm(a["exchange_id"])


def _get(c: Client, a: dict) -> Any:
    return c.get_exchange(a["exchange_id"])


def _reputation(c: Client, a: dict) -> Any:
    return c.reputation(a["agent_id"])


def _reputation_score(c: Client, a: dict) -> Any:
    fn = getattr(c, "get_reputation_score", None)
    if callable(fn):
        return fn(a["agent_id"], a.get("weights"))
    return c.reputation(a["agent_id"])


def _s(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


_STR = {"type": "string"}
_INT = {"type": "integer"}
_OBJ = {"type": "object"}

OPERATIONS: list[Operation] = [
    Operation("propose", "client 发起一笔交换提案", _s(
        {"provider": _STR, "resource_type": _STR, "quantity": _INT, "rule_id": _STR,
         "price": _OBJ, "idempotency_key": _STR, "timeouts": _OBJ},
        ["provider", "resource_type", "quantity", "rule_id", "price", "idempotency_key"],
    ), _propose),
    Operation("contract", "双方确认条款", _s({"exchange_id": _STR}, ["exchange_id"]), _contract),
    Operation("escrow", "client 冻结资金", _s(
        {"exchange_id": _STR, "amount": _INT, "currency": _STR},
        ["exchange_id", "amount", "currency"],
    ), _escrow),
    Operation("deliver", "provider 本地构造并签名 VDC 后交付", _s(
        {"exchange_id": _STR, "deliverable": {}}, ["exchange_id", "deliverable"],
    ), _deliver),
    Operation("verify", "触发确定性验收", _s({"exchange_id": _STR}, ["exchange_id"]), _verify),
    Operation("confirm", "client 本地补签并结算", _s({"exchange_id": _STR}, ["exchange_id"]), _confirm),
    Operation("get_exchange", "查询交换状态", _s({"exchange_id": _STR}, ["exchange_id"]), _get),
    Operation("reputation", "查询某 agent 的信誉记录", _s({"agent_id": _STR}, ["agent_id"]), _reputation),
    Operation("reputation_score", "查询加权信誉 score", _s(
        {"agent_id": _STR, "weights": _OBJ}, ["agent_id"],
    ), _reputation_score),
]

OPERATIONS_BY_NAME: dict[str, Operation] = {op.name: op for op in OPERATIONS}


def dispatch(client: Client, name: str, arguments: dict | None = None) -> Any:
    op = OPERATIONS_BY_NAME.get(name)
    if op is None:
        raise KeyError(f"未知操作: {name}")
    return op.handler(client, arguments or {})
