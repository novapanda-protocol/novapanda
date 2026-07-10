# Profile NP-LITE · 轻量 / 弱网 / 边缘交割姿态

> **版本**：0.1 · 2026-07-08  
> **状态**：规范性 Profile 草案 · **可选**；**禁止借本档撕掉 C1**  
> **依赖**：NP-MIN（密码学与 VDC 底线不变）  
> **任务**：T12 · 命令溯源 `继续设计：NP-LITE`  
> **叙事映射（informative）**：业界常说的 L0/L1/L2 ≈ 本档叙述中的 `lite` / `edge` / `full`（实现自选标签，非正式等级认证）

---

## 1. 问题

设备、边缘节点与弱网环境需要：**更小报文、更少往返、可延迟结算意图**——但不能发明「不验签也算 SETTLED」的旁路，也不能用设备运行态冒充交换状态机（见 Charter）。

---

## 2. In Scope / Out of Scope

### In Scope

- 报文与会话的**瘦身约定**（可省略的字段、批处理意图）  
- 弱网下的**重试 / 去重**期望（对齐幂等与 nonce）  
- 与 NP-DELEGATE 短 TTL 委托的配合意向  
- Manifest 能力声明：`lite` / `edge` 姿态  

### Out of Scope

- 取消 Ed25519 / canonical / VDC 双签（**撕 C1 = 违规**）  
- 新的并行「设备态状态机」替代 PROPOSED…SETTLED  
- 降低验收确定性（C5）为「偶尔差不多」  
- 强制所有实现只支持 LITE（MIN/NODE 仍可 full）  

---

## 3. 能力梯度（informative 绑定）

| 标签 | 意图 | 协议底线 |
|------|------|----------|
| `lite` | 极简客户端：少发现、少目录；仍能完成单笔最小交割 | C1 规范化/签名；C2 VDC schema；至少一终态路径 |
| `edge` | 边缘可托管短委托、本地队列、延迟上送 settlement intent | 同上 + capture-before-execute 意图落盘（若碰结算） |
| `full` | 完整 NODE 面（非本档强制） | NP-NODE |

**编码绑定意向（实现侧，非另起算法）**：

- 规范化与哈希：**仍用**仓库现行 canonical / SHA-256（C1）。  
- 签名：**仍用** Ed25519。  
- CBOR/二进制 MAY 作为传输编码，但语义 MUST 可映射回 JSON 测试向量。  
- **禁止**「LITE 专用弱哈希」或「截断签名当正式验签」。

---

## 4. 规范性要求

### 4.1 MUST

1. **[NP-LITE-01]** 宣告本档的实现 MUST 仍满足 NP-MIN 的密码学与独立复验要求。  
2. **[NP-LITE-02]** MUST NOT 因弱网省略 `state` 机非法转移检查或终态退款语义。  
3. **[NP-LITE-03]** 若使用离线队列，上线重放 MUST 保持幂等安全（同 idempotency_key / nonce 规则）。  
4. **[NP-LITE-04]** MUST NOT 将设备运行态（idle/busy/fault…）写入为交换 `state` 的替代枚举。

### 4.2 SHOULD

- **[NP-LITE-B1]** 支持哈希优先交付（可与 NP-PRIV `hash_only` 组合）。  
- **[NP-LITE-B2]** Manifest 声明 `transport.min_rtt_mode` 或等价「可延迟确认」能力。  
- **[NP-LITE-B3]** 与 NP-DELEGATE：设备持有短 TTL 委托，过期自动停写。  

### 4.3 MAY

- 批量确认多笔已本地排队的交付（仍须每笔可映射独立 VDC 或 Bundle 规则）。  
- 物理证据瘦报文（配合 NP-PHYS）。  

---

## 5. Manifest

```json
{
  "profiles": ["NP-MIN", "NP-LITE"],
  "lite": {
    "tier": "edge",
    "canonical": "novapanda-c1",
    "offline_queue": true
  }
}
```

`canonical: "novapanda-c1"` 明示**不另起**规范化方言。

---

## 6. 与 conformance

| Case | LITE 关系 |
|------|-----------|
| **C1** | MUST 通过；本档不得降级 |
| **C-LITE-RT** | 瘦报文↔标准形 round-trip · `tests/test_c_lite_rt.py` |
| **C2–C3 / C5** | MUST 语义保持 |
| **C4** | 离线重放场景 SHOULD 覆盖（OfflineQueue） |
| **C10** | 若声明结算，失败不假 SETTLED 仍适用 |

---

## 7. 威胁与减缓

| 威胁 | 减缓 |
|------|------|
| 「太慢就跳过验签」 | LITE-01；评审红线 |
| 离线双花 propose | 幂等键 + nonce；上线合并 |
| 设备态污染交换态 | LITE-04；Charter |
| 私有压缩不可互通 | 须可逆映射到公开向量 |

---

## 8. 实现时序（门闸）

1. 本设计成文（本任务）  
2. ✅ 转换层 + 向量：瘦报文 → 标准对象 round-trip（**C-LITE-RT**）  
3. （更后）边缘参考客户端；勿先改 CORE  

当前：**编码已挂套件**；边缘客户端仍须另令。

---

## 9. 版本

加性；若变更规范化绑定 → 视为 Breaking 并改 VERSIONING。

---

*NP-LITE 0.1 · 弱网姿态 · 勿撕 C1*
