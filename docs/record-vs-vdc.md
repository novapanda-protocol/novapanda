# 外部草图 → NovaPanda 规范对照

> **用途**：对外解释常见平行设计（记账 Record、W3C-VC 外壳、另起多链钱包基类）时，如何映射到现有规范，避免分叉。  
> **状态**：说明层（informative）· 非 MUST  
> **金标准**：[`spec/CORE.md`](../spec/CORE.md) · [`spec/schemas/vdc.schema.json`](../spec/schemas/vdc.schema.json) · [`spec/NP-HTTP.md`](../spec/NP-HTTP.md) · [`decisions/0001-vdc-first-not-account-balance.md`](../decisions/0001-vdc-first-not-account-balance.md) · [`decisions/0002-settlement-as-adaptor-not-core.md`](../decisions/0002-settlement-as-adaptor-not-core.md) · [`novapanda/wallet/DESIGN.md`](../novapanda/wallet/DESIGN.md)

**一句话**：愿景上「可验证交割 + 双签 + 第三方复验」正确；落地映射到 **VDC + Exchange**；钱包 / 结算只做身体旁路，不重写 CORE。

---

## 0. 概念层

| 外部草图说法 | 规范说法 | 怎么对外讲 |
|-------------|---------|-----------|
| Agent-to-Agent **记账**基础设施 | **可验证交割**协议（VDC 第一公民） | 记的是「交付事实」，不是账户余额 |
| `Record`（交换记录） | **VDC**（Verifiable Delivery Claim） | 凭证可离线复验，不绑节点账本 |
| provider / consumer | `parties.provider` / `parties.client` | client 发起并验收；provider 交付并先签 |
| 仲裁用 JSON 包 | Exchange **export** + 离线 **reverify** | 第三方只凭公开规范验，不靠原节点 DB |
| 结算隐含在 confirm 里 | 结算是 **NP-SETTLE 适配器**，非 CORE 真源 | 协议不托管资金、不发币 |
| Verifiable **Data** Credential | Verifiable **Delivery** Claim | 交割凭证，不是通用数据凭证别名 |
| W3C VC（issuer / holder / proof） | 双签 canonical JSON VDC | VC 外壳最多做身体投影，不进 CORE 真源 |
| 另起 `MultiChainWalletManager` | 现有 `AgentWalletManager` + `ChainAdapter` | 补真链 / 广播，不新开基类 |

---

## 1. 字段对照（Record 草图 → Schema）

| 草图字段 | 对应 / 替代 | 说明 |
|---------|------------|------|
| `record_id` | `vdc_id` | 凭证 ID，不是流水号 |
| `version: "v1"` | `vdc_version` | 跟 schema `$id` / 版本策略走 |
| `timestamp`（Unix） | `created_at` + `evidence.started_at/finished_at` | 规范用 ISO8601 |
| `provider` / `consumer` | `parties.provider` / `parties.client` | 身份见 §2 |
| `service_catalog` | `resource_type`（+ listing/manifest） | 交割类型进 VDC；目录在市场层 |
| `details`（任意 KV） | **不进 VDC 正文**；交付物走 blob，`result_hash` 锚定 | 防随意字段破坏可验性 |
| `payload_hash` | canonical 后哈希 + 签名范围（CORE §2.1） | 不是单独业务字段名 |
| `deliverable_hash`（可选） | **`result_hash`**（必填形） | `sha256:<hex>` |
| `status` | Exchange 状态机 + VDC.`state` | 见 §3；勿用 pending/confirmed 顶替 |
| `signature_provider` / `signature_consumer` | `signatures.provider_sig` / `signatures.client_sig` | Ed25519 + base64url；`state` **不进签** |

**草图常缺、CORE 必有：**

| 必有字段 | 作用 |
|---------|------|
| `rule_id` | 验收规则，与价格解耦 |
| `quantity` | 数量 |
| `idempotency_key` / `nonce` | 防重放、可幂等 |
| `prev_hash` | 链式锚定 |
| `evidence.level` | `self_reported` / `dual_signed` / `metered` / `third_party_witnessed` |

