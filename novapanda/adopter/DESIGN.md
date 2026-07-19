# Adopter Runtime · 接入方运行时

> 状态：参考实现 · **不进 CORE SM** · 对齐 [`docs/adopter-closed-loop.md`](../../docs/adopter-closed-loop.md)  
> 职责：填「规范 ↔ 灯塔场景」中空——草稿、出站队列、本地凭证库、意图映射、互存、查询导出。

## 边界

| 允许 | 禁止 |
|------|------|
| 包装 `NovaPandaClient` 做产品面 | 改 `TRANSITIONS` / 另起 Record schema |
| 本地 JSON 落盘、离线排队 | 离线伪称 SETTLED |
| Intent 自然语言 → Exchange ops | 运营账号代签 |
| Peer 互推同一 VDC 字节 | 改签后内容 |

## 模块

| 模块 | 文件 |
|------|------|
| DraftStore | `draft.py` |
| Outbox | `outbox.py` |
| VdcVault | `vault.py` |
| IntentMap | `intent.py` |
| PeerBackup | `peer.py` |
| Query / stats | `query.py` |
| 仲裁包导出 | `export_pkg.py` |
| 门面 | `runtime.py` |
| 车充 M2 | `charge.py`（`ChargeControlAdapter` · `AvChargeLoop`） |
| PDF 壳 M3 | `export_pdf.py` |
| 本地锚定 M3 | `anchor.py` |
| 场站发现 M3 | `stations.py` |
| 可插拔表计 M4 | `meter.py` |
| 多轨锚定 M4 | `anchor_rails.py`（bulletin · chain_stub） |
| 座舱 UX M4 | `cabin.py` |
| 巡检 Bundle M5 | `patrol.py`（`SitePatrolBundle` · 四腿 VDC） |
| Skill 面 M6 | `skill.py`（`AdopterSkill` · Function Calling） |
| Manifest 校验 M7 | 包外 `novapanda/manifest_validate.py` · CLI `manifest validate` |

## 验收

- `pytest tests/test_adopter_*.py tests/test_manifest_validate_cli.py`
- `python demo/adopter_smoke_all.py`
- `python -m novapanda manifest validate <manifest.json>`
- 看门狗：`python run_local_gatekeeper.py`
