# Exchange Bundle · 组合交割约定

> **状态**：叙事说明稿 · **规范性条文以** [`profiles/NP-BUNDLE.md`](../../profiles/NP-BUNDLE.md) **为准**（冲突时 Profile 优先）。  
> **配套**：[`catalog.md`](catalog.md) 嵌套场景 · 海报 [`figures/06-poster-nested.svg`](figures/06-poster-nested.svg)

---

## 为什么需要

单笔 exchange 的状态机已经够用。物联网与多智能体业务往往是：

> **一个业务目标 = 多笔对等交割（各一张 VDC）+ 依赖关系 + 可选人类终审。**

若把多笔硬塞进一个巨型状态机，会破坏「可复验原子收据」与联邦可携带性。  
因此增加 **Bundle（组合约定）**：编排语义在应用/Agent 侧；节点可选择索引，但不垄断工作流。

**与 ToolBundle 的区别**（工具打包 vs 多张 VDC 组合）：见 [`ecosystem-eight-domains.md`](ecosystem-eight-domains.md) §4。

---

## 旗舰同构

| | 嵌套 B · 现在（软件） | 嵌套 A · 灯塔（物理） |
|--|----------------------|----------------------|
| Goal | 供应商尽调包 | 到场巡检闭环 |
| 成员 | 抽取 → 勾选任务 → LLM 摘要 | 车到场 → 无人机巡检 → 机器人接点 → 可选充电 |
| catalog | `S-nested-soft-diligence` | `S-nested-site-patrol` |
| 今天 | Trial / plugfest 腿可排练 | 叙事 + energy/robot 冒烟腿 |

---

## 最小字段

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

### 语义

| 字段 | 含义 |
|------|------|
| `correlation_id` | 跨 exchange 的关联键；可写入各单笔扩展元数据 |
| `depends_on` | 启动约束由**编排方**执行；节点可不解释 |
| `success_rule` | `all_settled` / `quorum:n` 等 |
| `human_gate` | 对「目标完成声明」的附加签/拒；**不**回滚已签 VDC |
| `vdc_ids` | 完成后回填；目标证明 = VDC 集合 (+ gate) |

**Bundle 不是 VDC。** 第三方复验仍针对每张 VDC；Bundle 只回答「它们是否属于同一目标」。

---

## 价值如何传到下一笔（prior VDC）

交换的「价值」默认传递的是 **可验证的完成事实 / 资格**，不是协议内代币。

下一笔 propose / terms 可携带：

```json
"prior_vdc_refs": [
  {
    "vdc_id": "vdc_…",
    "claim": "inspection_passed",
    "required": true
  }
]
```

对端在 contract 前 MUST（Profile 级）能对该 VDC **独立 reverify**；失败则拒收。  
这是嵌套里最常见的传递：**出示引用（不转移所有权）**。

其他传递形态（委托出示、Bundle 累积、证据链哈希引用）见内部设计《陌生设备-握手交换与价值传递》；升 Profile 时再逐项规范化。

**不采用**：把 VDC 当可转账积分花掉；用节点私有余额冒充传递。

### 像货币一样的多跳（对齐说明）

目标体感：A→B→C→… 价值可持续接力（智能体与 IoT）。  
分层理解：

- **VDC**：事实锚（发票），防止无交付而空转；  
- **Settlement Claim / 余额（旁路）**：更接近「可再花」的权柄；SETTLED 后释放到持有方；  
- **下一跳**：新的握手 + 新 VDC；可附 prior VDC 或使用旁路资产支付/锁仓。

完整模型见内部《价值多跳流转-如货币》。可选转让 Claim 属未来 Profile，**不**等于协议发币。

---

## 与节点的关系

| | 必须 | 可选 |
|--|:----:|:----:|
| Agent 本地持有 Bundle | ✓ | |
| 单笔 exchange API | ✓ 不变 | |
| 节点存储 Bundle 索引 | | ✓ `POST /bundles`（未来） |
| 节点执行 depends_on | | 默认 **否**（防节点变成工作流垄断） |

---

## 失败原则

- 子交换 REJECTED / EXPIRED → 按商务条款决定其他子交换；已 SETTLED 的 VDC **事实仍在**。  
- 人类否决 goal → 记录 gate=rejected；不要求伪造「未交付」。  
- 换节点：带着 VDC 集合 + Bundle 描述即可继续。

---

## 非目标

- 不规定 ROS/飞控/智驾会话  
- 不引入协议币分账  
- 不强制所有子交换同一节点  

---

*说明稿 0.1 · 2026-07-08 · 升格见 profiles/NP-BUNDLE.md*
