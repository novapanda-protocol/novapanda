# Troodon 协议规范 v0

> 本规范（spec 目录）以 **CC BY 4.0** 授权；参考实现代码以 **Apache-2.0** 授权。
> 协议品牌名：**Troodon**（工作名，已定稿）。文字商标注册与官方域名筹备中；公开前见 [`../conformance/PRE_PUBLISH_CHECKLIST.md`](../conformance/PRE_PUBLISH_CHECKLIST.md)。
本规范定义智能体之间**跨主体、无预建关系**的价值交割层。它不规定价格、不发币、不托管资金；
它只规定一件事：**如何产出一份任何第三方都能独立复验的「可验证交割凭证」（VDC）**。

关键词 MUST / SHOULD / MAY 按 RFC 2119 解释。

---

## 1. 身份（Identity）

- Agent 身份 MUST 为 Ed25519 公钥；`agent_id` = `"ed25519:" + base58(pubkey)`。
- 私钥 MUST 仅存于本地，MUST NOT 上送任何节点。
- 任何一方仅凭对端 `agent_id` 即可验签，**无需预建关系**。

## 2. 规范化与密码学（Canonicalization & Crypto）

- 规范化 JSON MUST：键按 Unicode 码点排序、紧凑分隔符（无空白）、字符串 NFC 归一、UTF-8 编码。
- v0 MUST NOT 使用浮点数；小数以字符串承载（避免跨语言浮点格式分歧）。目标对齐 RFC 8785 (JCS)。
- 哈希 MUST 为 SHA-256，统一表示为 `sha256:<hex>`。
- 签名 MUST 为 Ed25519，编码为 base64url（无填充）。

### 2.1 VDC 签名范围（规范性）

- `state` 是生命周期标记，由交换/节点驱动，**MUST NOT 进入签名**（否则状态流转会使签名失效）。
- `provider_sig` = Ed25519( canonical( VDC 去掉 `signatures`、`state` ) )，编码为 **JSON canonical**（默认）或 **CBOR canonical**（`signatures.provider_payload_encoding=cbor`）。
- `client_sig`   = Ed25519( canonical( VDC 去掉 `state`、`signatures.client_sig` ) )，即 client 在 provider 签名之上认可。
VDC 结构 MUST 符合 [`schemas/vdc.schema.json`](schemas/vdc.schema.json)。

## 3. 交换状态机（Exchange State Machine）

```
PROPOSED → CONTRACTED → ESCROWED → DELIVERED → VERIFIED → SETTLED
   │            │           │           │
   ├────────────┴───────────┴──→ CANCELLED / EXPIRED_REFUNDED
                                  DELIVERED → REJECTED
                                  VERIFIED  → DISPUTED → SETTLED / REJECTED
```

- 终态：`SETTLED` / `REJECTED` / `EXPIRED_REFUNDED` / `CANCELLED`，MUST 无出边。
- 实现 MUST 拒绝非法转移。
- 进入终态退款语义（`REJECTED`/`EXPIRED_REFUNDED`/`CANCELLED`）MUST 触发已冻结资金退款。

## 4. 验收（Verification）

- 验收 MUST 与价格解耦：验收只回答「是否达标」，由 `rule_id` 指向的规则定义。
- 验收 MUST 确定性可复算：给定相同 `(deliverable, rule)`，任意第三方 MUST 得到相同 `passed`。
- v0 参考验收器为 JSON Schema（Draft 2020-12）校验。
- v1 参考实现另提供 `LLMJudgeVerifier`：schema/物理预检链 + 可选 HTTP/OpenAI 网关；`llm_audit` 含 prompt/model 快照供审计。
## 5. 结算（Settlement）

- 协议对资金流转**不可知**：结算为可插拔旁路（Mock / x402 / AP2 / 法币持牌伙伴）。
- 协议本身 MUST NOT 托管资金、MUST NOT 收取协议费、MUST NOT 发行代币。

## 6. 信誉（Reputation）

- 信誉账本 MUST 为 append-only 哈希链，每条记录由节点签名。
- 记录 MUST 符合 [`schemas/reputation-entry.schema.json`](schemas/reputation-entry.schema.json)。
- 任意持有者 MUST 能：重算 `entry_hash`、校验 `prev_hash` 链接、验证节点签名——无需信任该节点。

## 7. 接入面（Access Surfaces）

实现 SHOULD 提供多种等价接入：SDK / MCP / A2A / Skill / 适配器 / 裸 HTTP。
所有接入面 MUST 仅做「翻译」，MUST NOT 改变上述凭证、状态机与复验语义。

## 8. 一致性（Conformance）

一个实现被称为「Troodon 兼容」当且仅当：
1. 规范化与 VDC 双签可与参考实现互验；
2. 状态机转移与终态语义一致；
3. 产出的 VDC / 信誉记录通过本目录 JSON Schema 校验；
4. 验收决策确定性可被第三方复算；
5. Agent Manifest 可被发现、验签，并用于发起交换（C7）。

