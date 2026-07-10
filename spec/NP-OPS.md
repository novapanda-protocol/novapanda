# NovaPanda NP-OPS · 运维与持久化

> **卷**：NP-OPS · 参考节点运营语义

---

## 10. 超时与清扫

- `timeouts`：`contract` / `escrow` / `deliver` / 可选 `verify` / `confirm`。  
- 过期 SHOULD → `EXPIRED_REFUNDED`。  
- `POST /admin/sweep` 清扫入口。

## 11. 争议

- `VERIFIED → DISPUTED → SETTLED | REJECTED`。  
- 生产 SHOULD 独立仲裁者（`NOVAPANDA_ARBITRATOR`）。

## 12. 持久化、防重放、崩溃恢复

- Exchange / idempotency / nonce SHOULD 持久化。  
- `(agent_id, nonce)` MUST 唯一。  
- **capture-before-execute**：`settlement_intent=pending` 再调结算。  
- 启动 MUST `recover()` 幂等重放 pending。  
- RB-04 详设：内部 `T17-Runbook-RB04-settlement-intent悬挂.md`。

### 12.1 Agent Manifest

Agent `/.well-known/novapanda.json` 自签字段见原规范表；节点级 manifest 可不含 `sig`（发现用）。

**参考节点 Admin（NP-NODE）**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/settlement/intents` | RB-04 悬挂扫描 |
| POST | `/admin/recover` | 手动触发 `recover()` |
| GET | `/admin/reconcile/export` | T14 对账导出 |

---

*NP-OPS.md · T16*
