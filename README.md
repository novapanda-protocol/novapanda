# NovaPanda · Intelligent Open Delivery Protocol

> **Working name:** NovaPanda — *Intelligent Open Delivery Protocol*  
> **North star:** A shared, **verifiable delivery language** for agents, devices, and models — **before** unifying money.  
> We do not issue a protocol token. We do not custody funds. We do not take a protocol cut.  
> The unit of truth is a **VDC** — dual-signed, independently re-verifiable **off any node**.

[![License](https://img.shields.io/badge/code-Apache--2.0-blue.svg)](LICENSE)
[![Spec](https://img.shields.io/badge/spec-CC%20BY%204.0-green.svg)](spec/SPEC.md)
[![Litmus](https://img.shields.io/badge/litmus-stranger%20agent-black.svg)](CHARTER.md)

**Site:** [novapanda.io](https://novapanda.io) · [Vision](https://novapanda.io/vision.html) · [Constitution](https://novapanda.io/constitution.html) · [Trial](https://novapanda.io/trial.html) · [Zero node](https://node.novapanda.io)

<details>
<summary><strong>中文摘要</strong></summary>

**NovaPanda 智能开放交割协议**：让智能体 / 智能设备在**无预建关系**下完成跨主体价值交换。第一公民是 **VDC（可验证交割凭证）**，不是账户余额或代币。规范 CC BY 4.0 · 代码 Apache-2.0。商标申请中，**勿用 ®**。公开 Trial 仅 **mock 结算**。

</details>

---

## The problem

Decentralized **Agent-to-Agent** commerce fails in practice because:

1. **Delivery is unverifiable** — “I sent the result” is a chat message, not a credential.
2. **Settlement is entangled with trust** — escrow lives in silos; strangers cannot complete atomic handoff.
3. **Discovery without reputation is adversarial** — Sybil / wash trading collapses open markets.
4. **Large goals need supply chains** — one Agent cannot own every skill; DAG split + auction must still land on **atomic VDCs**.

NovaPanda attacks (1)–(4) with a minimal CORE and pluggable adapters — not another L1 token.

---

## Architecture (2026 stack)

```text
┌─────────────────────────────────────────────────────────────────┐
│  Autonomy (novapanda/autonomy)                                  │
│  TaskDispatcher → Auctioneer → SupplyChainOrchestrator          │
│  (DAG split · MatchRouter auction · Aggregate)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ ExchangeRunner (inject real rails)
┌────────────────────────────▼────────────────────────────────────┐
│  CORE                                                           │
│  Identity (Ed25519) · Exchange state machine · VDC dual-sign    │
│  Verifier (schema / optional LLM) · offline reverify            │
└───────┬─────────────────────┬─────────────────────┬─────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
  NP-SETTLE adapters    NP-REP marketplace     Wallet body
  mock·x402·fiat·wallet ScoreEngine·Sybil      EVM/Solana RPC
  (ADR-0002)            MatchRouter·Sink       Paymaster·Fiat GW
```

| Layer | What it guarantees | What it refuses |
|-------|--------------------|-----------------|
| **VDC + SM** | Atomic, dual-signed delivery facts | Protocol token / fee |
| **Reputation** | Amount-weighted score · wash/Sybil penalties | Writing into `TRANSITIONS` |
| **Wallet** | Unified Smart Account · USDC gas · Stripe slots | Replacing VDC truth |
| **Autonomy** | Split → auction → multi-VDC aggregate | One mega state machine |

Normative entry: [`CHARTER.md`](CHARTER.md) · [`spec/SPEC.md`](spec/SPEC.md) · Profiles under [`profiles/`](profiles/).  
Open-source boundary: [`docs/OPEN_SOURCE_SCOPE.md`](docs/OPEN_SOURCE_SCOPE.md).

---

## Quick start

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
pip install -e ".[dev]"

pytest -q                          # full suite
python demo/run_demo.py            # stranger-agent delivery
python -m novapanda.reverify demo/out/settled_vdc.json \
  --deliverable demo/out/deliverable.json
```

```bash
cd sdk/typescript && npm ci && npm run build && npm test
cd sdk/typescript && npm run attest:l0    # L0: dual-sign + offline reverify
```

### Config templates (no secrets in git)

```bash
cp .env.example .env
# Production host: deploy/env/production.env.example
```

Key slots: `NOVAPANDA_OPERATOR_DB`, `NOVAPANDA_EVM_RPC_URL` / `NOVAPANDA_SOLANA_RPC_URL`, `SIGNER_BROADCAST_KEY`, `STRIPE_LIVE_SECRET`, `NOVAPANDA_FIAT_COMPLIANCE`.  
Full guide: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

### Run a reference node

```bash
export NOVAPANDA_AUTH=0            # dev only
uvicorn novapanda.node.app:create_app --factory --reload

# production-shaped
export NOVAPANDA_AUTH=1
export NOVAPANDA_DB=./data/novapanda.sqlite
uvicorn novapanda.node.app:create_app_from_config --factory
```

Optional marketplace: `NOVAPANDA_MARKETPLACE=1` → see [`docs/marketplace-flow.md`](docs/marketplace-flow.md).

### Wire autonomy to a real settlement rail

Autonomy **does not** embed the state machine. Inject an `ExchangeRunner` that drives `ExchangeEngine` (or HTTP SDK) per awarded subtask — sketch in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) §5. CI uses `InMemoryExchangeRunner` only.

```bash
pytest tests/test_autonomy_dispatch.py -q
```

---

## Repository map

```
novapanda/           Reference implementation (Python)
  adopter/           Body-layer runtime (Outbox · Vault · Skill)
  autonomy/          Task split · auction · supply-chain orchestrator
  marketplace/       NP-REP discovery · reputation · Sybil · federation
  wallet/            Multi-chain account · Paymaster · fiat compliance
  node/              Operable HTTP body (zero-node)
sdk/typescript/      @novapanda/sdk
spec/                Normative SPEC + JSON Schema + BINDING-*
profiles/            NP-MIN · NODE · BUNDLE · SETTLE · LITE · …
demo/openclaw_pair/  Car × OpenClaw pair CLI + Skill template
demo/ · tests/ · conformance/
docs/                Implementer · adopter closed-loop · openclaw checklist
```

---

## Second implementation (open call)

We want **independent** nodes and clients — any language — that prove the litmus without our runtime.

**Start here (forwardable):** [`conformance/CALL_FOR_SECOND_IMPL.md`](conformance/CALL_FOR_SECOND_IMPL.md) · [EN](docs/en/call-for-second-impl.md)  
Then: [`SECOND_IMPL_STARTER.md`](conformance/SECOND_IMPL_STARTER.md) · [`EXTERNAL_PLUGFEST.md`](conformance/EXTERNAL_PLUGFEST.md) · register in [`docs/compatibility.md`](docs/compatibility.md).  
Robot / drone edge boundary: [`docs/lite-embedded-boundary.md`](docs/lite-embedded-boundary.md).

```bash
python -m novapanda conformance report --run          # reference baseline + registration_draft
python -m novapanda manifest validate ./manifest.json --require-profiles
```

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [`CHARTER.md`](CHARTER.md) | In/out of scope · Litmus |
| [`docs/IMPLEMENTER_GUIDE.md`](docs/IMPLEMENTER_GUIDE.md) | 30-minute implementer path |
| [`conformance/CALL_FOR_SECOND_IMPL.md`](conformance/CALL_FOR_SECOND_IMPL.md) | Public call for a second implementation |
| [`demo/openclaw_pair/README.md`](demo/openclaw_pair/README.md) | Car × OpenClaw install + Skill shell |
| [`spec/BINDING-OPENCLAW.md`](spec/BINDING-OPENCLAW.md) | OpenClaw binding (informative) |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Production env · secrets · runner injection |
| [`docs/OPEN_SOURCE_SCOPE.md`](docs/OPEN_SOURCE_SCOPE.md) | What is open vs body-private |
| [`docs/marketplace-flow.md`](docs/marketplace-flow.md) | Discover → propose → Sink |
| [`spec/SPEC.md`](spec/SPEC.md) | Protocol |
| [`conformance/`](conformance/) | Vectors · certification · pre-publish checklist |

---

## Brand & legal

**NovaPanda** is the protocol **working name**. Trademark application in progress in China — **not** a registered mark; **do not use ®**. Public trial settlement is **mock-only**. See [`conformance/PRE_PUBLISH_CHECKLIST.md`](conformance/PRE_PUBLISH_CHECKLIST.md).

## License

- **Code:** Apache-2.0  
- **Specification:** CC BY 4.0  
- Community: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) · Security: [`SECURITY.md`](SECURITY.md)
