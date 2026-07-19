# 生态适配器 · 共建指南（informative）

> **结论**：要提前做的是**适配器契约与登记面**，不是为每个厂商写完整驱动。  
> **铁律**：适配器只翻译；CORE / VDC / Exchange SM **不得**因设备而分叉。  
> **代码**：[`novapanda/ecosystem/`](../novapanda/ecosystem/) · 社区目录 [`adapters/`](../adapters/)  
> **已有接入面**：[`novapanda/surfaces/`](../novapanda/surfaces/)（MCP / A2A / Skill / `ProviderAdapter`）

---

## 1. 为什么「先写一部分」

| 做法 | 结果 |
|------|------|
| 每个 IOT/机器人厂商各写一套状态机 | 协议碎裂，无法互验 |
| 只写 OpenClaw，等有需求再散装 | 后来者没有挂钉，重复造轮子 |
| **契约 + 登记表 + 2～3 个参考适配器** | 社区可 PR；语义仍归 OPERATIONS |

目标生态（Agent / 车 / 机器人 / 传感器 / 家居网关）共用一张操作表：  
`propose`…`confirm` · 见 `novapanda.surfaces.base.OPERATIONS`。

---

## 2. 分层（谁写什么）

```text
┌─ 社区 adapters/<name>/ ─────────────────────────────┐
│  manifest.json · work_fn 或 CLI 壳 · 可选 README     │
│  （厂商 SDK / MQTT / ROS2 Topic → deliverable）       │
└───────────────────────┬─────────────────────────────┘
                        │ ProviderAdapter / pair_cli / Skill
┌───────────────────────▼─────────────────────────────┐
│  novapanda.surfaces · AdopterRuntime · SDK            │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│  CORE：Identity · Exchange · VDC · reverify           │
└─────────────────────────────────────────────────────┘
```

| 角色 | 负责 | 不负责 |
|------|------|--------|
| Steward / 本仓库 | 契约、登记、参考适配器、向量 | 每个 OEM 的量产驱动 |
| 社区 / 厂商 | `adapters/<slug>/` PR | 改 TRANSITIONS / 平行 Record API |
| 设备固件 | 边缘签验（NP-LITE） | 完整节点 |

---

## 3. 适配器类型（先覆盖这些）

| 类型 | 说明 | 本仓库种子 |
|------|------|------------|
| **agent_host** | OpenClaw / IDE / 编排器 | `adapters/openclaw`（指向 demo） |
| **work_fn** | 任意 Python 可调用交付 | `adapters/mqtt_iot`（示例） |
| **robot_bus** | ROS2 / DDS 事件 → deliverable | `adapters/ros2`（骨架，待硬件伙伴填） |
| **http_surface** | 已有 MCP/A2A/Skill | `novapanda/surfaces/*` |

**不做**：为每个品牌单独 fork CORE。

---

## 4. 社区如何加一个适配器

1. 复制 `adapters/_template/` → `adapters/<slug>/`  
2. 填 `manifest.json`（见 schema 字段）  
3. 实现最小 `work_fn` **或** 文档说明如何调 `pair_cli` / surfaces  
4. 勾选 [`conformance/adapter_author_checklist.json`](../conformance/adapter_author_checklist.json)  
5. PR：附 `settlement: mock|sandbox|…` 与自测命令  
6. Steward 合并后出现在：

```bash
python -m novapanda.ecosystem
python -m novapanda ecosystem list
```

红线同 [`BINDING-SKILL`](../spec/BINDING-SKILL.md)：私钥不上云；禁止口头 SETTLED。

---

## 5. 与宣传节奏

软发阶段：**契约齐 + OpenClaw/MQTT 示例可跑** 即可征集共建。  
ROS2 / 厂商 SDK 等有真机伙伴再加深——骨架占坑，不假装已认证。

边缘 MCU 边界见 [`lite-embedded-boundary.md`](lite-embedded-boundary.md)。
