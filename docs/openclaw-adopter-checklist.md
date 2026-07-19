# OpenClaw ↔ Adopter · 最小对接清单

> **目标**：智能车（Client）+ OpenClaw（Provider）本周真跑一笔 **SETTLED + 离线 reverify**。  
> **原则**：LLM / OpenClaw 只编排；**签验与状态机在本地 Runtime / SDK**；结算 **mock**。  
> **依赖**：[`adopter-closed-loop.md`](adopter-closed-loop.md) · [`lite-embedded-boundary.md`](lite-embedded-boundary.md) · `novapanda.adopter.skill.AdopterSkill`  
> **开箱结对**：[`demo/openclaw_pair/README.md`](../demo/openclaw_pair/README.md) · CLI + OpenClaw [`SKILL.md`](../demo/openclaw_pair/SKILL.md)

---

## 0. 装什么 / 要不要 Skill（直接答案）

| 侧 | 安装 | Skill |
|----|------|-------|
| **车** | Python · `pip install -e ".[dev]"` · `pair_cli.py` | **不需要** OpenClaw；命令行即可 |
| **OpenClaw 主机** | 同上 + OpenClaw | **需要 1 个薄 Skill**（复制 `demo/openclaw_pair/SKILL.md`，改路径） |
| **节点** | 本机 `uvicorn`（可与任一侧同机） | — |

Skill **不要重写协议**：只 `subprocess` 调 `pair_cli`。同机一键：`pair_cli.py run`。

---

## 0b. 角色与持钥（先钉死）

| 角色 | 身体 | 身份 | 密钥放哪 |
|------|------|------|----------|
| **Client** | 智能车 / 车机旁路 PC | `ed25519:…` | 车侧 `AdopterRuntime` 根目录；**不上云、不进 OpenClaw 日志** |
| **Provider** | OpenClaw 所在主机 | 另一把 `ed25519:…` | OpenClaw 本机旁路进程的 Runtime；Skill 只调 `invoke`，不读 raw key |
| **节点（可选）** | 本机 `uvicorn` 或零号节点 | — | 仅交换中继；仲裁靠导出 JSON |

```text
[车机 / 车侧 PC]                    [跑 OpenClaw 的电脑]
 AdopterRuntime (Client)             AdopterRuntime (Provider)
        │                                   │
        │         NP-HTTP / 局域网          │
        └──────────── 节点 ─────────────────┘
        │                                   │
   舱 UI / 人工确认                    OpenClaw Skill → AdopterSkill.invoke
```

**禁止**：两台共用一把私钥；让模型「记住」seed；用运营账号代签。

---

## 1. 本周交付物（选一个，写死 schema）

推荐 **行程/任务摘要**（不依赖真桩、真狗）：

```json
{
  "task_id": "trip-20260719-001",
  "summary": "从 A 到 B，耗时 18min",
  "odometer_km": 12345,
  "evidence_note": "openclaw-collected"
}
```

| 字段 | 规则 |
|------|------|
| `resource_type` | 建议先用 `data.extraction.structured`（向量成熟）或自建 rule |
| `rule_id` | 与 SchemaVerifier 一致，如 `R-extract-invoice-v1` 形状的自有 rule，或先复用发票 rule 做冒烟 |
| 金额 | 整数最小货币单位；demo 用 `{"amount": 100, "currency": "USD"}` + **mock** |
| 验收 | Provider `deliver` 的 JSON 必须过 schema；失败不得 SETTLED |

有机器人后再换 deliverable（到位坐标、巡检图哈希），**交换步骤不变**。

---

## 2. OpenClaw Skill 映射（最小集）

仓库已有工具定义：`novapanda.adopter.skill.ADOPTER_TOOL_DEFINITIONS`。  
OpenClaw 侧每个 Skill **薄封装** → `AdopterSkill(runtime).invoke(name, args)`。

| OpenClaw Skill 名（建议） | 调用 | 谁绑定 Runtime | 何时用 |
|---------------------------|------|----------------|--------|
| `np_list_tools` | `adopter_list_tools` | 双方均可 | 接入自检 |
| `np_discover` | `adopter_discover_stations` | Client（车） | 找 Provider（可先写死 agent_id） |
| `np_cabin` | `adopter_apply_intent` | **按身份** | 确认/争议/导出（车舱口语） |
| `np_vault` | `adopter_vault_stats` | 双方 | 演示「本地有凭证」 |
| `np_export` | `adopter_export_pack` | 双方 | 仲裁包指纹（人读摘要不可替验签） |
| `np_anchor` | `adopter_anchor` | 可选 | 旁路锚定；**不替代 SETTLED** |

