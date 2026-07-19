# BINDING-OPENCLAW · OpenClaw / 车结对接入（informative）

> **状态**：v0.1 · 2026-07-19 · **BINDING 层，非 CORE MUST**  
> **纪律**：OpenClaw Skill **≠** 交换状态机；只翻译到本地 CLI / `AdopterSkill`  
> **配套**：[`BINDING-SKILL.md`](BINDING-SKILL.md) · [`../demo/openclaw_pair/`](../demo/openclaw_pair/) · [`../docs/openclaw-adopter-checklist.md`](../docs/openclaw-adopter-checklist.md)

---

## 1. 问题

宿主（OpenClaw 等 Agent 运行时）与智能车要完成跨主体交割时，需要**标准安装面与 Skill 壳**，避免在对话里持钥或另造 Record API。

---

## 2. 分层

```text
OpenClaw Skill / 车侧 CLI
        │  subprocess / AdopterSkill.invoke
        ▼
AdopterRuntime + NovaPandaClient（本地持钥）
        │  NP-HTTP
        ▼
Node body（可选）──► Exchange SM ──► VDC
        │
        └── 离线 reverify（不经节点写路径）
```

| 层 | MAY | MUST NOT |
|----|-----|----------|
| OpenClaw Skill | 调 `pair_cli` / 汇报 `state` | 持私钥；口头 SETTLED |
| 车侧 CLI | Client Runtime；舱确认 | 与 Provider 共用密钥 |
| 结算 | 声明 `mock` / sandbox | 隐瞒 mock |

---

## 3. 标准工件（本仓库）

| 工件 | 路径 | 用途 |
|------|------|------|
| 结对 CLI | [`demo/openclaw_pair/pair_cli.py`](../demo/openclaw_pair/pair_cli.py) | `init` · `run` · `skill` · `car-confirm` |
| OpenClaw Skill 模板 | [`demo/openclaw_pair/SKILL.md`](../demo/openclaw_pair/SKILL.md) | 拷贝到宿主 skills，改路径 |
| 安装说明 | [`demo/openclaw_pair/README.md`](../demo/openclaw_pair/README.md) | 车 / OpenClaw 各装什么 |
| 对接清单 | [`docs/openclaw-adopter-checklist.md`](../docs/openclaw-adopter-checklist.md) | 验收勾选 |
| 边缘边界 | [`docs/lite-embedded-boundary.md`](../docs/lite-embedded-boundary.md) | MCU vs 伴侣机 |
| 向量测试 | [`tests/test_openclaw_pair.py`](../tests/test_openclaw_pair.py) | 同机 SETTLED + reverify |

---

## 4. 推荐动作映射

| 宿主意图 | 标准调用 |
|----------|----------|
| 同机演示交割 | `pair_cli.py run` |
| 列产品面工具 | `pair_cli.py skill --name adopter_list_tools` |
| vault / 导出 / 舱意图 | `adopter_*` via `pair_cli.py skill`（见 `AdopterSkill`） |
| 车侧确认 | `pair_cli.py car-confirm` 或 `--role car` + `adopter_apply_intent` |
| 离线复验 | `python -m novapanda.reverify …` |

全生命周期 propose…confirm 的**参考实现**为 `run`（双 Runtime 同机）。分机拆步为加性演进，不改 CORE。

---

## 5. Conformance

- 参考：`tests/test_openclaw_pair.py`  
- 无单独 C-OPENCLAW Case；语义仍归 C1–C5 / SI-03–04  
- Manifest 若声明 skill/openclaw 传输，**MUST NOT** 暗示宿主已认证安全  

---

*BINDING-OPENCLAW v0.1 · Skill 壳 + pair_cli · 勿云端代签*
