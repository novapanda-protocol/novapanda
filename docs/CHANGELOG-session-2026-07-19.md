# 工作记录 · 2026-07-19

> Steward 日结 · 软发前竖切收口  
> 分支：`main` · CI：绿（`a4e29bd` 起）

---

## 今日交付（已 push）

| Commit | 内容 |
|--------|------|
| `dc3ff37` | Adopter Runtime M1–M7 · 第二实现征集包 · TS offline reverify |
| `c695892` | OpenClaw BINDING · LITE 嵌入边界 · pair_cli + Skill 壳 |
| `4eecfc1` | 生态适配器 registry（openclaw / mqtt_iot / ros2）· 社区模板 |
| `e79eaf8` | `np ecosystem list` · mqtt demo · catalog 场景挂钉 |
| `a4e29bd` | CI 修复：`python-multipart` · TS plugfest 无 dist 时 skip |

仓库 About：Description / homepage / topics 已补。

---

## 关键落点（给人用）

| 用途 | 入口 |
|------|------|
| 车 × OpenClaw 真跑 | `demo/openclaw_pair/README.md` · `SKILL.md` |
| 对接清单 | `docs/openclaw-adopter-checklist.md` |
| 嵌入边界 | `docs/lite-embedded-boundary.md` |
| 生态共建 | `docs/ecosystem-adapters.md` · `adapters/` |
| 第二实现征集 | `conformance/CALL_FOR_SECOND_IMPL.md` |
| 列出适配器 | `python -m novapanda ecosystem list` |

---

## 红线（对外）

- 结算口头：**mock**  
- 商标未核准：不用 ®  
- 私钥不上 OpenClaw / 云端  
- 不宣称真机量产 / 持牌清算

---

## 未做 / 下次你来

- [ ] 车 + OpenClaw **真实操作与录屏**（环境与 CLI 已齐）  
- [ ] 有伙伴后再加深 ROS2 / 厂商 SDK  
- [ ] 商标核准前保持软发节奏  

---

## 本机真跑最短命令（备忘）

```bash
uvicorn novapanda.node.app:create_app --factory --host 127.0.0.1 --port 8765
python demo/openclaw_pair/pair_cli.py init --root demo/out/openclaw_pair
python demo/openclaw_pair/pair_cli.py run --root demo/out/openclaw_pair --base-url http://127.0.0.1:8765
```

---

*收工 · 2026-07-19*
