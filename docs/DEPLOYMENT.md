# Deployment Guide · NovaPanda reference node

> **Scope:** ops body (zero-node / self-hosted). Protocol truth remains **VDC + SPEC**, not this host.  
> **Do not** commit secrets. Use `.env.example` → local `.env`, or `deploy/env/production.env.example`.

---

## 1. Architecture reminder

```text
Agents (keys local) ──HTTP──► NovaPanda Node (orchestration body)
                                │
                                ├─ ExchangeEngine + state_machine (CORE)
                                ├─ SettlementAdapter (mock / x402 / fiat / wallet)
                                ├─ Marketplace (optional NOVAPANDA_MARKETPLACE=1)
                                └─ Wallet RPC / Paymaster / Fiat gateway (adapters)
```

Settlement, wallets, and marketplace **never** rewrite `state_machine.TRANSITIONS` (ADR-0002).

---

## 2. Secret slots (production)

| Slot | Env | Notes |
|------|-----|--------|
| Operator DB | `NOVAPANDA_OPERATOR_DB` | Console / ops persistence; body-layer |
| Exchange DB | `NOVAPANDA_DB` | SQLite path (or future Postgres DSN via body) |
| Reputation DB | `NOVAPANDA_REPUTATION_DB` | Optional; defaults with DB |
| Admin API | `NOVAPANDA_ADMIN_TOKEN` | Protect `/admin/*` |
| EVM RPC | `NOVAPANDA_EVM_RPC_URL` | Read / estimate; broadcast needs signer |
| Solana RPC | `NOVAPANDA_SOLANA_RPC_URL` | Same |
| Signer | `SIGNER_BROADCAST_KEY` | **Host-only**; wire into `signer_broadcast` callback |
| Stripe live | `STRIPE_LIVE_SECRET` / `NOVAPANDA_FIAT_API_KEY` | Licensed rail; PCI scope |
| Fiat mode | `NOVAPANDA_FIAT_COMPLIANCE=stripe` | vs `stub` |

Templates: [`.env.example`](../.env.example) · [`deploy/env/production.env.example`](../deploy/env/production.env.example).

---

## 3. Minimal bring-up

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env        # edit secrets locally

export NOVAPANDA_AUTH=1
export NOVAPANDA_DB=./data/novapanda.sqlite
uvicorn novapanda.node.app:create_app_from_config --factory --host 0.0.0.0 --port 8000
```

Health: `GET /health` · Manifest: `GET /.well-known/novapanda.json`.

Docker path: [`deploy/docker/`](../deploy/docker/) · AWS notes: [`deploy/AWS_P2_OPS.md`](../deploy/AWS_P2_OPS.md).

---

## 4. Enabling marketplace (NP-REP)

```bash
export NOVAPANDA_MARKETPLACE=1
export NOVAPANDA_REP_MIN_SCORE=0.5   # optional gate + match floor
```

See [`docs/marketplace-flow.md`](marketplace-flow.md).

---

## 5. Autonomy → real settlement (`ExchangeRunner`)

The autonomy stack (`novapanda.autonomy`) is **orchestration-only**. Inject a runner that calls your node / `ExchangeEngine`:

```python
from novapanda.autonomy import SupplyChainOrchestrator, TaskSpec, default_auctioneer
from novapanda.marketplace.types import PriceQuote

class NodeExchangeRunner:
    """Sketch: map each awarded subtask to propose→…→SETTLED on a live engine."""

    def __init__(self, engine, client_id, identities_by_agent):
        self.engine = engine
        self.client_id = client_id
        self.ids = identities_by_agent

    def start_leg(self, *, sub, provider_agent_id, client_agent_id, price, correlation_id):
        # 1) engine.propose(...)  2) contract  3) escrow  4) deliver/verify/confirm
        # Return {"exchange_id", "state", "vdc_id", "result"}
        raise NotImplementedError("wire to ExchangeEngine / HTTP SDK")

    def poll_leg(self, exchange_id: str):
        ex = self.engine.get(exchange_id)
        return {"state": ex.state, "vdc_id": (ex.vdc or {}).get("vdc_id")}
```

Tests use `InMemoryExchangeRunner` — keep production keys out of CI.

---

## 6. Pre-publish

Follow [`conformance/PRE_PUBLISH_CHECKLIST.md`](../conformance/PRE_PUBLISH_CHECKLIST.md). Trademark: **do not use ®** until counsel confirms registration.
