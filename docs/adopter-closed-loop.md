# 接入方业务闭环 · 填中空设计

> **状态**：说明层（informative）· 2026-07-19  
> **读者**：产品 / Steward / 第三方实现者——感觉「规范很全、场景很远、中间不知道造什么」时读本页  
> **非 MUST**：实现纪律仍以 [`CHARTER.md`](../CHARTER.md) · [`spec/CORE.md`](../spec/CORE.md) · Profiles 为准  
> **对照误区**：[外部草图对照](record-vs-vdc.md) · **最短互通**：[IMPLEMENTER_GUIDE.md](IMPLEMENTER_GUIDE.md)

---

## 0. 中空是什么

```text
┌─ 灯塔场景（catalog：车充 / 巡检 / 百跳…）──── 远 ─┐
│                                                   │
│           ░░░░░ 中空 ░░░░░                        │
│     「接入方运行时」缺一张施工图                   │
│                                                   │
└─ CORE / VDC / Exchange / 向量（已扎实）──── 近 ─┘
```

| 层 | 现状 | 中空感从哪来 |
|----|------|-------------|
| CORE + 向量 | 已有 | 像「语法书」，不是业务日课 |
| 场景 catalog | 叙事齐、部分 reserved/vision | 像海报，缺「明天车端写什么」 |
| 接入方运行时 | **薄** | 草稿、出站队列、互存、Skill 映射未成文 |
| 结算 / 钱包 | 旁路骨架 | 容易误当成下一件必做的「金融」 |

**填中空的原则**：先造 **Adopter Runtime**（客户端身体），用 **一条可演示竖切** 跑通闭环；不扩 CORE，不做积分/协议币。

---

## 1. 目标闭环（一句话）

> 第三方智能体或智能车：发现对端 → 本地持钥完成一笔交换 → 双方各持可 `reverify` 的 VDC → （可选）mock/旁路结算 → 能查、能导、能争议。

成功判据与 Litmus 同构：**SETTLED + 双签 VDC**，不依赖「必须用我们的节点」或「链上转账已到」。

---

## 2. 该造的中间层：Adopter Runtime

协议不规定这些模块，但**没有它们，接入方会觉得协议「空」**。

```text
┌──────────────────────────────────────────────────────────┐
│  Adopter Runtime（接入方造 · 填中空）                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │ DraftStore │ │ Outbox     │ │ VdcVault           │   │
│  │ 任务中草稿 │ │ 弱网重放   │ │ 本地 VDC+附件哈希  │   │
│  └────────────┘ └────────────┘ └────────────────────┘   │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │ IntentMap  │ │ PeerBackup │ │ Query/Export UI    │   │
│  │ 一键/自然语言 → Exchange ops │ │ 互推备份 │ │ list/统计/PDF壳 │   │
│  └────────────┘ └────────────┘ └────────────────────┘   │
├──────────────────────────────────────────────────────────┤
│  Binding：HTTP · Skill · MCP · A2A（只翻译）               │
├──────────────────────────────────────────────────────────┤
│  CORE：Identity · Exchange SM · VDC · reverify             │
├──────────────────────────────────────────────────────────┤
│  旁路：NP-SETTLE mock→真轨 · Wallet · 可选哈希锚定         │
└──────────────────────────────────────────────────────────┘
```

| 模块 | 职责 | 映射接入方建议 | 禁止 |
|------|------|----------------|------|
| **DraftStore** | 任务未完成前只存本地意图 / 半成品交付 | 「草稿模式」 | 半成品当已签 VDC |
| **Outbox** | 断网缓存 propose/deliver/confirm，恢复按幂等重放 | 「离线支持」 | 离线「先 SETTLED」 |
| **VdcVault** | 终态 VDC + `result_hash` 指向的交付物摘要本地落盘 | 「本地优先」「富附件哈希」 | 只信节点 DB |
| **IntentMap** | 「确认」「有异议」→ `confirm` / `dispute` | 「轻量确认 / 拒绝」 | 运营账号代签 |
| **PeerBackup** | SETTLED 后向对端推送同一 VDC 字节 | 「双方互存」 | 改签后内容 |
| **Query/Export** | peer/时间/状态过滤；JSON export；PDF 仅展示壳 | 「多维查询 / 统计 / 导出」 | PDF 当验签真源 |
| **Discovery** | 读 `/.well-known/novapanda.json`；聊天可用 `[NP:v1]` 提示 | 「协议标记 / 能力声明」 | 前缀替代 Manifest |

