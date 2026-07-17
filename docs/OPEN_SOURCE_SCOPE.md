# Open-source scope · NovaPanda

> What this public repository **is** and **is not**. Aligns with [`CHARTER.md`](../CHARTER.md).

## In the open repo

| Asset | License / note |
|-------|----------------|
| Protocol SPEC + schemas | CC BY 4.0 |
| Reference implementation (`novapanda/`) | Apache-2.0 |
| TypeScript SDK | Apache-2.0 |
| Profiles, conformance vectors, demos | As marked |
| Marketing site sources under `docs/` (HTML) | Present today — ops may split later |
| Design notes for marketplace / wallet / autonomy | Informative |

## Not required to interoperate

- Any single hosted node (including `node.novapanda.io`)
- Stripe / RPC / signer keys
- Operator DB contents
- Proprietary partner licenses

## Body vs protocol

| Layer | Open? | Role |
|-------|-------|------|
| VDC + state machine + verify | **Yes** | Interop truth |
| Settlement / wallet / marketplace / autonomy | **Yes (adapters)** | Optional; pluggable |
| Production keys, DB backups, brand ops | **Private** | Deployer’s responsibility |

Litmus remains: a stranger agent must complete delivery from **public SPEC alone**.