---

## 2. 身份对照

| 草图 | 规范 | 结论 |
|------|------|------|
| `device://car_01` 一类 URI | `ed25519:` + base58(公钥) | **设备 URI 不能当 CORE `agent_id`** |
| （未规定算法） | Ed25519；私钥仅本地 | 运营登录 ≠ Agent 签名 |
| （未规定验签材料） | 仅凭对端 `agent_id` 即可验 | 无预建关系（Litmus） |

车 / 机 / 体身份可挂在身体层或 DID / manifest；交换双方仍是 Ed25519 agent。  
可选 DID 文档见 [`did-document.schema.json`](../spec/schemas/did-document.schema.json)（`did:novapanda:ed25519:…` 占位），**不能**替代 CORE `agent_id`。

---

## 3. 状态机对照

**常见草图：**

```text
pending → confirmed
       ↘ disputed
```

**Exchange（规范）：**

```text
PROPOSED → CONTRACTED → ESCROWED → DELIVERED → VERIFIED → SETTLED
   │            │           │           │
   └────────────┴───────────┴──→ CANCELLED / EXPIRED_REFUNDED
                                  DELIVERED → REJECTED
                                  VERIFIED  → DISPUTED → SETTLED / REJECTED
```

| 草图状态 | 粗映射（勿 1:1 等同） | 丢失的语义 |
|---------|----------------------|-----------|
| `pending` | PROPOSED…DELIVERED 之间多态 | 条款双签、托管、交付、验收被压扁 |
| `confirmed` | 接近 SETTLED（双签完成） | 中间还有 VERIFIED ≠ 已结算 |
| `disputed` | DISPUTED | 出口仍可 SETTLED / REJECTED |

**VDC.`state` 枚举**（凭证上）：`DELIVERED` · `VERIFIED` · `SETTLED` · `DISPUTED` —— 与 Exchange 全图配合，不是三态 Record。

W3C-VC 草图常见枚举 `created / verified / settled / archived / disputed` 同样**不够**：缺 PROPOSED→CONTRACTED→ESCROWED→DELIVERED 路径；`archived` 非现规范。

---

## 4. API 对照（Record 六接口 → Exchange）

| 草图接口 | 对应能力 | 实际入口（参考） |
|---------|---------|-----------------|
| `novapanda_create()` | 发起交换 | `POST /exchanges` → **propose**（非直接造 VDC） |
| （无） | 条款确认 | `POST …/contract` |
| （无） | 冻结 / 意图 | `POST …/escrow` |
| （无） | 交付并出 VDC | `POST …/deliver`（provider 签） |
| （混在 create/confirm） | 确定性验收 | `POST …/verify` |
| `novapanda_confirm()` | client 补签并走结算 | `POST …/confirm` |
| （无） | 争议 | `POST …/dispute` |
| `novapanda_get()` | 查单条 | `GET /exchanges/{id}`；VDC：`/vdc/{id}` |
| `novapanda_list()` | 列表 / 过滤 | 节点侧 `/node/exchanges` 等（身体能力，非 CORE MUST） |
| `novapanda_export()` | 导出可仲裁包 | `/exchanges/{id}/export`（参考节点） |
| `novapanda_verify()` | 第三方复验 | CLI / 库 **`reverify(VDC, deliverable)`**，不依赖原节点 |

Skill / MCP / A2A 绑定的是同一套 Exchange 操作（`propose`…`confirm`），不是平行的 `novapanda_*` 面。见 [`spec/BINDING-SKILL.md`](../spec/BINDING-SKILL.md) 等。

---

## 5. W3C-VC 外壳草图对照

常见建议：用 W3C Verifiable Credentials 形状「升级」VDC（`@context` / `type` / `issuer` / `holder` / `credentialSubject` / `proof`，算法如 `Ed25519Signature2020`），并加 `vdc_auto_detect` / `vdc_verify_proof` / `vdc_dispute_raise`。

