# Profile NP-PHYS · 物理证据交割

> **版本**：0.1 · 2026-07-08  
> **状态**：能力档成文；实现已有 `v3/physical` 骨架与 plugfest 腿，**生产宣称须自测向量通过**  
> **依赖**：NP-MIN  
> **非目标**：飞控、智驾控制栈、功能安全认证、道路/空域许可（见 Charter）

---

## 1. 问题

能源 / 机器人 / 车充等交付物携带**计量或现场证据**字段；需在 VDC / deliverable 上可复验，而非口头「充好了」。

## 2. 要求

实现 MUST：

1. 对宣告的物理 `resource_type`（如 `energy.*` / `actuation.*`）在验收前运行物理 deliverable 校验（参考 `validate_physical_deliverable`）。  
2. 失败时 `passed=false` 且 checks 可回放。  
3. Manifest 列出支持的物理类型；未列出的 MUST NOT 默认接受。  
4. 不把控制回路协议（ISO 15118 会话等）塞进 CORE 状态机——仅作 Adapter / deliverable 证据来源。

实现 SHOULD：

- plugfest 中 energy / actuation 腿可复现。  
- metered 字段（量、单位、时间窗）进入 result_hash 覆盖范围。

实现 MAY：

- ISO15118 适配器、现场传感器原数据外链（哈希上链）。

## 3. 与灯塔场景

嵌套 A 巡检等成员场景可引用本 Profile；人类终审仍属 Bundle `human_gate`，不属本档。

## 4. Manifest

```json
"profiles": ["NP-MIN", "NP-PHYS"]
```

## 5. 测试挂钩

现有：`tests` 中 physical / iso15118 / plugfest energy·actuation。  
正式 Cx：**C9** · `tests/test_phys_c9.py`（C9-01…05）。

---

*成文 · 宣称兼容前跑通物理向量（suite 已挂）*
