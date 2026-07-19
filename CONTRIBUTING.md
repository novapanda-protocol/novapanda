# 贡献指南（Contributing）

欢迎贡献。本项目的目标是一个**普适、开放、可独立复验**的价值交割协议。

## 开发环境

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# 或   .venv/bin/python -m pip install -e ".[dev]"     # *nix
.venv/Scripts/python.exe -m pytest -q
python demo/run_demo.py
```

## 提交前

- `pytest` MUST 全绿。
- 涉及**复验语义**（规范化、签名范围、状态机、Schema）的改动，MUST 同步更新 `spec/` 并补一致性测试。
- 不引入"协议托管资金 / 协议费 / 代币"等违反中立性铁律的设计。

## 第二实现 / 兼容登记

独立语言或节点实现欢迎。最短路径：

1. [`conformance/CALL_FOR_SECOND_IMPL.md`](conformance/CALL_FOR_SECOND_IMPL.md)（[EN](docs/en/call-for-second-impl.md)）  
2. [`conformance/SECOND_IMPL_STARTER.md`](conformance/SECOND_IMPL_STARTER.md) · SI-01…SI-05  
3. PR 一行到 [`docs/compatibility.md`](docs/compatibility.md)，备注 `settlement: mock | sandbox | licensed partner`

TypeScript 客户端 L0（非第二节点）：`cd sdk/typescript && npm run attest:l0`。

## DCO（Developer Certificate of Origin）

本项目采用 **DCO**（而非传统 CLA）以降低贡献门槛。每个 commit MUST 带 sign-off：

```bash
git commit -s -m "your message"
```

`-s` 会追加一行 `Signed-off-by: Your Name <you@example.com>`，表示你认证了
[developercertificate.org](https://developercertificate.org/) 的条款（你有权提交该代码并以本项目许可发布）。

> 若未来需要将规范著作权集中转入中立实体（见 GOVERNANCE.md 阶段 2），届时会就**规范文本**单独引入轻量 CLA；
> **代码贡献始终走 DCO**。

## 授权

- 你对 `novapanda/` 等代码的贡献，按 **Apache-2.0** 授权。
- 你对 `spec/` 的贡献，按 **CC BY 4.0** 授权。