六接口口语对照（实现仍走 Exchange）：见 [`record-vs-vdc.md`](record-vs-vdc.md) §4。

---

## 3. 竖切 A · 第三方软件 Agent（现在就能闭）

**场景**：陌生 Client 要约「结构化抽取」→ Provider 交付 JSON → 双签 SETTLED（对齐 `S-invoice-extract` / Trial）。

### 3.1 角色分工

| 角色 | 持什么 | 跑什么 |
|------|--------|--------|
| Provider Agent | 本地 Ed25519；DraftStore；技能执行器 | 接任务 → 产 deliverable → `deliver` 签名 |
| Client Agent | 本地 Ed25519；验收规则；IntentMap | `propose`…`verify`→`confirm` 或 `dispute` |
| 节点（可替换） | 编排与持久化；**不持 Agent 私钥** | HTTP Exchange；Manifest |
| 任意第三方 | 导出的 JSON 包 | `reverify(VDC, deliverable)` |

### 3.2 时序（业务日课）

```text
Client                         Node                      Provider
  │  discover well-known         │                          │
  │─────────────────────────────>│                          │
  │  propose (idempotency_key)   │                          │
  │─────────────────────────────>│────── notify / pull ────>│
  │  contract_ack ×2             │<─────────────────────────│
  │  escrow (mock OK)            │                          │
  │─────────────────────────────>│                          │
  │                              │   执行任务（DraftStore）   │
  │                              │   deliver + provider_sig  │
  │                              │<─────────────────────────│
  │  verify(rule)                │                          │
  │  confirm → client_sig        │                          │
  │─────────────────────────────>│                          │
  │  SETTLED · 双方 VdcVault 互存 · 可选 export              │
```

### 3.3 接入方「一键」怎么接真 API

| 用户/Agent 动作 | Runtime | 协议调用 |
|----------------|---------|----------|
| 任务完成点「记账」 | Draft→正式交付物 | `POST …/deliver` |
| 对方回「确认」 | IntentMap | `POST …/confirm` |
| 对方回「不对」 | IntentMap | `POST …/dispute`（附 reason） |
| 「导出给仲裁」 | Export UI | `GET …/export` + 本地 `reverify` |
| 断网点确认 | Outbox 入队 | 恢复后带原 `idempotency_key` / nonce 重放 |

**本竖切 Done 定义**：Client/Provider 各一个小 Runtime（甚至脚本）+ mock 结算 + 互存两份 VDC + 离线 reverify 全绿。

---

## 4. 竖切 B · 智能车 ↔ 充电桩（灯塔闭环设计）

**场景**：`S-av-charge` / `S-energy-dc` · Profile **NP-MIN + NP-PHYS**（+ 弱网时 **NP-LITE** 姿态）。  
**非目标**：ISO 15118 控制回路、车规功能安全、持牌收单——那些是 Adapter / 伙伴，不进 CORE。

### 4.1 主体与身份

| 主体 | `agent_id` | Manifest 要点 |
|------|------------|----------------|
| 车端 Agent（车机 / HSM 旁路持钥） | `ed25519:…` | `profiles: [NP-MIN, NP-PHYS, NP-LITE?]`；`resource_types` 含消费电能 |
| 桩端 Agent | `ed25519:…` | 同上；挂牌 `energy.electric.dc`；可选 marketplace listing |
| 车 VIN / 桩设备号 | **不进** CORE id | 可放 deliverable 或身体元数据；真源仍是密钥身份 |

车不是 `device://car_01`；设备标识是业务字段，签名身份是 Agent。

### 4.2 控制回路 vs 交割回路（必须拆开）

```text
【充电控制 · 非 NovaPanda】     【交割 · NovaPanda】
  ISO15118 / 枪连接 / PWM    →    结束后表计证据进 deliverable
  车桩会话、安全认证         →    session_id · kwh · meter_signature
  实时功率环                 →    不进 Exchange 状态机
```

