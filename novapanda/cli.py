"""NovaPanda CLI（路线 B2）：rails / quote / negotiate / conformance / manifest / ecosystem。

用法：
  python -m novapanda rails
  python -m novapanda quote --amount 50 --currency USDC
  python -m novapanda negotiate --amount 50 --currency USDC --preferred x402,mock
  python -m novapanda conformance list
  python -m novapanda conformance report [--run]
  python -m novapanda manifest validate path.json
  python -m novapanda ecosystem list
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .config import NodeConfig
from .rail_registry import SettlementBindingError, build_rail_registry, preview_settlement_binding


def _json_out(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _registry_from_env():
    return build_rail_registry(NodeConfig.from_env())


def _split_csv(raw: Optional[str]) -> Optional[list[str]]:
    if not raw:
        return None
    return [p.strip() for p in raw.split(",") if p.strip()]


def cmd_rails(_: argparse.Namespace) -> int:
    _json_out(_registry_from_env().manifest_block())
    return 0


def cmd_ecosystem_list(_: argparse.Namespace) -> int:
    from .ecosystem import list_adapter_summaries

    rows = list_adapter_summaries()
    _json_out({"adapters": rows, "count": len(rows)})
    return 0


def cmd_quote(args: argparse.Namespace) -> int:
    reg = _registry_from_env()
    _json_out(
        reg.quote(
            args.amount,
            args.currency,
            preferred_rails=_split_csv(args.preferred),
            client_rails=_split_csv(args.client_rails),
            provider_rails=_split_csv(args.provider_rails),
        )
    )
    return 0


def cmd_negotiate(args: argparse.Namespace) -> int:
    reg = _registry_from_env()
    settlement = None
    if args.settlement_json:
        settlement = json.loads(args.settlement_json)
    elif args.preferred:
        settlement = {"preferred_rails": _split_csv(args.preferred)}
    try:
        binding = preview_settlement_binding(
            amount=args.amount,
            currency=args.currency,
            settlement_terms=settlement,
            node_rails=reg.manifest_rails(),
            client_rails=_split_csv(args.client_rails),
            provider_rails=_split_csv(args.provider_rails),
        )
    except SettlementBindingError as exc:
        print(json.dumps({"error": "E_RAIL_MISMATCH", "msg": str(exc)}), file=sys.stderr)
        return 1
    quote = reg.quote(
        args.amount,
        args.currency,
        preferred_rails=(settlement or {}).get("preferred_rails"),
        client_rails=_split_csv(args.client_rails),
        provider_rails=_split_csv(args.provider_rails),
    )
    _json_out({"quote": quote, "binding_preview": binding})
    return 0


def cmd_conformance_list(_: argparse.Namespace) -> int:
    from conformance.suite import list_cases

    _json_out({"cases": list_cases()})
    return 0


def cmd_conformance_run(args: argparse.Namespace) -> int:
    from conformance.suite import run_case

    return run_case(args.case_id)


def cmd_conformance_report(args: argparse.Namespace) -> int:
    from .conformance_report import build_report

    report = build_report(run_all=bool(args.run))
    _json_out(report)
    if args.run and not report.get("run_all", {}).get("passed", False):
        return 1
    return 0


def cmd_manifest_validate(args: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from .manifest_validate import validate_agent_manifest, validate_manifest_file

    if args.path == "-":
        doc = json.load(sys.stdin)
        report = validate_agent_manifest(
            doc,
            claim_mock_only=not args.claim_production,
            delegation_supported=not args.no_delegation,
            require_profiles=bool(args.require_profiles),
        )
        report["path"] = "-"
    else:
        report = validate_manifest_file(
            Path(args.path),
            claim_mock_only=not args.claim_production,
            delegation_supported=not args.no_delegation,
            require_profiles=bool(args.require_profiles),
        )
    _json_out(report)
    if not report.get("ok"):
        return 1
    if args.strict_warnings and report.get("warnings"):
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="novapanda", description="NovaPanda CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("rails", help="本机 env 的多轨 Manifest").set_defaults(func=cmd_rails)

    q = sub.add_parser("quote", help="结算轨报价探测")
    q.add_argument("--amount", "-a", type=int, required=True)
    q.add_argument("--currency", "-c", required=True)
    q.add_argument("--preferred", help="逗号分隔 preferred_rails")
    q.add_argument("--client-rails")
    q.add_argument("--provider-rails")
    q.set_defaults(func=cmd_quote)

    n = sub.add_parser("negotiate", help="预览 settlement_binding")
    n.add_argument("--amount", "-a", type=int, required=True)
    n.add_argument("--currency", "-c", required=True)
    n.add_argument("--preferred", help="逗号分隔 preferred_rails")
    n.add_argument("--settlement-json", help="完整 settlement JSON 字符串")
    n.add_argument("--client-rails")
    n.add_argument("--provider-rails")
    n.set_defaults(func=cmd_negotiate)

    conf = sub.add_parser("conformance", help="一致性套件")
    conf_sub = conf.add_subparsers(dest="conf_cmd", required=True)
    conf_sub.add_parser("list", help="列出 Case").set_defaults(func=cmd_conformance_list)
    cr = conf_sub.add_parser("run", help="运行单个 Case")
    cr.add_argument("case_id")
    cr.set_defaults(func=cmd_conformance_run)
    crep = conf_sub.add_parser("report", help="登记用一致性报告（gap audit + Case 列表）")
    crep.add_argument("--run", action="store_true", help="附加运行全套件")
    crep.set_defaults(func=cmd_conformance_report)

    man = sub.add_parser("manifest", help="Agent Manifest 工具")
    man_sub = man.add_subparsers(dest="man_cmd", required=True)
    mv = man_sub.add_parser("validate", help="校验 Manifest 签名与 Profile 诚实")
    mv.add_argument("path", help="manifest JSON 路径，或 - 表示 stdin")
    mv.add_argument(
        "--require-profiles",
        action="store_true",
        help="缺少 profiles 字段则失败",
    )
    mv.add_argument(
        "--strict-warnings",
        action="store_true",
        help="存在 warnings 时以退出码 2 失败",
    )
    mv.add_argument(
        "--claim-production",
        action="store_true",
        help="宣告 NP-CLAIM-XFER 时按生产轨（关闭 mock-only 诚实闸）",
    )
    mv.add_argument(
        "--no-delegation",
        action="store_true",
        help="节点未启用委托时用于诚实检查",
    )
    mv.set_defaults(func=cmd_manifest_validate)

    eco = sub.add_parser("ecosystem", help="社区生态适配器目录")
    eco_sub = eco.add_subparsers(dest="eco_cmd", required=True)
    eco_sub.add_parser("list", help="列出 adapters/*/manifest.json").set_defaults(
        func=cmd_ecosystem_list,
    )

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not hasattr(args, "func"):
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
