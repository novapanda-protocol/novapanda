# 生态八域 · 交付物如何挂接 NovaPanda

> **状态**：公开说明 · 2026-07-09 · **非规范性**（叙事与登记；MUST 以 [`CHARTER.md`](../../CHARTER.md) · [`spec/`](../../spec/) · [`profiles/`](../../profiles/) 为准）  
> **读者**：产品、生态伙伴、实现者——想知道「API / MCP / Skill / 工作流 / OTA / P2P… 能不能接」  
> **一句话**：NovaPanda 不是万物操作系统，而是 **万物可互认交付的语法层**；八域里的具体形态走 **Profile · 绑定 · 注册表** 扩展，不复制八套状态机。

---

## 1. 先读这三句

1. **我们统一的是「交付是否发生、能否独立复验」**（VDC），不是工作流引擎、OTA 平台或飞控 OS。  
2. **广括生态靠分层扩展**：内核很小很稳；能力用可选 Profile 与接入绑定叠上去。  
3. **兼容靠向量自测**，不靠「必须过某一家节点」——零号只是可替代的试用实例。

---

## 2. 分层：交付物落在哪一层

```text
┌─ 说明层（本页、场景 catalog）────────────────────────────┐
│  八域登记 · IoT 海报 · 产业姿态（不上升为 MUST）          │
├─ 身体层（运营实例：零号节点等）──────────────────────────┤
│  配额 · 审计 · 沙箱结算 · Operator 登录 · 目录托管      │
├─ 绑定层 BINDING ─────────────────────────────────────────┤
│  HTTP API · MCP · A2A · Skill 表面 · Proxy 翻译          │
├─ 能力层 PROFILES ────────────────────────────────────────┤
│  MIN · NODE · BUNDLE · PHYS · SETTLE · DELEGATE · PRIV · LITE │
├─ 注册表 REGISTRIES ──────────────────────────────────────┤
│  资源本体 · 验收规则 · 批量扩展包（加性演进）             │
├─ 内核 CORE ──────────────────────────────────────────────┤
│  身份 · 规范化签名 · VDC · 交换状态机 · 独立复验         │
└──────────────────────────────────────────────────────────┘
```

**纪律**：新交付物类型默认先登记；只有确属交割 MUST 的，才进入 Profile 或 conformance 向量。

---

## 3. 八域一览

图例：**已挂接** = 规范或套件已有落点 · **进行中** = 设计/参考实现/部分测 · **邻接** = 可挂钩、今日不立法 · **不进内核** = Charter 明确 Out of Scope

### 3.1 远程服务

| 交付物 | 挂接方式 | 状态 | 说明 |
|--------|----------|:----:|------|
| **HTTP API** | 绑定 · [`spec/NP-HTTP.md`](../../spec/NP-HTTP.md) | 已挂接 | 一等互通面；OpenAPI 与 C1–C7 向量 |
| **MCP** | [`spec/BINDING-MCP.md`](../../spec/BINDING-MCP.md) | 已挂接 | 工具/资源列表 ≠ 交换状态机 |
| **Remote Pod** | Manifest `compute.*` | 邻接 | 远端算力单元；Pod 生命周期不进内核 |
| **ToolBundle** | → [`NP-BUNDLE`](../../profiles/NP-BUNDLE.md) | 进行中 | 多工具打包；见下节「与 Bundle 区别」 |
| **Proxy 网关** | 绑定/身体 | 邻接 | x402/AP2/法币等网关形状；**不得代签 Agent** |

### 3.2 本地执行

| 交付物 | 挂接方式 | 状态 | 说明 |
|--------|----------|:----:|------|
| **Skill** | 绑定 | 进行中 | 能力发现表面；交割仍走 VDC |
| **Script** | 客户端 | 邻接 | Composer 库优先编排 |
| **固件 App** | 设备 Manifest | 邻接 | 配合 [`NP-PHYS`](../../profiles/NP-PHYS.md) / [`NP-LITE`](../../profiles/NP-LITE.md) |
| **推理模型包** | 规则 + `compute.*` | 进行中 | LLM 可作验收辅助；**不得单独终局 SETTLED** |
| **诊断探针** | 运维绑定 | 邻接 | 审计/SBOM；远控不进内核 |

### 3.3 编排协同

| 交付物 | 挂接方式 | 状态 | 说明 |
|--------|----------|:----:|------|
| **工作流** | **客户端** Composer | 进行中 | 多步编排不进 CORE；见 [`bundle.md`](bundle.md) |
| **分布式任务分片** | Bundle + Claim | 邻接 | 多跳价值叙事；调度非协议 MUST |
| **事件处理器** | 绑定/Notify | 邻接 | 可对齐 CloudEvents 形状；事件总线不替代 VDC |

### 3.4 无代码规则

| 交付物 | 挂接方式 | 状态 | 说明 |
|--------|----------|:----:|------|
| **状态机** | **CORE**（仅交换态） | 已挂接 | `PROPOSED…SETTLED`；设备 idle/busy **≠** 交换态 |
| **触发器 / 定时** | CORE 超时 + 身体 sweep | 已挂接/进行中 | recover、RB-04 告警 |
| **提示词模板** | 规则注册表 | 进行中 | 模板可变；验收须可复算（C5） |
| **配额** | NODE 身体 | 已挂接 | 接入节流；**不是协议税** |
| **审计规则** | NODE Admin | 进行中 | 可追溯；**不改写已签 VDC** |