| 草图 | 规范 | 判断 |
|------|------|------|
| VDC = Verifiable **Data** Credential | Verifiable **Delivery** Claim | 缩写撞车，语义不同 |
| `issuer` 单方 `proof` | `provider_sig` + `client_sig` 双签 | 单方签发不够 Litmus |
| `Ed25519Signature2020`（LD Proofs） | canonical JSON + Ed25519 base64url | 互操作面不同，换皮会分叉向量 |
| `credentialSubject` + 任意元数据 | 结构化 VDC 字段 + `result_hash` 锚定交付物 | 随意 KV 破坏可验性 |
| `holder` DID | `parties.client`（`ed25519:…`）；DID 可选邻接 | DID 不进 CORE MUST |
| `vdc_auto_detect()` | 显式 **`deliver`** | 禁止「模拟检测自动建证」 |
| `vdc_verify_proof()` | **`reverify(VDC, deliverable)`** | 不新造入口名 |
| `vdc_dispute_raise()` + reason hash | Exchange **`dispute`**（可附争议上下文） | 挂现有状态机，不另起控制器 |

**可吸收（不改 CORE）**：争议附带 reason / reason hash；对外说明「DID 文档可选」「结算与凭证分离」。  
**应拒绝**：用 W3C VC 替换 `vdc.schema.json`；把 Data Credential 叙事写进规范真源。

---

## 6. 多链钱包草图对照

常见建议：新建 `MultiChainWalletManager`（EVM + Solana，`get_balance` / `transfer` / `estimate_gas_fee`，金额 `float`，构造注入 KMS key），并把链上转账当作 Agent「自主结算」。

| 草图 | 已有 / 规范 | 判断 |
|------|------------|------|
| 新基类 `MultiChainWalletManager` | [`AgentWalletManager`](../novapanda/wallet/DESIGN.md) + `ChainAdapter` | **不必另起**；补缺口即可 |
| EVM + Solana 统一视图 | 已有 EVM / Solana 适配、Paymaster、法币合规入口 | 方向对 |
| `amount: float` | 最小单位 **`int`**（`Balance` / `TransferRequest`）；协议禁 float（`NP-CAN-02`） | 接口细节错 |
| `transfer` = 交割终局 / 自主结算 | 链上转账 ≠ SETTLED；结算走 **NP-SETTLE**（ADR-0002） | 层次混 |
| 构造函数持 `encrypted_kms_key` | VDC 签钥 **仅本地**；资金钥若在身体层用 KMS 须单独划界 | 勿与「节点代签」混淆 |
| 从零实现钱包层 | DESIGN 已标：RPC 适配 ✅；`signer_broadcast` 真链提交 ⏳ | 优先补身体缺口 |

**可吸收**：继续做多链统一账户视图；真链广播与持牌法币轨在身体层迭代。  
**应拒绝**：用 float 钱包 API 替换现类型；把 `tx_hash` 当作 VDC / SETTLED 真源。

---

## 7. 密码学 / 验收对照

| 草图 | 规范 |
|------|------|
| SHA256 哈希 | MUST：`sha256:` + 64 hex；canonical JSON（键序、NFC、无 float） |
| 非对称签名 / LD Proofs | MUST：Ed25519；签名范围见 `NP-VDC-01`…`03`（非 `Ed25519Signature2020` 默认路径） |
| confirm 改 status | 合法转移才改状态；非法 MUST 拒（`E_STATE_INVALID`） |
| （常未提验收） | `(deliverable, rule)` 确定性可复算；验收与价格解耦 |

---

## 8. 给外部实现者的「翻译句」

| 若对方说… | 你回应… |
|-----------|---------|
| 我们要做 Record Schema | 做 **VDC schema**（已有 `vdc.schema.json`） |
| pending → confirmed 就够了 | 不够；至少跑通到 **SETTLED + 双签**，并支持 dispute 支路 |
| 六个 `novapanda_*` API | 映射到 **Exchange 生命周期 + reverify** |
| `device://` 身份 | 换成 **`ed25519:…`**；设备身份放身体 / 清单 |
| 这是记账系统 | 这是 **交割凭证系统**；钱在 NP-SETTLE 适配器 |
| 升级成 W3C VC / Data Credential | VDC = **Delivery Claim**；不要换 VC 外壳进 CORE |
| `vdc_auto_detect` 自动建证 | 必须显式 **deliver**；检测可辅助运维，不能当建证真源 |
| 另写 `MultiChainWalletManager` | 用现有 **AgentWalletManager**；金额用整数最小单位 |
| 链上 transfer 就算结算完成 | 只有 **SETTLED + 双签 VDC** 才是交割终局；链是旁路轨 |