> 一致性即成员资格（conformance = membership）：不靠许可，靠可复验。

---

## 9. HTTP API 与请求鉴权

### 9.1 通用请求头（写操作 MUST）

| 头 | 说明 |
|----|------|
| `X-Agent-Id` | 调用者 `agent_id` |
| `X-Nonce` | 唯一 nonce（防重放） |
| `X-Signature` | 对请求 canonical 字节的 Ed25519 签名 |
| `Idempotency-Key` | SHOULD 用于 `POST /exchanges`（body 内 `idempotency_key` 亦 MUST） |

签名输入 MUST 为 canonical JSON：

```json
{"method":"POST","path":"/exchanges/{id}/contract","nonce":"…","body_sha256":"sha256:…"}
```

### 9.2 授权矩阵（authz）

| 端点 | 允许调用者 |
|------|-----------|
| `POST /exchanges` | `body.client` |
| `POST …/contract` | client 或 provider |
| `POST …/escrow` / `…/confirm` | client |
| `POST …/deliver` | provider |
| `POST …/verify` / `…/cancel` / `…/expire` / `…/dispute` / `…/resolve` | 相关方 |
| GET 端点 | 公开（无需签名） |

生产节点 SHOULD 默认启用鉴权（`auth=true`）；开发/测试 MAY 关闭。

### 9.3 Contract 双签

- `propose` 时节点 MUST 计算并冻结 `terms_hash = sha256(canonical(条款字段))`。
- `POST …/contract` body MUST 含 `signature`：调用者对 `{action:"contract_ack", exchange_id, terms_hash}` 的 Ed25519 签名。
- client **与** provider 各 ack 一次；双方齐后才 `PROPOSED → CONTRACTED`。
- 重复 ack 同一方 MUST 幂等（不重复副作用）。

---

## 10. 超时与清扫

- `timeouts` 按阶段（`contract` / `escrow` / `deliver` / 可选 `verify` / `confirm`）设 `deadline`。
- `verify` / `confirm` 超时过期 SHOULD 清扫为 `EXPIRED_REFUNDED`（参考实现）。
- `DELIVERED` 后若未设 `verify` 超时，MAY 清除 deliver deadline；争议走 §11。- 节点 SHOULD 提供清扫入口（如 `POST /admin/sweep`），将过期且可转 `EXPIRED_REFUNDED` 的交换退款。

---

## 11. 争议（DISPUTED）

- `VERIFIED → DISPUTED → {SETTLED | REJECTED}`。
- 任一方 MAY 在 `VERIFIED` 后发起 `POST …/dispute`。
- `POST …/resolve` body：`outcome` = `settle` | `reject`。
- v0 参考实现允许相关方裁决；生产 SHOULD 限定独立仲裁者。

---

## 12. 持久化、防重放与崩溃恢复

- Exchange / idempotency / nonce SHOULD 持久化（SQLite 或等价）。
- `(agent_id, nonce)` MUST 唯一；重放窗口 SHOULD 为 24h（过期 nonce 可清理）。
- 结算/退款 MUST **capture-before-execute**：先落盘 `settlement_intent=pending`，再调外部结算；完成后 `done`。
- 节点启动 MUST 调用 `recover()`，幂等重放 pending 意图并补齐终态。

---

## 12.1 Agent Manifest（能力发现）

Agent SHOULD 在 `/.well-known/troodon.json` 自签 manifest：

| 字段 | R/O | 说明 |
|------|:---:|------|
| `protocol` | R | `"troodon"` |
| `version` | R | 规范版本 |
| `agent_id` | R | Ed25519 agent_id |
| `did` | O | `did:troodon:<agent_id>`；若 present MUST 与 `agent_id` 一致 |
| `pubkey` | R | base64url 公钥 || `capabilities[]` | R | `{resource_type, rules[], price?}` |
| `endpoints.exchange` | R | 交换节点 URL |
| `endpoints.transport[]` | R | `http` / `mcp` / `a2a` / `skill` |
| `sig` | R | 对除 `sig` 外 canonical 字节的自签名 |

对端 MUST 验签 manifest 后再信任其能力声明。

---

## 13. 错误码

| code | HTTP | 含义 |
|------|:----:|------|
| `E_AUTH_MISSING` | 401 | 缺鉴权头 |
| `E_SIG_INVALID` | 401 | 请求签名失败 |
| `E_REPLAY` | 409 | nonce 重放 |
| `E_FORBIDDEN` | 403 | 越权 |
| `E_STATE_INVALID` | 409 | 非法状态转移 |
| `E_NOT_FOUND` | 404 | 资源不存在 |
| `E_SETTLEMENT_FAILED` | 402 | 结算失败（可重试） |
| `E_INVALID` | 400 | 其他业务/校验错误 |
| `E_DID_INVALID` / `E_DID_MISMATCH` | 400 | DID 格式或 party 不一致 |
| `E_REPUTATION_LOW` | 403 | 信誉门槛未达（`TROODON_REP_MIN_SCORE`） |
| `E_NOT_IMPLEMENTED` | 501 | v2 能力未启用（特性开关 off） || `E_TYPE_UNKNOWN` / `E_RULE_UNKNOWN` | 400 | 本体/规则未注册 |

