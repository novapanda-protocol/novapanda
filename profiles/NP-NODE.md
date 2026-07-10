# Profile NP-NODE · 可运营节点

> **版本**：0.1 · 2026-07-08  
> **依赖**：宣告 NP-NODE 的实现 MUST 同时满足 **NP-MIN**。

---

## 1. 要求

在 NP-MIN 之上，节点实现 MUST：

1. **持久化**交换与 VDC（崩溃后状态可恢复）。  
2. 启动时 **`recover()`**（或等价）：幂等重放 pending 结算意图并补齐终态。  
3. **超时清扫**（sweep）：推动 EXPIRED 类退款语义。  
4. **`GET /health`**（或等价）报告存活与关键依赖。  
5. **Manifest** 于 well-known（或文档化等价发现入口），且对端可验签。  
6. 写操作鉴权模型符合 SPEC（Agent 签名头）；生产部署 SHOULD 默认启用鉴权。  
7. 信誉若暴露，须为可复验哈希链（或明确宣告未实现 NP-REP）。

实现 SHOULD：

- conformance **C4、C6、C7**。  
- OpenAPI 或等同机器可读 API 描述。  
- 联邦拉取 VDC 的只读路径（若开启联邦特性）。

实现 MAY：

- Operator 注册、配额、控制台——属身体，须在 Manifest `features` 声明，且不得替代 Agent 鉴权。

---

## 2. 显式不要求

- 执行 Bundle `depends_on`（编排默认在客户端）。  
- 持牌清算、短信 OTP。

---

## 3. Manifest 示例

```json
{
  "profiles": ["NP-MIN", "NP-NODE"],
  "features": {
    "access_policy": "open_quota"
  }
}
```

---

## 4. 测试挂钩

见 [conformance/VECTORS.md](../conformance/VECTORS.md) 中 NP-NODE 行。
