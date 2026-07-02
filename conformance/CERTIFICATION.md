# NovaPanda Conformance & Certification (pre-publish)

本目录说明 **NovaPanda-compatible** 一致性认证的准备材料；**尚未对外发布**，不含已注册商标图样。

## Conformance Suite

运行全部 C1–C7：

```bash
python -m conformance.run
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

通过 C1–C7 的第三方实现可申请 **NovaPanda-compatible** 标识（见 `TRADEMARK.md` 占位）。

## 认证流程（草案）

1. 自测：`python -m conformance.run` + `python demo/plugfest.py`
2. TS 交叉：`cd sdk/typescript && npm run build && npm test`
3. 提交实现版本、manifest 样例、结算 rail 说明
4. Steward 复核后授予兼容标识（待基金会/商标就绪）

## 相关

- [`PRE_PUBLISH_CHECKLIST.md`](PRE_PUBLISH_CHECKLIST.md) — **公开前检查清单（商标/域名/表述红线）**
- `EXTERNAL_PLUGFEST.md` — 对外 plugfest 指南
- `TRADEMARK.md` — 商标与标识占位
- `spec/SPEC.md` — 协议规范
