# NovaPanda Exchange Scenarios · 交换场景图谱

> **单一真相源**：本目录开源发布，供官网 Pages、零号节点 `/node/scenarios`、开发者文档共用。  
> **读图顺序**：总览三图 → 场景矩阵 → 分场景说明。  
> 设计说明（内部演进记录）见仓库策略；公开以本目录与 [`catalog.json`](catalog.json) 为准。

## 这是什么

NovaPanda 不规定「用什么币付钱」，而规定：**陌生智能体 / 智能 IoT 如何留下一张可独立复验的交付收据（VDC）**。

北极星表述：**一切智能体与智能 IoT，无需人参与也能自主交割。人制定规则与终审 · 交换过程可由机器对机器完成。**

下面所有场景共用同一套状态机：

```text
PROPOSED → CONTRACTED → ESCROWED → DELIVERED → VERIFIED → SETTLED
（分支：REJECTED · EXPIRED_REFUNDED · CANCELLED · DISPUTED）
```

## 图目录（逐步补齐 SVG）

| 图 | 文件 | 命题 |
|----|------|------|
| 生命周期 | [`figures/01-lifecycle.svg`](figures/01-lifecycle.svg) | 所有场景共用主路径 |
| 陌生人 | [`figures/02-strangers.svg`](figures/02-strangers.svg) | 无预建关系也可交割 |
| 分层 | [`figures/03-layers.svg`](figures/03-layers.svg) | VDC 在上，清算可插拔 |
| 矩阵 | [`figures/04-matrix.svg`](figures/04-matrix.svg) | 场景 × 证据形态 |
| IoT 生态 | [`figures/05-iot-ecosystem.svg`](figures/05-iot-ecosystem.svg) | 车·无人机·机器人·软件 Agent |
| 嵌套海报 | [`figures/06-poster-nested.svg`](figures/06-poster-nested.svg) | 一笔业务 · 多张收据 |
| 智能万物交换 | [`../figures/brand/novapanda-intelligent-everything-exchange-zh.webp`](../figures/brand/novapanda-intelligent-everything-exchange-zh.webp) | 官网愿景页主视觉 · 横向 |
| 交付与清算 | [`figures/novapanda-exchange-layers-settlement-zh.webp`](figures/novapanda-exchange-layers-settlement-zh.webp) | 官网场景页 · 交割怎么叠、钱在哪一层 |

组合约定（开源草案）：[`bundle.md`](bundle.md) · 旗舰：`S-nested-soft-diligence` / `S-nested-site-patrol`

**生态八域（公开）**：API / MCP / Skill / 工作流 / OTA / P2P… 如何挂接而不膨胀内核 → [`ecosystem-eight-domains.md`](ecosystem-eight-domains.md) · [网页版](ecosystem-eight-domains.html)

> SVG 按分期绘制；缺失时本页文字与 [`catalog.md`](catalog.md) 仍完整可读。

## 场景目录

完整表见 [`catalog.md`](catalog.md)，机器可读见 [`catalog.json`](catalog.json)。

### 现在可演示（software / agent）

- **发票/结构化抽取** — 陌生 Client ↔ Provider，JSON 验收双签  
- **通用可验收任务** — field match / LLM judge  
- **推理用量** — `compute.inference.tokens`  
- **拒绝退款 / 超时清扫** — 异常路径同样是协议的一部分  
- **多节点与见证** — 换节点仍可验；可选 witness/stake  

### 灯塔 · 智能 IoT（同一语法 · 可无人值守）

- **机器人** — 任务完成、机队分账；设备侧可自动签收  
- **能源 / 车充** — 表计 kWh；车↔桩自动交割  
- **自动驾驶车** — 场站、V2X 交付层（不管控制栈）  
- **无人机** — 航线、空域/起降、巡检交付  
- **传感 / 边缘** — 可证数据与边缘算力  
- **跨域编排** — 车·机·无人机协作；**交换过程可无人参与**，人保留规则与重大终审  

总图：[`figures/05-iot-ecosystem.svg`](figures/05-iot-ecosystem.svg)。

## 试用

- 官网 Trial：<https://novapanda.io/trial.html>  
- 零号节点：<https://node.novapanda.io/>（Scenes 页将挂载本目录）  
- 本地：`python demo/trial_remote.py` · `python demo/plugfest.py`

## 许可

场景文案与图示随本仓库 `docs/` 发布，遵守项目规范许可（CC BY 4.0 叙事层）；实现代码 Apache-2.0。
