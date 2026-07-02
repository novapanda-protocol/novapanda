# NovaPanda · 智能世界价值交割层

> 让任意智能体/智能设备之间，在**无预建关系**下完成**跨主体**价值交换——
> 不发币、不托管资金、不收协议费；交割的真理是一份**任何人都能独立复验**的凭证。

**对外品牌：NovaPanda** · 参考实现 Python 包名仍为 `troodon`（内部代号）。规范 CC BY 4.0、代码 Apache-2.0。

**官方站点：** [https://novapanda.io](https://novapanda.io)（`novapanda.xyz` 跳转至主域）

> **品牌筹备中**：**域名已注册**（Namecheap）；**NovaPanda 国内商标已提交**（待缴费/受理）。**对外高调发布前**请阅读 [`conformance/PRE_PUBLISH_CHECKLIST.md`](conformance/PRE_PUBLISH_CHECKLIST.md)。

## 这是什么
价值交换的第一公民是 **VDC（可验证交割凭证）**：结构化、Ed25519 双签、可被任何人脱离本系统独立验真。本仓库提供：

- **凭证层**：JSON/CBOR canonical + SHA-256 + Ed25519 双签（`state` 不进签名）。
- **状态机**：`PROPOSED → … → SETTLED`（含拒绝/超时/争议/取消）。
- **验收**：SchemaVerifier + 可选 LLM judge（预检链 + 网关 + audit 快照）。
- **结算**：Mock / x402 / AP2 / 法币 HTTP 骨架（**参考 fake 网关**；真实持牌伙伴对接属部署层，**不阻塞协议验证**）。
- **信誉**：哈希链 + 加权 score + 可选 gate / 联邦 import。
- **节点 + SDK**：Python 参考节点 + TypeScript SDK；私钥永不上送。

## 设计底线

> 普适通用 · 降低接入难度 · 要标准 · 要开放。
> Litmus：陌生 Agent 能否不依赖我方专有组件、不经许可，照规范完成交割并被任何人独立复验？

## 快速开始（约 5 分钟）

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q          # 223+ tests
.\.venv\Scripts\python.exe demo\run_demo.py      # 陌生 Agent 完整交割
.\.venv\Scripts\python.exe demo\plugfest.py       # 9 场景冒烟
python -m conformance.run                         # C1–C7 一致性套件
```
```bash
cd sdk/typescript && npm run build && npm test    # TS parity + lifecycle
```

### 独立复验 VDC

```bash
python -m troodon.reverify demo/out/settled_vdc.json --deliverable demo/out/deliverable.json
```

### 启动节点

```bash
# 开发
$env:TROODON_AUTH="0"
.\.venv\Scripts\python.exe -m uvicorn troodon.node.app:create_app --factory --reload

# 生产（SQLite + 鉴权 + 环境配置）
$env:TROODON_DB="troodon.sqlite"
$env:TROODON_AUTH="1"
.\.venv\Scripts\python.exe -m uvicorn troodon.node.app:create_app_from_config --factory
```

### 常用环境变量

| 变量 | 说明 |
|------|------|
| `TROODON_AUTH` | 鉴权 1/0 |
| `TROODON_DB` | SQLite 路径 |
| `TROODON_SETTLEMENT` | mock / x402 / ap2 / fiat |
| `TROODON_WITNESS_V2` / `TROODON_FEDERATION_V2` | v2 特性 |
| `TROODON_VERIFIER` / `TROODON_LLM_JUDGE` / `TROODON_LLM_GATEWAY_URL` | 验收器 |
| `TROODON_REP_MIN_SCORE` / `TROODON_REP_GATE_STRICT` | 信誉 gate |

完整列表见 [`troodon/config.py`](troodon/config.py) 与 [`spec/SPEC.md`](spec/SPEC.md) §19。

### 生产部署（自营全球节点）

**路径**：mock 上云 → x402 sandbox → 持牌法币伙伴。AWS / 阿里云国际通用 Docker 方案：

- [`deploy/README.md`](deploy/README.md) — 架构、阶段、环境变量、cron
- [`deploy/OPERATOR_LEGAL.md`](deploy/OPERATOR_LEGAL.md) — 主体/银行/国内公司说明
- [`deploy/MOCK_STABILITY.md`](deploy/MOCK_STABILITY.md) — mock 稳定标准与 smoke 脚本
- [`deploy/MINIMAL_LAUNCH_CN.md`](deploy/MINIMAL_LAUNCH_CN.md) — 国内公司一页启动 + 对外试用说明
- [`deploy/aws/README.md`](deploy/aws/README.md) / [`deploy/aliyun/README.md`](deploy/aliyun/README.md)

## 仓库结构

```
troodon/        参考实现（Python）
sdk/typescript/ TypeScript SDK
spec/           规范 + JSON Schema
demo/           模拟舱 + plugfest
tests/          pytest + 一致性向量
```

## 文档

- [`spec/SPEC.md`](spec/SPEC.md) — 协议规范
- [`GOVERNANCE.md`](GOVERNANCE.md) / [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`conformance/CERTIFICATION.md`](conformance/CERTIFICATION.md) — Conformance C1–C7
- [`conformance/PRE_PUBLISH_CHECKLIST.md`](conformance/PRE_PUBLISH_CHECKLIST.md) — 公开发布前检查
- [`deploy/README.md`](deploy/README.md) — 参考节点部署

## 许可

- 代码：Apache-2.0
- 规范：CC BY 4.0