桩端 Adapter：`iso15118` 会话结束 → 组装物理 deliverable → 才进入 `deliver`。  
参考校验字段：`session_id` · `kwh_delivered` · `meter_signature`（见 `novapanda/v3/physical.py` · C9）。

### 4.3 闭环时序（车为 Client，桩为 Provider）

> 电是桩「交付」的，故 **provider = 桩**，**client = 车**（要约并验收 kWh）。

```text
0. 发现
   车：场站目录 / 本地缓存 / GET 桩 /.well-known/novapanda.json
   可选：marketplace discover（NP-REP）选桩

1. 要约（车可先写 DraftStore：目标 kWh、时限、价格条款）
   车 → propose(resource_type=energy.electric.dc, rule_id=R-energy-meter-v1, …)
   双方 contract_ack（条款含单价/上限）
   车 → escrow（Trial：mock；生产：NP-SETTLE 伙伴）

2. 物理充电（Outbox/本地会话；弱网不阻塞充电控制）
   枪连接与充电会话在车桩私有栈完成
   桩 Meter 产出：{ session_id, kwh_delivered, meter_signature, window_* }

3. 交割上链到协议（不是「上公链」，是上 Exchange）
   桩 → deliver(deliverable) + provider_sig
   车（或车委托的边缘 Agent）→ verify（NP-PHYS 校验 + rule）
   车 → confirm + client_sig → SETTLED
   失败：verify 不过 → reject；争议 → dispute + reason_hash

4. 互存与离线
   车 VdcVault ← VDC；桩 VdcVault ← 同一字节
   弱网：Outbox 延迟 confirm；恢复后重放；此前不得伪称 SETTLED
   可选身体：VDC/`result_hash` 廉价锚定（旁路，非终局）

5. 事后
   车队后台 Query：按桩 peer、时间、状态
   仲裁：export JSON → 第三方 reverify（不依赖原场站节点）
```

### 4.4 车端 Runtime 最小组件清单

| 组件 | 车端行为 |
|------|----------|
| Keystore | HSM/TEE 或安全元件；**私钥不上云** |
| DraftStore | 导航到站前缓存「拟充 30kWh」意图 |
| ChargeAdapter | 只读会话结束事件 → 触发协议侧 verify/confirm |
| Outbox | 地库无网时暂存 confirm/dispute |
| VdcVault | 行程级收据文件夹；与账单系统对账用哈希 |
| IntentMap | 座舱「确认结算」/「电量不对」→ confirm/dispute |

### 4.5 桩端 Runtime 最小组件清单

| 组件 | 桩端行为 |
|------|----------|
| MeterAdapter | 表计签名进 deliverable；对齐 C9 |
| Listing | Manifest / marketplace 暴露 `energy.electric.dc` |
| DeliverPipeline | 会话结束自动 `deliver`（**不是** auto 造假 VDC；有真实 meter 才交付） |
| Settlement rail | mock → 持牌分账伙伴；与 VDC 解耦 |
| PeerBackup | 向车推送终态包（蓝牙/本地 Wi‑Fi/经节点均可） |

### 4.6 一笔业务多张收据（避免「超级凭证」）

若车主业务是「到场巡检 + 顺便充电」（`S-nested-site-patrol`）：

```text
VDC₁ 车到场/泊位（mobility 或 task）
VDC₂ 无人机巡检
VDC₃ 机器人接点
VDC₄ 充电 energy.electric.dc   ← 本竖切只强制先闭这一张
```

Bundle 在**客户端编排**（ADR-0003）；每张仍是原子 VDC。中空阶段 **先闭 VDC₄ 单腿**，再叠组合。

---

## 5. 填中空的施工顺序（替代「积分→金融」路线）

接入方建议里的阶段 3–4（积分、金融）**不作为本设计路线**。改用下面四档：

