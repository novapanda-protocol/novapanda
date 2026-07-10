# Profile NP-BUNDLE · 组合交割

> **版本**：0.1 · 2026-07-08  
> **状态**：由 `docs/scenarios/bundle.md` 升格的规范性 Profile 草案  
> **依赖**：编排方与验证方须理解 NP-MIN；节点索引能力可选，建议兼具 NP-NODE。

---

## 1. 问题

一个业务目标 = **多笔**对等交割（各一张 VDC）+ 依赖 + 可选人类终审。  
禁止用巨型单一状态机替代原子 VDC。

## 2. Bundle 对象

```json
{
  "bundle_version": "0.1",
  "goal_id": "goal_…",
  "correlation_id": "site-patrol-42",
  "title": "到场巡检闭环",
  "exchange_ids": ["ex_a", "ex_b", "ex_c"],
  "depends_on": {
    "ex_c": ["ex_a", "ex_b"]
  },
  "success_rule": "all_settled",
  "human_gate": {
    "required": true,
    "agent_id": "ed25519:…",
    "status": "pending"
  },
  "vdc_ids": []
}
```

| 字段 | 要求 |
|------|------|
| `correlation_id` | MUST：跨交换关联；宜写入各单笔扩展元数据 |
| `depends_on` | 启动约束由**编排方**执行；节点 MAY 忽略 |
| `success_rule` | MUST 可解释：`all_settled` / `quorum:n` … |
| `human_gate` | 若 required：目标完成声明的附加签/拒；MUST NOT 回滚已签 VDC；`required=false` 时 `status` MAY 为 `skipped` |
| `vdc_ids` | 完成后回填；目标证明 = VDC 集合 (+ gate) |

**Bundle 不是 VDC。** 第三方复验仍针对每张 VDC。

## 3. prior_vdc_refs

下一笔 terms MAY 含：

```json
"prior_vdc_refs": [
  { "vdc_id": "vdc_…", "claim": "inspection_passed", "required": true }
]
```

若 `required=true`，对端在 contract 前 MUST 能对该 VDC 独立 reverify；失败则拒收。

## 4. 节点关系

| | MUST | MAY |
|--|:----:|:---:|
| Agent 持有 Bundle | ✓ | |
| 单笔 Exchange API | ✓ 不变 | |
| 节点存储 Bundle 索引 | | ✓ |
| 节点执行 depends_on | | 默认 **否** |

## 5. 失败原则

- 子交换失败 → 商务决定其余腿；已 SETTLED VDC 事实仍在。  
- 人类否决 goal → `gate=rejected`；不得伪造未发生的交付。  
- 换节点：携带 VDC 集合 + Bundle 描述即可。

## 6. 非目标

- ROS / 飞控 / 智驾会话  
- 协议币分账  
- 强制子交换同一节点  
- Claim 转让（→ 未来 NP-CLAIM-XFER）

## 7. Manifest

```json
"profiles": ["NP-MIN", "NP-BUNDLE"]
```

支持索引时建议同时宣告 `NP-NODE`。

## 8. 旗舰场景（非 MUST）

- 嵌套 B 尽调 `S-nested-soft-diligence`  
- 嵌套 A 巡检 `S-nested-site-patrol`  

见 [docs/scenarios/](../docs/scenarios/)。

## 9. 叙事原文

说明性原文保留：[docs/scenarios/bundle.md](../docs/scenarios/bundle.md)。**冲突时以本 Profile 为准。**
