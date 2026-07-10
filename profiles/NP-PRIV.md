# Profile NP-PRIV · 隐私增强交割姿态

> **版本**：0.1 · 2026-07-08  
> **状态**：规范性 Profile 草案 · **可选**；不替代 NP-MIN  
> **依赖**：NP-MIN  
> **前序**：内部 [`NP-PRIV-范围宪章切片.md`](../internal/design/NP-PRIV-范围宪章切片.md)（K4 · In/Out 与永续张力）  
> **任务**：T11 · 命令溯源 `继续设计：NP-PRIV`  
> **红线**：本档 **不是**「符合某国全部个保法」的合规认证；注销 ≠ 抹除全球 VDC 副本

---

## 1. 问题

交割事实需要可长期复验；运营与个人信息法需要目的限定与可删除路径。NP-PRIV 提供**可选姿态**：在仍可独立论证「交付是否发生」的前提下，减少原文与 PII 的默认暴露，并给出地理/跨境/留存的**标签语言**供实现与策略引擎使用。

---

## 2. In Scope / Out of Scope

### In Scope

- 交付暴露模式：`hash_only` 等（见 §3）  
- **地理精度分级**与上报关闭开关  
- **跨境 / 最小化 / 留存**标签（非全球执法器）  
- Operator PII 与 VDC 签名体分离的实现要求（与身体/NODE 对齐）  
- 日志最小化期望  

### Out of Scope

- 声称已获某一司法辖区合规认证本体  
- 可伪造删除已传播签名字节的「被遗忘」（与复验冲突）  
- 强制零知识证明（MAY 未来子档）  
- 用本档否定公开向量、Litmus 或 NP-MIN  

---

## 3. 交付暴露模式

实现若宣告 `NP-PRIV`，MUST 支持至少一种非「默认全文入库公开」的模式，并在条款或 Manifest 声明：

| `delivery_exposure` | 含义 |
|---------------------|------|
| `hash_only` | VDC / 可公开字段仅含内容哈希；原文经授权通道、短时 URL 或端到端密文元数据取得 |
| `ciphertext_meta` | 公开侧为密文元数据（算法、kid、nonce 等）；明文仅授权方 |
| `full_local` | 全文仅存本地/授权副本；联邦复验方可只验哈希（弱模式须条款写明） |

**[NP-PRIV-01]** SETTLED 路径仍 MUST 产出可验签的 VDC；不得因隐私档省略双签或规范化。  
**[NP-PRIV-02]** deliverable **原文** MAY 按授权过期或用户请求删除；删除 MUST NOT 被宣称为「VDC 从未存在」。  
**[NP-PRIV-03]** Operator 邮箱/手机等 PII MUST NOT 写入 VDC 签名体。

---

## 4. 地理精度分级

| 级别 `geo_precision` | 建议语义 | 默认公网/目录 |
|----------------------|----------|----------------|
| `none` | 不上报位置 | 允许 |
| `region` | 国家/大区级 | 宜为默认上限 |
| `city` | 城市级模糊 | SHOULD 需授权 |
| `precise` | 高精度坐标 | MUST 限本地或显式授权通道；可关闭 |

**[NP-PRIV-04]** 公网发现面默认 MUST NOT 要求 `precise`。  
**[NP-PRIV-05]** 实现 MUST 提供关闭定位上报的配置或等价能力（设备侧 MAY）。

物理交割证据（NP-PHYS）若需高精度，MUST 走授权通道，不得因目录曝光精确点位。

---

## 5. 跨境与留存标签（意向字段 · 策略用）

标签供实现、Composer、结算路由**读取**；协议 MUST NOT 自充「各国执法引擎」。

```json
{
  "privacy": {
    "delivery_exposure": "hash_only",
    "geo_precision": "region",
    "cross_border": "deny|allow|unknown",
    "data_minimization": true,
    "retention_hint": "P30D"
  }
}
```

| 字段 | 要求 |
|------|------|
| `cross_border` | SHOULD：`deny` 时实现 SHOULD 避免将受限载荷默认同步到未声明辖区（身体策略） |
| `data_minimization` | SHOULD：为 true 时默认日志与导出剥离原文 |
| `retention_hint` | MAY：ISO-8601 duration，提示运营留存；**不**改 VDC 密码学永续性 |

**[NP-PRIV-06]** 结算 `receipt` SHOULD 最小化 PII；`provider_ref` MUST NOT 塞入身份证号等政府证件号。

---

## 6. 与 VDC 永续（设计裁决 · 继承切片）

| 数据 | 可否删 | 说明 |
|------|:------:|------|
| VDC 签名包装字段 | 不可伪造全球删除 | 节点删库 ≠ 持有副本者无法复验 |
| deliverable 原文 | 可按政策删 | 复验改为持有原文方或仅哈希弱模式 |
| Operator PII | 可注销/匿名化 | 不得进签名体 |
| 伙伴 KYC | 伙伴管辖 | 协议不存 |

**产品话术**：注销账号 = 停止本实例服务与 PII 处理 ≠ 撤销已发生交割事实。

---

## 7. Manifest

```json
{
  "profiles": ["NP-MIN", "NP-PRIV"],
  "privacy": {
    "delivery_exposure": ["hash_only"],
    "geo_precision_default": "region",
    "geo_precision_max_public": "city"
  }
}
```

未见宣告 ⇒ 对端 MUST NOT 假设对端承诺 `hash_only`。

---

## 8. 与其它 Profile

| Profile | 关系 |
|---------|------|
| NP-MIN | 不依赖 PRIV；MIN 可用哈希实践但不强制本档 |
| NP-NODE | 身体：PII 分离、备份、注销出口 |
| NP-SETTLE | receipt 少 PII；真钱合规在伙伴 |
| NP-CLAIM-XFER | Claim 元数据同样最小化 |
| NP-DELEGATE | 审计可记 delegation_id；勿记密钥与证件号 |
| NP-LITE | 弱网可只传哈希+短委托；不降低验签要求 |

---

## 9. 宣传与认证纪律

- 禁止在未跑通可演示路径前宣传「已获 NP-PRIV 认证」。  
- 本档通过 ≠ 任一国家个保法合规证书。  

完整法规适配：**运营方 / 伙伴责任**（外置）。

---

## 10. 测试

- **C-PRIV**：`tests/test_c_priv.py`（hash_only · 无 Operator PII · ciphertext_meta）  
- 公网 Manifest 不强制 precise geo（政策默认 `city`）  
- 注销话术与导出包（身体）对齐——工程测另挂 NODE  

---

## 11. 版本

加性；破坏暴露模式语义 → 大版本。

---

*NP-PRIV 0.1 · 隐私姿态 · 非合规证书*
