# NovaPanda NP-HTTP · 参考 HTTP 绑定

> **卷**：NP-HTTP · 参考节点一种绑定；非唯一互通方式  
> **扩展错误码**（`E_DELEGATION*`、`E_QUOTA` 等）属 **NP-NODE 身体**，非 CORE MUST

---

## 9. HTTP API 与请求鉴权

### 9.1 写操作请求头

| 头 | 说明 |
|----|------|
| `X-Agent-Id` | 调用者 `agent_id` |
| `X-Nonce` | 唯一 nonce |
| `X-Signature` | Ed25519 签名 |
| `X-Delegation-Id` | 可选 · NP-DELEGATE |
| `Idempotency-Key` | SHOULD · propose |

签名输入 canonical JSON：

```json
{"method":"POST","path":"/exchanges/{id}/contract","nonce":"…","body_sha256":"sha256:…"}
```

### 9.2 授权矩阵

| 端点 | 允许调用者 |
|------|-----------|
| `POST /exchanges` | `body.client` |
| `POST …/contract` | client 或 provider |
| `POST …/escrow` / `…/confirm` | client |
| `POST …/deliver` | provider |
| `POST …/verify` / cancel / expire / dispute / resolve | 相关方 |
| GET | 公开 |

### 9.3 Contract 双签

- `terms_hash` 在 propose 冻结。  
- 双方各 `contract_ack` 一次；幂等。

---

## 10. 分布式追踪（traceparent · v0.2 邻接）

> informative · 对齐 [`internal/design/NP-TRACE-traceparent约定.md`](../internal/design/NP-TRACE-traceparent约定.md)  
> **不进 VDC 签名范围**；无 trace 不得拒收交换。

### 10.1 请求头

| 头 | 说明 |
|----|------|
| `traceparent` | W3C Trace Context · 节点 **MAY** 透传 |
| `tracestate` | **MAY** 含 `np=corr:{correlation_id}`（与 Bundle `correlation_id` 对齐） |

入站：节点生成或续传；调用结算伙伴或联邦节点时 **SHOULD** 原样转发。

### 10.2 日志与响应

- 审计日志 / `AuditEvent` **SHOULD** 记录 `correlation_id` 与 trace（若存在）。  
- `GET /exchanges/{id}` 响应 **MAY** 含只读 `extensions.trace`（不参与签名）。  
- **MUST NOT** 在 `tracestate` baggage 中携带 Operator PII。

### 10.3 与 Bundle

编排方 `correlation_id` 为业务关联真源；HTTP trace 为运维排障邻接，二者宜一致但不必强绑。

---

## 13. 错误码

| code | HTTP | 含义 |
|------|:----:|------|
| `E_AUTH_MISSING` | 401 | 缺鉴权 |
| `E_SIG_INVALID` | 401 | 签名失败 |
| `E_REPLAY` | 409 | nonce 重放 |
| `E_FORBIDDEN` | 403 | 越权 |
| `E_DELEGATION` / `E_DELEGATION_LIMIT` / `E_DELEGATION_QUOTA` | 401/403/429 | NP-DELEGATE（NODE） |
| `E_QUOTA` | 429 | propose 配额（NODE） |
| `E_STATE_INVALID` | 409 | 非法状态 |
| `E_NOT_FOUND` | 404 | 不存在 |
| `E_SETTLEMENT_FAILED` | 402 | 结算失败 |
| `E_INVALID` | 400 | 其他 |
| `E_DID_*` / `E_REPUTATION_LOW` | 400/403 | 见参考实现 |
| `E_NOT_IMPLEMENTED` | 501 | v2 off |

响应：`{code, msg}`。

OpenAPI：参考节点 `/docs`（machine-readable 伴生，informative）。

---

*NP-HTTP.md · T16 · v0.2 + §10 traceparent*
