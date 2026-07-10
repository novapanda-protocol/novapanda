# NovaPanda · 智能开放交割协议

> **对外主称呼：** **NovaPanda 智能开放交割协议**（*Intelligent Open Delivery Protocol*）· 技术本质为智能世界的**开放交割语法** · 名称规范见 [`internal/ops/对外名称规范.md`](internal/ops/对外名称规范.md)

> **北极星：** 让一切智能体、智能设备、大模型，在**无预建关系**下，用同一套**可验证的交割语言**彼此交换价值——**智能万物交换**。
>
> 智能世界**不是先统一货币**，而是先统一**「交割与互认」**。我们不造新钱，我们给智能世界一种**「承认彼此付出」**的共同语言。
>
> 今天从陌生软件 Agent 的模拟舱出发；明天同一套 VDC + 状态机平移到能源、机器人与物理设备。详见 [愿景与路径](https://novapanda.io/vision.html)。

> 让任意智能体/智能设备之间，在**无预建关系**下完成**跨主体**价值交换——
> 不发币、不托管资金、不收协议费；交割的真理是一份**任何人都能独立复验**的凭证（VDC）。

**品牌：NovaPanda** · Python 包名 `novapanda` · TypeScript `@novapanda/sdk`。规范 CC BY 4.0、代码 Apache-2.0。

**官方站点：** [https://novapanda.io](https://novapanda.io)（`novapanda.xyz` 跳转至主域）· [愿景](https://novapanda.io/vision.html) · [协议宪法](https://novapanda.io/constitution.html) · [交换场景](https://novapanda.io/scenarios/overview.html) · [Vision (EN)](https://novapanda.io/en/vision.html)

<details>
<summary><strong>English TL;DR</strong></summary>

**NovaPanda** is an open protocol for **verifiable value delivery** between strangers — agents, devices, and models with **no pre-existing relationship**.

- **North star:** Universal machine exchange — one shared, verifiable delivery language before unifying money.
- **First citizen:** **VDC** (Verifiable Delivery Credential) — dual-signed, independently re-verifiable off any node.
- **Not:** a wallet, token, bank, or platform taking a cut on every swap.
- **Access surfaces (SPEC §7):** Skill · MCP · A2A · SDK (Python + TypeScript) · adapters · raw HTTP — all equivalent translations; core semantics unchanged.
- **Settlement rails (pluggable):** mock / x402 / AP2 / fiat HTTP skeletons — Trial uses **mock only**.
- **Litmus:** Can a stranger agent complete delivery per the public spec, without our proprietary stack, and can anyone re-verify the VDC?

Try: [Trial](https://novapanda.io/trial.html) · mock node [`node.novapanda.io`](https://node.novapanda.io) · [SPEC](spec/SPEC.md)

**Brand notice:** NovaPanda is the protocol working name. Trademark application pending in China (App. No. `________`, filed `____-__-__`); **not** a registered mark yet — do not use ® until counsel confirms. Public trial uses **mock settlement only**.

</details>

> **品牌说明**：**NovaPanda** 为本项目协议工作名。主域名已注册；**国家知识产权局商标申请已提交**（申请号：`________`，申请日：`____-__-__`），**尚未核准注册**，对外请勿使用 ® 或「已注册商标」表述。高调宣传前请阅读 [`conformance/PRE_PUBLISH_CHECKLIST.md`](conformance/PRE_PUBLISH_CHECKLIST.md)。

## 交换场景图谱（开源）

公开设想的交割场景用图表达，**文案与 SVG 均在仓库** [`docs/scenarios/`](docs/scenarios/)：

- [场景总览](docs/scenarios/overview.md) · [目录 catalog](docs/scenarios/catalog.md) · [`catalog.json`](docs/scenarios/catalog.json)
- 图：生命周期 / 陌生人 / 分层 / 矩阵（`docs/scenarios/figures/`）
- 在线路由：<https://novapanda.io/scenarios/overview.html>

零号节点将挂载同一份 `catalog.json`（控制台「场景」Tab），避免运营站与开源两套故事。

## 这是什么
价值交换的第一公民是 **VDC（可验证交割凭证）**：结构化、Ed25519 双签、可被任何人脱离本系统独立验真。本仓库提供：

- **凭证层**：JSON/CBOR canonical + SHA-256 + Ed25519 双签（`state` 不进签名）。
- **状态机**：`PROPOSED → … → SETTLED`（含拒绝/超时/争议/取消）。
- **验收**：SchemaVerifier + 可选 LLM judge（预检链 + 网关 + audit 快照）。
- **结算**：Mock / x402 / AP2 / 法币 HTTP 骨架（**参考 fake 网关**；真实持牌伙伴对接属部署层，**不阻塞协议验证**）。
- **信誉**：哈希链 + 加权 score + 可选 gate / 联邦 import。
- **节点 + SDK**：Python 参考节点 + TypeScript `@novapanda/sdk`；私钥永不上送。
- **接入面（SPEC §7）**：Skill / MCP / A2A / SDK / 适配器 / 裸 HTTP — 等价翻译，不改变 VDC 与状态机语义（`novapanda/surfaces/`）。

## 设计底线

> 普适通用 · 降低接入难度 · 要标准 · 要开放。
> Litmus：陌生 Agent 能否不依赖我方专有组件、不经许可，照规范完成交割并被任何人独立复验？

## 快速开始（约 5 分钟）

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q          # 223+ tests
.\.venv\Scripts\python.exe demo\run_demo.py      # 陌生 Agent 完整交割
.\.venv\Scripts\python.exe demo\nested_diligence.py  # 嵌套尽调三连 Bundle
.\.venv\Scripts\python.exe demo\plugfest.py       # 9 场景冒烟
python -m conformance.run                         # C1–C8 一致性套件
```
```bash
cd sdk/typescript && npm run build && npm test    # TS parity + lifecycle
```

### 独立复验 VDC

```bash
python -m novapanda.reverify demo/out/settled_vdc.json --deliverable demo/out/deliverable.json
```

### 启动节点

```bash
# 开发
$env:NOVAPANDA_AUTH="0"
.\.venv\Scripts\python.exe -m uvicorn novapanda.node.app:create_app --factory --reload

# 生产（SQLite + 鉴权 + 环境配置）
$env:NOVAPANDA_DB="novapanda.sqlite"
$env:NOVAPANDA_AUTH="1"
.\.venv\Scripts\python.exe -m uvicorn novapanda.node.app:create_app_from_config --factory
```

### 常用环境变量

| 变量 | 说明 |
|------|------|
| `NOVAPANDA_AUTH` | 鉴权 1/0 |
| `NOVAPANDA_DB` | SQLite 路径 |
| `NOVAPANDA_SETTLEMENT` | mock / x402 / ap2 / fiat |
| `NOVAPANDA_WITNESS_V2` / `NOVAPANDA_FEDERATION_V2` | v2 特性 |
| `NOVAPANDA_VERIFIER` / `NOVAPANDA_LLM_JUDGE` / `NOVAPANDA_LLM_GATEWAY_URL` | 验收器 |
| `NOVAPANDA_REP_MIN_SCORE` / `NOVAPANDA_REP_GATE_STRICT` | 信誉 gate |

完整列表见 [`novapanda/config.py`](novapanda/config.py) 与 [`spec/SPEC.md`](spec/SPEC.md) §19。

### 公开试用节点

- **Trial 指南（官网）：** [https://novapanda.io/trial.html](https://novapanda.io/trial.html)
- 节点（mock）：[`https://node.novapanda.io`](https://node.novapanda.io)
- 一键脚本：`python demo/trial_remote.py`
- 健康检查：`GET /health`
- Manifest：`GET /.well-known/novapanda.json`

自营节点部署与运维文档不在本公开仓库；第三方可按规范与参考实现自建同构节点。

## 仓库结构

```
novapanda/        参考实现（Python）
sdk/typescript/ TypeScript SDK
spec/           规范 + JSON Schema
demo/           模拟舱 + plugfest
tests/          pytest + 一致性向量
```

## 文档

- [`CHARTER.md`](CHARTER.md) — 范围宪章与 Litmus
- [`docs/IMPLEMENTER_GUIDE.md`](docs/IMPLEMENTER_GUIDE.md) — 实现者最短路径
- [`docs/compatibility.md`](docs/compatibility.md) — 兼容实现登记（欢迎第二实现）
- [`spec/SPEC.md`](spec/SPEC.md) — 协议规范
- [`profiles/`](profiles/) — 能力档（MIN / NODE / BUNDLE / SETTLE / …）
- [`VERSIONING.md`](VERSIONING.md) · [`SECURITY.md`](SECURITY.md) · [`GOVERNANCE.md`](GOVERNANCE.md) · [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`conformance/CERTIFICATION.md`](conformance/CERTIFICATION.md) — Conformance C1–C8
- [`conformance/VECTORS.md`](conformance/VECTORS.md) — 黄金向量与 SPEC/Profile 挂钩
- [`conformance/PRE_PUBLISH_CHECKLIST.md`](conformance/PRE_PUBLISH_CHECKLIST.md) — 公开发布前检查

## 许可

- 代码：Apache-2.0
- 规范：CC BY 4.0
- 社区：[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) · 安全披露见 [`SECURITY.md`](SECURITY.md) §6