---

## 9. 刻意不按草图做的事

- 不新增平行 `Record` / `payload_hash` 主 schema  
- 不把状态机缩成两态或 W3C 五态（含 `archived`）  
- 不以「记账」或「Data Credential」替换「Delivery Claim」叙事  
- 不用 W3C VC / `Ed25519Signature2020` 替换现有双签 VDC  
- 不实现 `vdc_auto_detect` 式自动建证  
- 不另起 float 金额的多链钱包基类；不把 `transfer` 当 SETTLED 真源  
- 不把 list / export 当成 CORE MUST（节点身体可有；兼容靠向量）

---

## 10. 接入方产品建议（可吸收 / 已有 / 应挡）

来自第三方智能体「应用时」的体验清单（创建·确认·存证·查询·发现）。协议真源不变；下列只指导 **Adopter Runtime / 身体**。闭环施工图见 [`adopter-closed-loop.md`](adopter-closed-loop.md)。

| # | 建议 | 判断 | 落点 |
|---|------|------|------|
| 1 | 一键创建（任务完立刻记） | 可取（产品） | 映射 `deliver`，非另造 create-record |
| 2 | 富附件 + 交付物哈希 | 已有 | blob + `result_hash` |
| 3 | 草稿模式 | 可取（客户端） | DraftStore；半成品不进已签 VDC |
| 4 | 显式确认才生效 | 已有 | client `confirm` / 双签 |
| 5 | 轻量确认（一键 /「确认」） | 可取（UX） | IntentMap → `confirm`；签仍本地 |
| 6 | 拒绝与修改 | 半有 | `dispute` / `reject`；改单走新交换或争议解决 |
| 7 | 本地优先 JSON/SQLite | 已有 / 可取 | 节点 DB + Agent VdcVault |
| 8 | 廉价哈希锚定 | 可取（旁路） | 身体轨；≠ SETTLED 真源 |
| 9 | 双方互存 | 方向对 | PeerBackup 推同一 VDC 字节 |
| 10 | 多维查询 | 可取（身体） | list/filter；非 CORE MUST |
| 11 | 统计视图 | 可取（运营） | console；不进协议语义 |
| 12 | 导出 PDF/JSON | 半有 | JSON export + reverify；PDF 仅展示壳 |
| 13 | `[NP:v1]` 前缀 | 可酌情（绑定） | 聊天发现辅助；正式靠 Manifest |
| 14 | `/.well-known/novapanda.json` | 已有 | 参考节点已暴露 |
| 15 | 离线缓存恢复同步 | 可取（客户端） | Outbox + 幂等；禁止离线伪 SETTLED |

**演进挡板**：阶段化「积分 / 协议内金融」不采纳；信用用 NP-REP，真钱用 NP-SETTLE 伙伴。施工顺序用 [`adopter-closed-loop.md`](adopter-closed-loop.md) §5（M0–M3）。

---

## 11. 怎么用这份表

- Record / 六接口：§1 · §3 · §4  
- W3C-VC 外壳：§5  
- 钱包 / 结算旁路：§6  
- 接入方 15 条体验：§10 · 闭环设计：[`adopter-closed-loop.md`](adopter-closed-loop.md)  
- 实现方宣称兼容：仍以 [`profiles/NP-MIN.md`](../profiles/NP-MIN.md) + [`conformance/VECTORS.md`](../conformance/VECTORS.md) 为准  
- 最短实现路径：[`IMPLEMENTER_GUIDE.md`](IMPLEMENTER_GUIDE.md)