### 3.5 开发工具

| 交付物 | 挂接方式 | 状态 | 说明 |
|--------|----------|:----:|------|
| **多语言 SDK** | 实现者工具 | 进行中 | Python · TypeScript；见 [`compatibility.md`](../compatibility.md) |
| **CLI** | 客户端 | 进行中 | `reverify` 已有；统一 `np` CLI 路线图 |
| **Schema 规范** | SPEC | 已挂接 | VDC schema · [`spec/schemas/`](../../spec/schemas/) |

### 3.6 交付升级

| 交付物 | 挂接方式 | 状态 | 说明 |
|--------|----------|:----:|------|
| **OTA 升级包** | 证据 deliverable | 邻接 · **不进内核** | 可挂包哈希+签名；**不做全球 OTA 协议** |
| **批量扩展包** | 注册表加性发布 | 进行中 | 本体/规则批量；须遵守 VERSIONING |

### 3.7 安全权限

| 交付物 | 挂接方式 | 状态 | 说明 |
|--------|----------|:----:|------|
| **委托凭证** | [`NP-DELEGATE`](../../profiles/NP-DELEGATE.md) | 已挂接 | 临时代签/代付边界；**不是余额账户** |
| **访问控制策略包** | NODE 身体 | 进行中 | Operator 策略；**Operator 登录 ≠ Agent 签** |

### 3.8 网格协同

| 交付物 | 挂接方式 | 状态 | 说明 |
|--------|----------|:----:|------|
| **P2P 网格** | federation 叙事 | 邻接 | 不得成唯一真源；兼容仍靠向量 |
| **差分同步片段** | [`NP-LITE`](../../profiles/NP-LITE.md) | 进行中 | 弱网瘦报文；**不得撕 C1 规范化** |

---

## 4. ToolBundle 与 Exchange Bundle

很多人把「工具包」和「交割组合」混为一谈。公开区分如下：

| | **ToolBundle**（工具打包） | **Exchange Bundle**（组合交割） |
|--|---------------------------|----------------------------------|
| **解决什么** | 一次调用里挂多个 MCP/Skill/API | 一笔业务目标对应多笔交换、多张 VDC |
| **协议落点** | 绑定层 + 客户端编排 | [`NP-BUNDLE`](../../profiles/NP-BUNDLE.md) Profile |
| **成功判据** | 工具是否被正确调用 | 每笔成员是否 **SETTLED + 可复验** |
| **详文** | 本页 §3.1 | [`bundle.md`](bundle.md) |

编排（工作流、depends_on、人类终审）默认在 **Agent/Composer 侧**；节点可提供索引，但不垄断工作流。

---

## 5. 与场景图谱、IoT 叙事的关系

| 文档 | 关系 |
|------|------|
| [`overview.md`](overview.md) | 场景三问：是什么、能换什么、与支付何异 |
| [`figures/05-iot-ecosystem.svg`](figures/05-iot-ecosystem.svg) | 车·无人机·机器人·软件 Agent 对等主体 |
| [`catalog.md`](catalog.md) | 可演示 vs 灯塔场景目录 |
| [`bundle.md`](bundle.md) | 嵌套尽调 / 巡检等同构 |

八域回答的是：**生态里还有哪些「交付物类型」可以挂进来**；场景回答的是：**具体在换什么**。

---

## 6. 实现者从哪里开始

```bash
# 读范围
cat CHARTER.md

# 跑向量（示例）
python -m conformance.run --list
python -m conformance.run C1

# 自报兼容
# 见 docs/compatibility.md
```

| 文档 | 用途 |
|------|------|
| [`IMPLEMENTER_GUIDE.md`](../IMPLEMENTER_GUIDE.md) | 30 分钟最短路径 |
| [`profiles/README.md`](../../profiles/README.md) | 宣告哪些 Profile |
| [`conformance/VECTORS.md`](../../conformance/VECTORS.md) | Case 与 Profile 挂钩 |

---

## 7. 我们明确不做

- 全球 OTA 宿主协议、飞控/交规引擎、路径冲突仲裁 OS  
- 把工作流引擎塞进 CORE 状态机  
- 协议层 Tool 商店或「必须过零号扫描」  
- 协议币、协议税、二清资金池  
- 用运营账号邮箱登录 **代替** Agent 密码学签名  

详见 [`CHARTER.md`](../../CHARTER.md) Out of Scope。

---

## 8. 诚实边界（2026-07-09）

| 已较完整 | 仍在演进 |
|----------|----------|
| 交换态 + VDC + HTTP 绑定 | MCP/Skill 绑定专卷 |
| DELEGATE / PHYS / LITE / SETTLE 等 Profile 向量 | 统一 CLI · 策略包 JSON |
| 场景 + IoT 海报 + Bundle 叙事 | P2P 网格互操作向量 |
| 兼容登记空表（欢迎第二实现） | OTA/批量包注册格式 |

**这不影响 Litmus**：陌生 Agent 仅凭公开规范完成交割并被第三方复验——今日已可排练（mock 结算）。

---

## 9. 维护

新增生态交付物类型时：先在本页八域表加一行 → 评审是否升格 Profile/绑定 → 必要时补 conformance Case。  
规范性变更走 [`GOVERNANCE.md`](../../GOVERNANCE.md) / [`VERSIONING.md`](../../VERSIONING.md)。

---

*生态八域公开页 · docs/scenarios · CC BY 4.0 叙事层*
