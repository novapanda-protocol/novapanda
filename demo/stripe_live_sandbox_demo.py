"""Stripe 真网沙箱试跑（需本机 sk_test，不进 git）。

用法（PowerShell）：
  $env:NOVAPANDA_FIAT_API_KEY = "sk_test_…"
  python demo/stripe_live_sandbox_demo.py

或从文件读（勿提交）：
  $env:NOVAPANDA_FIAT_KEY_FILE = "$HOME\\.novapanda\\stripe_sk_test"
  python demo/stripe_live_sandbox_demo.py

仅探测 PaymentIntent（不跑交割）：
  python demo/stripe_live_sandbox_demo.py --probe-only
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from novapanda.config import NodeConfig
from novapanda.identity import Identity
from novapanda.node import create_app_from_config
from novapanda.sdk import NovaPandaClient
from novapanda.settlement import SettlementError
from novapanda.stripe_gateway import StripeGateway

RULE = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
GOOD = {"invoice_no": "LIVE-001", "total": "1.00", "currency": "USD"}


def _load_api_key() -> str:
    key = (os.environ.get("NOVAPANDA_FIAT_API_KEY") or "").strip()
    if not key:
        path = os.environ.get("NOVAPANDA_FIAT_KEY_FILE")
        if path and Path(path).is_file():
            key = Path(path).read_text(encoding="utf-8").strip()
    if not key.startswith("sk_test_"):
        print(
            "缺少 Stripe 沙箱密钥。\n"
            "  1. 打开 https://dashboard.stripe.com/test/apikeys\n"
            "  2. 复制 Secret key（sk_test_…）\n"
            "  3. PowerShell:\n"
            '       $env:NOVAPANDA_FIAT_API_KEY = "sk_test_你的密钥"\n'
            "  4. 再运行本脚本\n"
            "\n纪律：密钥勿进 git、勿贴聊天。"
        )
        raise SystemExit(2)
    return key


def probe_stripe(api_key: str) -> str:
    """最小 PI：authorize → capture，返回 payment_intent id。"""
    gw = StripeGateway(api_key=api_key)
    eid = "np-probe-" + uuid.uuid4().hex[:10]
    print(f"probe authorize exchange_id={eid} amount=50 USD ($0.50)")
    ref = gw.authorize(eid, 50, "USD")
    print(f"  payment_intent={ref}")
    cap = gw.capture(ref)
    print(f"  captured amount={cap['amount']} {cap['currency']}")
    return ref


def full_exchange(api_key: str) -> None:
    os.environ["NOVAPANDA_AUTH"] = "0"
    os.environ["NOVAPANDA_RAILS"] = "sandbox,mock"
    os.environ["NOVAPANDA_DEFAULT_RAIL"] = "sandbox"
    os.environ["NOVAPANDA_SETTLEMENT_ENV"] = "sandbox"
    os.environ["NOVAPANDA_FIAT_PROVIDER"] = "stripe"
    os.environ["NOVAPANDA_FIAT_URL"] = "https://api.stripe.com/v1"
    os.environ["NOVAPANDA_FIAT_API_KEY"] = api_key
    os.environ["NOVAPANDA_SANDBOX_PARTNER"] = "stripe-sandbox"

    app = create_app_from_config(NodeConfig.from_env())
    tc = TestClient(app)

    print("=" * 64)
    print("Stripe LIVE sandbox — full NovaPanda exchange")
    print("=" * 64)

    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)

    ex = client.propose(
        provider=provider.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE,
        price={"amount": 100, "currency": "USD"},
        idempotency_key="stripe-live-" + uuid.uuid4().hex[:8],
        settlement={"preferred_rails": ["fiat-s1-sandbox"], "currency": "USD"},
    )
    eid = ex["exchange_id"]
    print(f"exchange_id={eid}")
    client.contract(eid)
    provider.contract(eid)
    print("escrow → Stripe authorize …")
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, GOOD)
    client.verify(eid)
    settled = client.confirm(eid)
    receipt = settled.get("settlement_receipt") or {}
    print(
        f"SETTLED partner={receipt.get('partner')} rail={receipt.get('rail')} "
        f"env={receipt.get('environment')} amount={receipt.get('amount')}"
    )
    assert receipt.get("environment") == "sandbox"
    assert receipt.get("partner") == "stripe-sandbox"
    print("\nOK: real Stripe sandbox + NovaPanda SETTLED (sandbox ≠ bank deposit)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stripe 真网沙箱试跑")
    parser.add_argument("--probe-only", action="store_true", help="仅测 PaymentIntent，不跑交割")
    args = parser.parse_args()

    api_key = _load_api_key()
    masked = api_key[:12] + "…" + api_key[-4:]
    print(f"using key {masked}")

    try:
        probe_stripe(api_key)
        print("probe OK")
        if args.probe_only:
            return
        full_exchange(api_key)
    except SettlementError as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        print(
            "\n常见原因：密钥错/过期、账户未开 sandbox、或测试 PM 不可用。"
            "\n可在 Dashboard → Developers → API keys 重新生成 sk_test。",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
