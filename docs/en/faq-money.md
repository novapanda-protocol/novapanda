# Where is the money? · NovaPanda FAQ

> **Status**: public note · 2026-07-10 · **non-normative** (narrative; MUST follow [Constitution](../constitution.html) · [SPEC](https://github.com/novapanda-protocol/novapanda/blob/main/spec/CORE.md))  
> **Web**: [faq-money.html](faq-money.html) · **中文**: [../faq-money.md](../faq-money.md)

---

## Three sentences

1. **The protocol does not mint money, custody network funds, or tax each exchange.**  
2. **VDC anchors “delivery happened”**; fiat / USDC / mock are **pluggable settlement legs** below the exchange state machine.  
3. **The operating company may charge for services** (hosted node, certification, routing, enterprise support) — **not** for “owning the protocol.”

---

## FAQ

### Does user payment flow through you?

**Usually not.** Public Trial and the zero node default to **mock or sandbox** (e.g. Stripe test mode). Production settlement goes through **licensed or declared partners**; the protocol only requires SETTLED to bind `vdc_id` + an honest `settlement_receipt`.

### How do you make money?

| Revenue | What it is | What it is not |
|---------|------------|----------------|
| Hosted reference node | Ops, quota, audit, reputation index | Protocol license fee |
| Compatibility certification (UC-40) | Steward review + optional mark license (may be free early) | Paywall to join |
| Settlement routing / reconcile export | Help partners translate VDC to invoices | FX spread |
| Enterprise support / private deploy | Red Hat model | Private protocol |

### Relation to x402 / on-chain payment stacks?

**Interoperate, not replace.** x402 may be one settlement leg; differentiation is **verifiable delivery + cross-agent reputation + settlement-agnostic open ontology** — not “another charge API.”

### Is Claim your token?

**No.** Claim is **transfer of settlement rights anchored to a signed VDC**, not a circulating token.

### Why must Manifest say mock / sandbox?

**Honesty.** Claiming production settlement while only running mock leads to downgrade or removal in the [compatibility matrix](https://github.com/novapanda-protocol/novapanda/blob/main/docs/compatibility.md) and certification review.

---

## Diagram

```text
  Client ──escrow──► settlement partner / mock / sandbox
       │
       └── Exchange state machine ──► VDC (offline reverify)
                ▲
                └── Protocol core: not which bank holds funds — whether delivery is provable
```

---

## Related

- [Constitution](../constitution.html) · [Scenarios](../scenarios/overview.html)  
- [Compatibility registry](https://github.com/novapanda-protocol/novapanda/blob/main/docs/compatibility.md)  
- [Developer Trial](../trial.html)

---

*Public FAQ EN · source: `internal/design/BA-钱在哪-FAQ-EN.md`*
