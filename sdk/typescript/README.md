# @novapanda/sdk

TypeScript **client** for NovaPanda: canonical JSON, Ed25519 auth, VDC dual-sign, offline reverify.

Not a second full node — use it against a reference (or any) HTTP body that speaks `NP-HTTP`.

## Install / build

```bash
npm ci
npm run build
npm test
```

## L0 self-attest (SETTLED + offline reverify)

**Offline (no node)** — dual-sign + `reverify` against the Python parity fixture:

```bash
npm run attest:l0
```

**Against a live auth node** (reference uvicorn or plugfest host):

```bash
# terminal A
export NOVAPANDA_AUTH=1
uvicorn novapanda.node.app:create_app --factory --host 127.0.0.1 --port 8765

# terminal B
npm run build
node test/plugfest_lifecycle.mjs http://127.0.0.1:8765
```

Pytest wrapper (repo root, needs `dist/` built): `pytest tests/test_ts_plugfest.py -q`.

## Register

After a green run, PR one row to [`docs/compatibility.md`](../../docs/compatibility.md)  
(`settlement: mock` unless you truly ran sandbox/licensed rails).  
Call: [`conformance/CALL_FOR_SECOND_IMPL.md`](../../conformance/CALL_FOR_SECOND_IMPL.md).