响应体：`{code, msg}`（与参考实现一致）。

---

## 14. v2 见证 + 质押（特性开关）

默认 `TROODON_WITNESS_V2=0`（端点返回 501）。设为 `1` 后启用 attach/lock/slash/release。

Schema：[`witness-attestation.schema.json`](schemas/witness-attestation.schema.json)、[`stake-lock.schema.json`](schemas/stake-lock.schema.json)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v2/witness/validate` | 校验见证声明（始终可用） |
| POST | `/v2/stake/validate` | 校验质押结构（始终可用） |
| POST | `/exchanges/{id}/v2/witness/attach` | 挂 witness 到 VDC（需 WITNESS_V2） |
| POST | `/v2/stake/lock` | 锁定质押（需 WITNESS_V2；SQLite 持久化） |
| POST | `/v2/stake/release` | 释放质押 |
| POST | `/v2/stake/slash` | 罚没质押 |

`TROODON_WITNESS_REQUIRE_STAKE=1` 时 attach 前 MUST 存在同 exchange 的 locked stake。

## 15. 持久化：vdcs 表 + stakes 表

SQLite 部署时 VDC 正文 MUST 存入 `vdcs` 表；质押存入 `stakes` 表。`GET /vdc/{vdc_id}` 公开只读，供联邦拉取。

## 16. 联邦与可携带性

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/reputation/export` | 导出信誉 bundle |
| POST | `/v2/reputation/validate` | 校验外链 bundle |
| POST | `/v2/reputation/import` | 导入 mirror（`TROODON_FEDERATION_V2=1`） |
| GET | `/v2/reputation/{agent_id}/score` | 本地加权 score（含 mirror） |
| GET | `/exchanges/{id}/export` | 可携带交换包 |
| POST | `/v2/identity/key-history/validate` | 密钥历史校验 |

## 17. v1 扩展（LLM · DID · CBOR · TS SDK）

| 方法 | 路径 | 说明 |
|------|------|------|
| — | `TROODON_VERIFIER=llm` | LLM 验收；`TROODON_LLM_JUDGE=regex\|field_match\|http\|openai` |
| — | `TROODON_LLM_GATEWAY_URL` / `TROODON_LLM_MODEL` / `TROODON_LLM_API_KEY` | LLM 网关配置 |
| POST | `/v1/did/register` | 注册 DID Document |
| GET | `/v1/did/resolve/{did}` | 解析 did → agent_id + pubkey |
| POST | `/v1/did/validate` | DID Document 结构/签名校验 |
| POST | `/v1/cbor/canonical` | CBOR canonical 编码（需 cbor2） |
| — | `sdk/typescript/` | TS SDK：全生命周期 + Ed25519 + `getReputationScore` |

交换流 MAY 用纯 DID：`propose.provider` / `client` 为 `did:troodon:…`；`contract.party_did` + 签名。

## 18. 物理扩展 v3 + ISO 15118 模拟

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v3/physical/validate` | energy.*/actuation.* deliverable 校验 |
| POST | `/v3/iso15118/sessions` | 创建可测充电会话（模拟器） |
| POST | `/v3/iso15118/sessions/{id}/complete` | 完成会话并产出 deliverable |
| POST | `/v3/iso15118/deliverable` | 一步完成会话并返回 deliverable |

## 19. 信誉聚合与 gate

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v2/reputation/aggregate` | 多 bundle 加权汇总（只读） |

环境变量（完整列表见 `troodon/config.py`）：

| 变量 | 说明 |
|------|------|
| `TROODON_AUTH` | 鉴权开关 |
| `TROODON_DB` / `TROODON_REPUTATION_DB` | SQLite |
| `TROODON_SETTLEMENT` + `TROODON_*_URL` | 结算适配器 |
| `TROODON_WITNESS_V2` / `TROODON_FEDERATION_V2` | v2 特性 |
| `TROODON_TIMEOUT_*` | 各阶段超时 |
| `TROODON_VERIFIER` / `TROODON_LLM_*` | 验收器 |
| `TROODON_REP_WEIGHTS` / `TROODON_REP_MIN_SCORE` / `TROODON_REP_GATE_STRICT` | 信誉 gate |
| `TROODON_WITNESS_REQUIRE_STAKE` | witness 须先 stake |
| `TROODON_ARBITRATOR` | 独立仲裁者 |