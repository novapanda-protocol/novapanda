"""车 ↔ OpenClaw 最小结对 CLI：持钥分目录 + 一键交割 / 分步交割。

同机冒烟::

    python demo/openclaw_pair/pair_cli.py init --root demo/out/openclaw_pair
    # 另开终端起节点后：
    python demo/openclaw_pair/pair_cli.py run --root demo/out/openclaw_pair \\
        --base-url http://127.0.0.1:8765

分机：车侧 ``--role car``，OpenClaw 主机 ``--role claw``（见 README）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from novapanda.adopter import AdopterRuntime, AdopterSkill
from novapanda.identity import Identity
from novapanda.reverify import reverify
from novapanda.sdk import NovaPandaClient

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
DEFAULT_DELIVERABLE = {
    "invoice_no": "OPENCLAW-TRIP-001",
    "total": "100.00",
    "currency": "USD",
}


def _key_path(agent_root: Path) -> Path:
    return agent_root / "identity.hex"


def _load_or_create_identity(agent_root: Path) -> Identity:
    agent_root.mkdir(parents=True, exist_ok=True)
    kp = _key_path(agent_root)
    if kp.is_file():
        return Identity.from_private_bytes(bytes.fromhex(kp.read_text(encoding="utf-8").strip()))
    ident = Identity.generate()
    kp.write_text(ident.private_bytes().hex(), encoding="utf-8")
    return ident


def _runtime(base_url: str, agent_root: Path) -> AdopterRuntime:
    ident = _load_or_create_identity(agent_root)
    sdk = NovaPandaClient(base_url.rstrip("/"), ident)
    return AdopterRuntime(sdk, agent_root / "runtime")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root)
    car = root / "car"
    claw = root / "claw"
    car_rt = _runtime(args.base_url, car)
    claw_rt = _runtime(args.base_url, claw)
    meta = {
        "car_agent_id": car_rt.agent_id,
        "claw_agent_id": claw_rt.agent_id,
        "base_url": args.base_url,
        "settlement": "mock",
        "paths": {"car": str(car.resolve()), "claw": str(claw.resolve())},
    }
    _write_json(root / "pair.json", meta)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    role_root = Path(args.root) / args.role
    rt = _runtime(args.base_url, role_root)
    print(json.dumps({"role": args.role, "agent_id": rt.agent_id, "root": str(role_root)}, indent=2))
    return 0


def cmd_skill(args: argparse.Namespace) -> int:
    role_root = Path(args.root) / args.role
    rt = _runtime(args.base_url, role_root)
    skill = AdopterSkill(rt)
    out = skill.invoke(args.name, json.loads(args.args or "{}"))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


def _all_ok(checks: dict) -> bool:
    return (
        checks.get("provider_sig_valid") is True
        and checks.get("client_sig_valid") is True
        and checks.get("settled_valid") is True
        and checks.get("result_hash_matches") is True
    )


def cmd_run(args: argparse.Namespace) -> int:
    """同机一键：car Client × claw Provider → SETTLED + reverify。"""
    root = Path(args.root)
    if not (root / "pair.json").is_file():
        cmd_init(argparse.Namespace(root=str(root), base_url=args.base_url))
    car = _runtime(args.base_url, root / "car")
    claw = _runtime(args.base_url, root / "claw")
    deliverable = DEFAULT_DELIVERABLE
    if args.deliverable:
        deliverable = json.loads(Path(args.deliverable).read_text(encoding="utf-8"))

    draft = claw.open_draft(
        peer_id=car.agent_id,
        resource_type=RESOURCE,
        rule_id=RULE_ID,
        intent_summary="openclaw trip / task summary",
    )
    ex = car.client.propose(
        provider=claw.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price=PRICE,
        idempotency_key=f"openclaw-{draft.draft_id}",
    )
    eid = ex["exchange_id"]
    claw.drafts.bind_exchange(draft.draft_id, eid)
    car.client.contract(eid)
    claw.client.contract(eid)
    car.client.escrow(eid, amount=PRICE["amount"], currency=PRICE["currency"])
    claw.prepare_deliverable(draft.draft_id, deliverable)
    claw.deliver_from_draft(draft.draft_id)
    car.verify(eid)
    car.confirm(eid)
    settled = car.client.get_exchange(eid)
    car.remember_settled(eid, role="client", deliverable=deliverable)
    claw.remember_settled(eid, role="provider", deliverable=deliverable)

    vdc = settled.get("vdc") or {}
    checks = reverify(vdc, deliverable)
    out = {
        "ok": _all_ok(checks) and settled.get("state") == "SETTLED",
        "exchange_id": eid,
        "state": settled.get("state"),
        "car_agent_id": car.agent_id,
        "claw_agent_id": claw.agent_id,
        "vdc_id": vdc.get("vdc_id"),
        "reverify": checks,
        "settlement": "mock",
    }
    _write_json(root / "last_run.json", out)
    _write_json(root / "settled_vdc.json", vdc)
    _write_json(root / "deliverable.json", deliverable)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


def cmd_car_confirm(args: argparse.Namespace) -> int:
    car = _runtime(args.base_url, Path(args.root) / "car")
    skill = AdopterSkill(car)
    out = skill.invoke(
        "adopter_apply_intent",
        {"exchange_id": args.exchange_id, "text": args.text or "确认"},
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OpenClaw ↔ 车结对 CLI")
    p.add_argument("--root", default="demo/out/openclaw_pair", help="结对数据根目录")
    p.add_argument("--base-url", default="http://127.0.0.1:8765", help="节点 URL")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="生成 car/claw 两把钥与 pair.json")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("whoami", help="打印某角色 agent_id")
    s.add_argument("--role", choices=("car", "claw"), required=True)
    s.set_defaults(func=cmd_whoami)

    s = sub.add_parser("skill", help="调用 AdopterSkill 工具（供 OpenClaw 封装）")
    s.add_argument("--role", choices=("car", "claw"), required=True)
    s.add_argument("--name", required=True, help="adopter_* 工具名")
    s.add_argument("--args", default="{}", help="JSON 参数")
    s.set_defaults(func=cmd_skill)

    s = sub.add_parser("run", help="同机一键 SETTLED + reverify")
    s.add_argument("--deliverable", default="", help="可选 deliverable JSON 路径")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("car-confirm", help="车侧舱确认（OpenClaw 可代触发文案）")
    s.add_argument("--exchange-id", required=True)
    s.add_argument("--text", default="确认")
    s.set_defaults(func=cmd_car_confirm)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
