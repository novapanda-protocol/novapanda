# Call for a Second Implementation · 第二实现公开征集

> **一句话**：用你自己的语言/运行时，跑通「陌生 Agent → SETTLED VDC → 离线复验」，登记一行即可。  
> **不要求**：用我们的节点、付认证费、持牌清算、或任何协议代币。  
> **状态**：v0.2 材料齐备 · **正在征集**  
> **EN stub**：[`docs/en/call-for-second-impl.md`](../docs/en/call-for-second-impl.md)

---

## Why this matters

One codebase cannot prove a protocol. Compatibility lives in **vectors + independent nodes**, not in a single reference repo.  
We already ship a Python reference and a TypeScript client. The missing piece is **your** implementation in the [compatibility matrix](../docs/compatibility.md).

---

## What you submit (minimum)

| Deliverable | Bar |
|-------------|-----|
| One SETTLED lifecycle | propose → … → confirm · dual-signed VDC |
| Offline reverify | no live node required to check the VDC |
| Honest Manifest | profiles you claim = cases you ran |
| One matrix row | PR [`docs/compatibility.md`](../docs/compatibility.md) · note `settlement: mock \| sandbox \| licensed partner` |

Optional: Bundle · PHYS · LITE · MCP · sandbox rails — only if you declare them.

---

## 48-hour path

1. Read [`SECOND_IMPL_STARTER.md`](SECOND_IMPL_STARTER.md) (reading order + anti-patterns).  
2. Tick [`second_impl_checklist.json`](second_impl_checklist.json) `must[]` (SI-01…SI-05).  
3. Scenario ideas / plugfest matrix: [`EXTERNAL_PLUGFEST.md`](EXTERNAL_PLUGFEST.md).  
4. Open a PR with one table row + link to CI log or vector dump.

Reference commands (Python; other languages: equivalent assertions against [`VECTORS.md`](VECTORS.md)):

```bash
pip install -e ".[dev]"
python -m novapanda conformance report --run
python -m novapanda manifest validate ./my-manifest.json --require-profiles
```

TypeScript **client** L0 (not a second node, but a second language surface):

```bash
cd sdk/typescript && npm ci && npm run attest:l0
# optional live node: node test/plugfest_lifecycle.mjs http://127.0.0.1:8765
```

---

## Who we especially want

- **Second node** in Rust / Go / Java / Kotlin / Swift / etc.  
- **Agent frameworks** that already have wallets or tool runners  
- **Vertical bodies** (EV / energy / robotics) that can produce real meter or sensor evidence  
- **Settlement partners** willing to run **sandbox** with honest labeling  

Not looking for: a second copy of our API shape that invents a parallel `Record` state machine — see [`docs/record-vs-vdc.md`](../docs/record-vs-vdc.md).

---

## Contact

- Technical: GitHub issue / PR per [`CONTRIBUTING.md`](../CONTRIBUTING.md)  
- Steward schedule / public URL: announced when ready (trademark & domain discipline in [`PRE_PUBLISH_CHECKLIST.md`](PRE_PUBLISH_CHECKLIST.md))

**Forward this file.** Detailed runbooks live next to it; this page is the invite.
