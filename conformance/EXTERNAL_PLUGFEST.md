# External Plugfest Guide (draft)

面向第三方实现与集成伙伴的 **对外 plugfest** 准备说明（未正式发布）。

## 目标

验证两个独立 Troodon 节点 + 可选结算/LLM/见证服务能否：

1. 通过 manifest 发现能力
2. 完成 propose → contract → escrow → deliver → verify → confirm
3. 产出可离线复验的 SETTLED VDC
4. 写入信誉链

## 参考脚本

```bash
# 本地 8 场景（含 energy / witness / LLM）
python demo/plugfest.py

# TS SDK 生命周期 + auth
cd sdk/typescript && npm run build && node test/plugfest_lifecycle.mjs http://127.0.0.1:8000
```

## 建议场景矩阵

| 场景 | 说明 |
|------|------|
| invoice_happy | 结构化数据 + schema 验收 |
| energy_dc | ISO15118 adapter + 物理验收 |
| witness_stake | witness v2 + stake 锁定 |
| llm_field_match | 内置 LLM judge |
| llm_http_openai | OpenAI-compat 网关 |
| confirm_timeout | VERIFIED 后 confirm 超时退款 |
| actuation_robot | 物理 actuation 规则 |
| auth_lifecycle | 带鉴权 TS SDK |

## 环境变量清单

见 `troodon/config.py` 模块 docstring（`TROODON_*`）。

## 对外举办 checklist

- [ ] 公布测试向量：`tests/fixtures/`
- [ ] 提供 fake x402/AP2/fiat 网关（`troodon/*_fake.py`）
- [ ] 提供 `llm_fake` OpenAI-compat 端点
- [ ] 运行 `python -m conformance.run` 全绿
- [ ] 记录互操作矩阵（实现 × 场景）

## 状态

**草案** — 待商标/域名/对外节点 URL 决策后发布。