### 2.1 生命周期谁调什么（关键）

`AdopterSkill` **当前不覆盖** propose/contract/escrow/deliver 全路径（那些在 Runtime/SDK）。  
本周真跑请用下列之一，OpenClaw 只做「触发与汇报」：

| 步骤 | Client（车） | Provider（OpenClaw 主机） |
|------|--------------|---------------------------|
| propose | SDK / `AdopterRuntime` 脚本 | — |
| contract ×2 | SDK | SDK |
| escrow | SDK | — |
| deliver | — | SDK + 填好的 deliverable JSON |
| verify | SDK 或舱 `adopter_apply_intent`「验收」 | — |
| confirm | 舱 `adopter_apply_intent`「确认」或 SDK | — |
| reverify | 导出后本地 CLI / TS `attest:l0` | 同左 |

**参考竖切（不经 OpenClaw）**：`python demo/adopter_closed_loop.py`  
OpenClaw 接入后：把该脚本里的人工步骤换成 Skill 触发，**签名仍走 Runtime**。

### 2.2 Skill 伪代码（Provider 侧）

```text
on tool np_deliver_task(task_json):
  # 1) OpenClaw 收集/生成 task_json（可含车况摘要）
  # 2) 调用本机脚本，禁止把 private key 传给模型
  subprocess: python scripts/np_provider_deliver.py --exchange-id … --deliverable task.json
  # 3) 向用户回报 exchange_id + state，不回报签名原文
```

Client 侧同理：`np_confirm` → `adopter_apply_intent(exchange_id, "确认")`。

---

## 3. 环境与命令清单

### 3.1 一次准备

```bash
pip install -e ".[dev]"
# 两台机器或两个目录：client_root / provider_root
export NOVAPANDA_SETTLEMENT=mock   # 或默认 mock；勿写成生产清算
```

### 3.2 本机节点（开发）

```bash
export NOVAPANDA_AUTH=0            # 仅本机联调；外网务必开 auth
uvicorn novapanda.node.app:create_app --factory --host 127.0.0.1 --port 8765
```

车与 OpenClaw 主机若分离：节点放中间机，两边 SDK `baseUrl` 指向它；**密钥仍在各自 Runtime**。

### 3.3 冒烟（不经 OpenClaw）

```bash
python demo/adopter_closed_loop.py
python demo/adopter_smoke_all.py
```

### 3.4 离线复验（宣传素材必录）

```bash
python -m novapanda.reverify path/to/settled_vdc.json --deliverable path/to/deliverable.json
# 或
cd sdk/typescript && npm run attest:l0
```

### 3.5 Manifest（可选诚实声明）

```bash
python -m novapanda manifest validate ./manifest.json --require-profiles
# profiles 含 NP-MIN；弱网加 NP-LITE + offline_queue
```

---

## 4. 验收勾选（真跑通过才算）

- [ ] Client / Provider **两把不同** Ed25519，分属两目录  
- [ ] 一笔交换到达 **`SETTLED`**，双方 vault 各有 VDC  
- [ ] 断开节点后，`reverify(VDC, deliverable)` **全绿**  
- [ ] OpenClaw 对话里只有 tool 结果（state / fingerprint），**无私钥、无完整 seed**  
- [ ] 对外口播：`settlement: mock`；商标未核准不用 ®  
- [ ] （加分）车机或手机录屏 60s：propose→SETTLED→reverify  

---

## 5. 录屏分镜（车 + OpenClaw）

| 镜 | 画面 | 旁白红线 |
|----|------|----------|
| 1 | 两屏显示不同 `agent_id` | 陌生对端、本地持钥 |
| 2 | OpenClaw 聊天触发任务 | Agent 编排，不是口头结算 |
| 3 | 终端/`SETTLED` | 双签 VDC |
| 4 | 停节点后再跑 reverify | 不依赖原节点 |
| 5 | （可选）车舱说「确认」 | `adopter_apply_intent` |

---

## 6. 刻意不做（本清单范围外）

- 等机器人厂商官方嵌入 NovaPanda  
- 在 OpenClaw 云端代持密钥  
- 平行 Record API / 先 SETTLED 再补签  
- ROS2 全量适配（有狗/臂后再做身体层）  
- 把 mock 写成持牌清算  

---

## 7. 下一步（有机器人以后）

同一清单，只换 §1 deliverable（例如到位 pose + 照片 sha256），控制走厂商 SDK；  
VDC 规则见 [`lite-embedded-boundary.md`](lite-embedded-boundary.md)。

---

*OpenClaw 编排 · Adopter 持钥 · 本周 litmus*