| 档 | 目标 | 交付物 | 场景锚点 |
|----|------|--------|----------|
| **M0 · 语法闭环** | 一笔 SETTLED + reverify | `demo/run_demo.py` · SDK | `S-invoice-extract` |
| **M1 · Runtime 闭环** | Draft + Outbox + VdcVault + IntentMap + Peer + Query | **`novapanda/adopter/`** · `demo/adopter_closed_loop.py` ✅ | 同左 |
| **M2 · 物理单腿** | 车/桩 + ISO15118 sim → energy VDC | **`adopter/charge.py`** · `demo/adopter_av_charge.py` ✅ | `S-energy-dc` / `S-av-charge` |
| **M3 · 产品面** | 场站发现 + 本地锚定 + PDF/JSON 导出 | **`stations`/`anchor`/`export_pdf`** · `demo/adopter_m3_product.py` ✅ | 身体旁路；非 CORE |
| **M4 · 增强轨** | 可插拔表计 + 公告板/链 stub 多轨锚定 + 座舱指令 | **`meter`/`anchor_rails`/`cabin`** · `demo/adopter_m4_rails.py` ✅ | 真桩/真链替换后端 |
| **M5 · Bundle 巡检** | 车到场→无人机→机器人→充电 · 多 VDC | **`patrol.py`** · `demo/adopter_site_patrol.py` ✅ | `S-nested-site-patrol` |
| **M6 · 收口** | Skill 映射 + CI/看门狗冒烟 | **`skill.py`** · `demo/adopter_smoke_all.py` ✅ | 推荐接入路径钉死 |
| **M7 · 生态证明** | `np manifest validate` + NP-LITE Outbox 对齐 | **`manifest_validate.py`** · CLI ✅ | — |
| **M8 · 第二实现征集包** | 起步包 + checklist + Exchange/Manifest schema draft | **`SECOND_IMPL_STARTER.md`** ✅ | 等外部填 compatibility 行 |
| **M8b · 对外邀请入口** | 可转发短文 + README 挂钉 | **`CALL_FOR_SECOND_IMPL.md`** ✅ | 传播 / 找第二节点 |
| **M8c · TS L0 自证** | 离线 reverify + plugfest 生命周期 | **`sdk/typescript` `attest:l0`** ✅ | 第二节点仍外征 |
| **M8d · CI 挂钉** | CI `attest:l0` + `ts-plugfest` · EN 征集入口 | **`.github/workflows/ci.yml`** ✅ | 传播 / 找第二节点 |
| **M8e · LITE 嵌入边界** | MCU vs 伴侣机 vs 节点；实物分镜 | **`docs/lite-embedded-boundary.md`** ✅ | 真机视频 / ROS2 后置 |
| **M8f · OpenClaw 对接清单** | 车 Client + OpenClaw Provider 本周真跑 | **`docs/openclaw-adopter-checklist.md`** ✅ | 录屏 / 租狗后换 deliverable |
| **M8g · 结对 CLI + Skill 壳** | `pair_cli` 一键 SETTLED · OpenClaw `SKILL.md` | **`demo/openclaw_pair/`** ✅ | 分机拆步（可选） |
| **M8h · 标准 BINDING** | `BINDING-OPENCLAW` 入 spec 索引 | **`spec/BINDING-OPENCLAW.md`** ✅ | — |
| **M8i · 生态适配器挂钉** | registry + openclaw/mqtt/ros2 种子 · 社区模板 | **`adapters/`** · **`novapanda/ecosystem`** ✅ | 社区 PR 填厂商 |

**刻意后置**：真法币/持牌清算、协议内积分、跨链「金融功能」、W3C VC 换皮。

---

## 6. 你（第三方 Agent / 车）的每日检查清单

1. 我是否本地持钥？节点是否只编排？  
2. 本笔是否走到 **SETTLED + 双签**？（不是 pending/confirmed 两态）  
3. 交付物是否在 `result_hash` 内？物理场是否过 NP-PHYS？  
4. 断网时我是否只用 Outbox，而非跳过验签？  
5. 对方丢库后，我能否掏出 VdcVault 让第三方 `reverify`？  
6. 钱：Manifest 是否诚实写 mock/sandbox？有没有把 `tx_hash` 当交割终局？

全绿 = 业务闭环成立；否则仍在中空或旁路幻觉里。

