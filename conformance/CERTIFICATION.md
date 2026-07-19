# NovaPanda Conformance & Certification (pre-publish)

本目录说明 **NovaPanda-compatible** 一致性认证的准备材料；**尚未对外发布**，不含已注册商标图样。

## Conformance Suite

运行全部 C1–C8、C10–C12：

```bash
python -m conformance.run
python -m conformance.gap_audit   # T15 套件审计
python -m novapanda conformance report      # 登记用 JSON 报告
python -m novapanda conformance report --run  # 附全套件运行
```

列出映射：

```bash
python -m conformance.run --list
```

| Case | 含义 |
|------|------|
| C1 | 规范化/签名（JSON + CBOR 交叉向量） |
| C2 | VDC schema 合规 |
| C3 | 状态机与超时 |
| C4 | 幂等与 nonce 重放防护 |
| C5 | 验收确定性 |
| C6 | 信誉链与加权聚合 |
| C7 | Manifest 发现与交换 |
| C8 | Bundle 字段与 prior_vdc_refs 复验拒收 |
| C10 | Settlement 幂等 / mock 诚实（NP-SETTLE） |
| C11 | Claim 无锚 / 双花拒绝（mock 向量） |
| C12 | DELEGATE 过期 / 限价 / 轨白名单 |
| C-MCP | MCP 绑定 ≡ SDK（**意向**，未进默认 suite） |

通过 C1–C7 的第三方实现可申请 **NovaPanda-compatible** 标识（见 `TRADEMARK.md` 占位）；宣告 NP-BUNDLE 时尚须 C8；宣告 NP-SETTLE / NP-DELEGATE 时建议附 C10/C12 日志。宣告 MCP 接入时参阅 [`C-MCP.md`](C-MCP.md)（informative）。

## 认证流程（草案）

详见 [`internal/design/UC-40-认证流程设计.md`](../internal/design/UC-40-认证流程设计.md)（L0–L3 分级 · Steward 复核表）。

1. 自测：`python -m conformance.run` + `python -m conformance.gap_audit` + （可选）`python demo/plugfest.py`
2. TS 交叉：`cd sdk/typescript && npm run attest:l0`（含离线 reverify）；可选 `pytest tests/test_ts_plugfest.py`
3. 提交实现版本、manifest 样例、结算 rail 说明 → PR `docs/compatibility.md`
4. Steward 复核后授予 Compatible（L1/L2）；Certified（L3）待商标/合同就绪

## 相关

- [`VECTORS.md`](VECTORS.md) — 黄金向量与 SPEC / Profile 挂钩
- [`PRE_PUBLISH_CHECKLIST.md`](PRE_PUBLISH_CHECKLIST.md) — **公开前检查清单（商标/域名/表述红线）**
- `CALL_FOR_SECOND_IMPL.md` — 第二实现公开征集（可转发）
- `EXTERNAL_PLUGFEST.md` — 对外 plugfest 指南
- `TRADEMARK.md` — 商标与标识占位
- [`../profiles/`](../profiles/) — NP-MIN / NP-NODE / NP-BUNDLE
- `spec/README.md` — 规范分卷索引（CORE / NP-HTTP / NP-OPS / NP-V2）
- [`spec/schemas/README.md`](../spec/schemas/README.md) — JSON Schema 索引（bundle / claim / pod · v0.1）
- [`C-MCP.md`](C-MCP.md) — MCP 绑定一致性向量（意向）
- `spec/SPEC.md` — 兼容入口（索引）
