# 车 × OpenClaw · 装什么、要不要 Skill

> **规范绑定（informative）**：[`spec/BINDING-OPENCLAW.md`](../../spec/BINDING-OPENCLAW.md)  
> **清单**：[`docs/openclaw-adopter-checklist.md`](../../docs/openclaw-adopter-checklist.md)

目标：两边**少装东西**，用同一套 `pair_cli` 结对，OpenClaw 只需一个薄 Skill 调 CLI。

---

## 一句话答案

| 侧 | 必装 | 要不要做 Skill |
|----|------|----------------|
| **车（Client）** | Python 3.11+ · 本仓库 `pip install -e ".[dev]"` · 本目录 CLI | **不必**装 OpenClaw；确认可用命令行或舱口令 |
| **OpenClaw 主机（Provider）** | 同上 Python 包 · **OpenClaw** · 复制本目录 [`SKILL.md`](SKILL.md) | **要**：一个 Skill，内部只 `subprocess` 调 `pair_cli` |
| **中间（可同机）** | `uvicorn` 参考节点 | 不是第三方「钱包 App」 |

**密钥**：两侧各有 `identity.hex`，**不要**放进 OpenClaw 对话或云端。

---

## 车侧装什么

```text
智能车 / 车机旁路笔记本
├── Python + pip install -e ".[dev]"   # 克隆本仓库后
├── demo/openclaw_pair/pair_cli.py
└── 数据目录（例 demo/out/openclaw_pair/car/）
    ├── identity.hex                  # 自动生成，勿外传
    └── runtime/                      # Outbox / Vault
```

不必装 OpenClaw。日常：

```bash
python demo/openclaw_pair/pair_cli.py init --root demo/out/openclaw_pair
python demo/openclaw_pair/pair_cli.py whoami --role car --root demo/out/openclaw_pair
# 同机一键交割（节点已起时）：
python demo/openclaw_pair/pair_cli.py run --root demo/out/openclaw_pair --base-url http://127.0.0.1:8765
```

---

## OpenClaw 主机装什么

```text
OpenClaw 电脑
├── OpenClaw（你已有）
├── Python + 同一 novapanda 仓库
├── SKILL.md → 拷进 OpenClaw skills（见下）
└── 数据目录 …/claw/identity.hex
```

Skill **要做，但只做一层壳**：不要在 Skill 里重写状态机。  
仓库已提供 [`SKILL.md`](SKILL.md) 模板；把其中的路径改成你的仓库绝对路径即可。

Skill 会调用：

```bash
python …/pair_cli.py skill --role claw --name adopter_vault_stats --root …
python …/pair_cli.py run --root …     # 同机演示
python …/pair_cli.py car-confirm --exchange-id … --root …
```

`adopter_*` 工具列表见 `novapanda.adopter.skill`（确认/导出/vault 等）。  
**propose→deliver 全路径**由 `run` 一键完成（同机）；分机时先同机跑通，再拆。

---

## 推荐：先同机跑通（5 分钟）

终端 A：

```bash
export NOVAPANDA_AUTH=0
uvicorn novapanda.node.app:create_app --factory --host 127.0.0.1 --port 8765
```

终端 B：

```bash
python demo/openclaw_pair/pair_cli.py init --root demo/out/openclaw_pair
python demo/openclaw_pair/pair_cli.py run --root demo/out/openclaw_pair --base-url http://127.0.0.1:8765
python -m novapanda.reverify demo/out/openclaw_pair/settled_vdc.json \
  --deliverable demo/out/openclaw_pair/deliverable.json
```

`ok: true` 后再把 OpenClaw Skill 指到同一 `root`，用自然语言触发 `run` / `skill`。

---

## 分机时（车一台、OpenClaw 一台）

1. 两边都 `pip install -e ".[dev]"`，共享同一 `base-url`（可访问的节点）。  
2. **只在一处** `init`，把 `pair.json` 与对端需要的 `agent_id` 拷过去；或两边分别 init 后手动把 Provider `agent_id` 配进车侧。  
3. 当前 `run` 是同机双 Runtime；分机下一步可拆 `car-propose` / `claw-deliver`（需要时再加）。**先同机 + Skill 触发 `run` 即可宣传。**

---

## 红线

- 结算口头：**mock**  
- Skill / 模型：**不持钥、不代签**  
- 商标未核准：不用 ®  

详见 [`docs/openclaw-adopter-checklist.md`](../../docs/openclaw-adopter-checklist.md)。