---

## 7. 与仓库落点对照

| 设计块 | 已有 | 待接入方 / 身体补 |
|--------|------|-------------------|
| Exchange + VDC | `novapanda` CORE · NP-HTTP | — |
| Manifest / well-known | `GET /.well-known/novapanda.json` | 车/桩固件侧暴露 |
| 物理校验 | `v3/physical.py` · C9 · NP-PHYS | 真表计 Adapter |
| 弱网姿态 | NP-LITE 成文 · [嵌入边界](lite-embedded-boundary.md) | 真机固件 / 实物视频 |
| 市场发现 | NP-REP · marketplace-flow | 场站目录产品 |
| 导出 | `/exchanges/{id}/export` · `adopter/export_pkg.py` | PDF 展示壳（可选） |
| **Adopter Runtime（M1）** | **`novapanda/adopter/`** · `demo/adopter_closed_loop.py` · `tests/test_adopter_runtime.py` | — |
| **车充竖切（M2）** | **`adopter/charge.py`** · `demo/adopter_av_charge.py` · `tests/test_adopter_av_charge.py` | 真表计 Adapter |
| **产品面（M3）** | **`stations.py` · `anchor.py` · `export_pdf.py`** · `demo/adopter_m3_product.py` | 精美 PDF |
| **增强轨（M4）** | **`meter.py` · `anchor_rails.py` · `cabin.py`** · `demo/adopter_m4_rails.py` | 真表计 / 真链 broadcast |
| **Bundle 巡检（M5）** | **`patrol.py`** · `demo/adopter_site_patrol.py` · `tests/test_adopter_site_patrol.py` | 真实机队/场站 Adapter |
| **Skill / CI（M6）** | **`skill.py`** · `tests/test_adopter_skill.py` · gatekeeper + CI smoke | 宿主 IDE 接线 |
| **Manifest CLI（M7）** | **`manifest_validate.py`** · `np manifest validate` · LITE Outbox 对齐 | 外部第二实现 |
| 结算 | NP-SETTLE mock | 持牌伙伴合同 |

### 7.1 Adopter 模块地图（已实现）

| 积木 | 路径 |
|------|------|
| 设计说明 | [`novapanda/adopter/DESIGN.md`](../novapanda/adopter/DESIGN.md) |
| 门面 | `novapanda/adopter/runtime.py` → `AdopterRuntime` |
| DraftStore | `draft.py` |
| Outbox | `outbox.py` |
| VdcVault | `vault.py` |
| IntentMap | `intent.py` |
| PeerBackup | `peer.py` |
| Query/stats | `query.py` |
| 仲裁 JSON + 文本壳 | `export_pkg.py` |
| 车充控制+闭环 | `charge.py` → `ChargeControlAdapter` · `AvChargeLoop` |
| 场站发现 | `stations.py` |
| 本地锚定 | `anchor.py`（旁路；≠ SETTLED） |
| PDF 展示壳 | `export_pdf.py`（人读；验签仍靠 JSON） |
| 可插拔表计 | `meter.py` → `MeterAdapter` / `Iso15118MeterBackend` |
| 多轨锚定 | `anchor_rails.py` → bulletin + `ChainAnchorStub` |
| 座舱 UX | `cabin.py` → `CabinConsole` |
| 巡检 Bundle | `patrol.py` → `SitePatrolBundle`（四腿 + human_gate） |
| Skill 面 | `skill.py` → `AdopterSkill`（`adopter_*` 工具） |

```bash
pytest tests/test_adopter_runtime.py tests/test_adopter_av_charge.py tests/test_adopter_m3_product.py tests/test_adopter_m4_rails.py tests/test_adopter_site_patrol.py tests/test_adopter_skill.py -q
python demo/adopter_smoke_all.py
python run_local_gatekeeper.py
```

---

## 8. 一句话收束

中空不是「协议还缺一个 Record 层」，而是 **缺 Adopter Runtime + 一条竖切（先软件、再车充单腿）**。  
造中间层时，一律把口语「记账 / 确认 / 导出」**翻译**成 Exchange + VDC；灯塔场景用同一语法叠腿，不另起状态机。
