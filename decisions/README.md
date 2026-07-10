# Architecture Decision Records（ADR）

> **状态**：v0.2 模板 · 2026-07-10  
> **抬 G**：G05  
> **纪律**：重大分叉写 ADR；编号递增；合并后不可改标题，只能 `Superseded by`。

## 何时写

- 规范破坏性变更或 Profile 新增  
- 安全 / 结算 / 治理红线解释  
- 「为什么不用 X」且未来会有人再问  

## 文件命名

`NNNN-短标题.md` — 例如 `0001-canonical-json-not-msgpack.md`

## 索引

| ADR | 标题 | 状态 |
|-----|------|------|
| [0001](0001-vdc-first-not-account-balance.md) | VDC 第一公民，非账户余额 | Accepted |
| [0002](0002-settlement-as-adaptor-not-core.md) | 结算作为适配器，不进 CORE | Accepted |
| [0003](0003-bundle-orchestration-client-side.md) | Bundle 编排留在客户端 | Accepted |

模板：[`0000-template.md`](0000-template.md)
