# 钱在哪？· NovaPanda FAQ

> **状态**：公开说明 · 2026-07-10 · **非规范性**（叙事与商业口径；MUST 以 [协议宪法](constitution.html) · [SPEC](https://github.com/novapanda-protocol/novapanda/blob/main/spec/CORE.md) 为准）  
> **网页版**：[faq-money.html](faq-money.html) · **EN**: [en/faq-money.md](en/faq-money.md)

---

## 三句话

1. **协议不铸币、不托管全网资金、不按笔收协议税。**  
2. **VDC 锚的是「交付已发生」**；法币 / USDC / mock 是**可插拔清算腿**，在交换状态机之外。  
3. **运营公司可收服务费**（托管节点、认证、路由、企业支持）——**不是**「拥有协议」。

---

## 常见问题

### 用户付的钱经过你们吗？

**通常不。** 公开 Trial 与零号节点默认 **mock 或 sandbox**（如 Stripe 测试网）。生产清算须经**持牌或声明的结算伙伴**；协议只要求 SETTLED 绑定 `vdc_id` + 诚实的 `settlement_receipt`。

### 那你们赚什么？

| 收入来源 | 是什么 | 不是什么 |
|----------|--------|----------|
| 托管参考节点 | 运营、配额、审计、信誉索引 | 协议许可费 |
| 兼容认证（UC-40） | Steward 复核 + 可选商标许可（前期可不收） | 入网门票 |
| 清算路由 / 对账导出 | 帮伙伴把 VDC 翻译成发票/对账行 | 换汇抽成 |
| 企业支持 / 私有部署 | 红帽模式 | 私有协议 |

### 和 x402 / 链上支付栈什么关系？

**互操作，不替代。** 可用 x402 作一腿清算；差异化在**可验证交付 + 跨 Agent 信誉 + 结算无关 + 开放本体**，不是「又一种扣款 API」。

### Claim 是不是你们发的币？

**不是。** Claim 是**锚定已签 VDC 的结算权柄转让**，不是流通代币。

### 为什么 Manifest 要写 mock / sandbox？

**诚实要求。** 宣称生产清算却仅跑 mock，会在[兼容矩阵](https://github.com/novapanda-protocol/novapanda/blob/main/docs/compatibility.md)与认证复核中被降级或移除。

---

## 图示

```text
  Client ──escrow──► 清算伙伴 / mock / sandbox
       │
       └── Exchange 状态机 ──► VDC（可离线 reverify）
                ▲
                └── 协议核心：不管钱在哪家银行，管「交付是否可证」
```

---

## 相关

- [协议宪法](constitution.html) · [交换场景](scenarios/overview.html)  
- [兼容登记](https://github.com/novapanda-protocol/novapanda/blob/main/docs/compatibility.md)  
- [开发者 Trial](trial.html)

---

*公开 FAQ · 内部真源副本：`internal/design/BA-钱在哪-FAQ.md`*
