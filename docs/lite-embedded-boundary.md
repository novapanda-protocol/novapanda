# NP-LITE · 嵌入 / 边缘边界（informative）

> **用途**：写死「什么能烧进无人机/机器人边缘芯片，什么必须留在伴侣机或零号节点身体」。  
> **规范真源**：[`profiles/NP-LITE.md`](../profiles/NP-LITE.md) · [`CHARTER.md`](../CHARTER.md)  
> **参考实现**：`novapanda.adopter.Outbox` · TS/Python 签验与 CBOR · **非**完整 `uvicorn` 节点  
> **状态**：v0.1 · 2026-07-19 · 不升格为新 Profile 名（避免平行方言）

---

## 1. 一句话

边缘只做 **持钥 · 签验 · 瘦编码 · 离线队列**；  
**交换状态机与 SETTLED 真值**仍在 NP-MIN / CORE，不另造「设备态状态机」。

---

## 2. 三层部署（MUST 心里清楚）

```text
┌─────────────────────────────────────────────────────────────┐
│ A · Embedded / MCU / Flight-compute（极小面）                 │
│    Ed25519 签验 · CBOR/JSON 编解码 · 本地 Outbox · 密钥仓     │
│    MAY：缓存未完成的 propose/deliver/confirm 意图             │
│    MUST NOT：宣称 SETTLED、跑完整 HTTP 节点、改 TRANSITIONS     │
└───────────────────────────┬─────────────────────────────────┘
                            │ BLE / UWB / LAN / 恢复后回传
┌───────────────────────────▼─────────────────────────────────┐
│ B · Companion / 车机 / 树莓派「身体」（Adopter Runtime）        │
│    DraftStore · VdcVault · IntentMap · flush Outbox           │
│    对端发现 · 调 Exchange（本机库或远端 HTTP）                 │
└───────────────────────────┬─────────────────────────────────┘
                            │ 可选
┌───────────────────────────▼─────────────────────────────────┐
│ C · Node body（零号节点 / 自建节点）                          │
│    NP-HTTP · 验收 · 信誉 · 结算 adapter（mock/sandbox/…）     │
│    可离线；仲裁靠导出 VDC + reverify，不靠节点永生             │
└─────────────────────────────────────────────────────────────┘
```

| 层 | 典型硬件 | 跑什么 | 不跑什么 |
|----|----------|--------|----------|
| **A** | 飞控旁路 MCU、机器人边缘 SoC | 签验 + CBOR + Outbox 落盘 | uvicorn / 市场 / LLM judge |
| **B** | 车机、树莓派、工控机 | `AdopterRuntime` 竖切 | 协议代币钱包当真源 |
| **C** | 服务器 / 零号节点 | 可选身体 | 「没有我就无法 reverify」 |

---

## 3. 嵌入面允许清单（Allow）

| 能力 | 约定 | 仓库锚点 |
|------|------|----------|
| Ed25519 签 / 验 | 与 C1 同一算法；禁截断签 | Python `identity` · TS `sign`/`reverify` |
| Canonical / CBOR | 语义可映射回 JSON 向量 | C1 · C-LITE-RT · `provider_payload_encoding` |
| 双签 VDC 字段子集 | 瘦报文 ↔ 标准形 round-trip | `tests/test_c_lite_rt.py` |
| Outbox | 断网排队；恢复幂等重放 | `adopter/outbox.py` · NP-LITE-03 |
| Manifest `lite` | `tier` · `canonical: novapanda-c1` · `offline_queue` | `np manifest validate` |
| 物理计量摘要 | 进 deliverable / evidence，不进 CORE id | NP-PHYS · `adopter/charge.py` |

---

## 4. 禁止清单（Deny）— 撕这里 = 撕 Litmus

1. **禁止**「太慢就跳过验签 / 先 SETTLED 再补签」。  
2. **禁止**用 `idle/busy/charging/fault` 等设备态**替换** Exchange `state`。  
3. **禁止**平行 `Record` / pending→confirmed API（见 [`record-vs-vdc.md`](record-vs-vdc.md)）。  
4. **禁止**在 MCU 上默认部署完整 `uvicorn` 零号节点当「嵌入 Profile」。  
5. **禁止** LITE 专用弱哈希、私有压缩且不可逆映射到公开向量。  
6. **禁止**把 mock 结算写成持牌清算；Outbox 延迟 ≠ 已清算。  
7. **禁止**把 ROS2 / 飞控 Topic 命名直接当成协议状态枚举（适配器可映射，语义真源仍在 CORE）。

---

## 5. 断网语义（对照 NP-LITE-02/03）

| 阶段 | 嵌入侧可以 | 嵌入侧不可以 |
|------|------------|--------------|
| 物理动作进行中（充电/抓取） | 本地会话 + 计量缓冲 | 因无网中止物理控制（控制环 ≠ Exchange） |
| 待 confirm / deliver | Outbox 入队 | 对外宣称 SETTLED |
| 网络恢复 | `flush` + 原 `idempotency_key` / nonce | 换新键重放造成双花意图 |
| 仲裁 | 导出已持有的 VDC JSON | 要求原边缘节点在线 |

自检：`AdopterRuntime.check_lite_alignment()` · `python -m novapanda manifest validate … --require-profiles`。

---

## 6. 与「第二实现」的关系

- **第二节点**：异语言实现 A+B 或 C，跑 SI-01…05 → [`compatibility.md`](compatibility.md)。  
- **嵌入库**：可以只实现 A 面 + 对 B/C 的 RPC；登记时写明 `lite.tier` 与 `settlement: mock|…`。  
- 征集入口：[`../conformance/CALL_FOR_SECOND_IMPL.md`](../conformance/CALL_FOR_SECOND_IMPL.md)。

机器可读勾选：[`../conformance/lite_embedded_checklist.json`](../conformance/lite_embedded_checklist.json)。

---

车 + OpenClaw 软件/半真机清单：[`openclaw-adopter-checklist.md`](openclaw-adopter-checklist.md)。

## 7. 实物演示分镜（无人机 / 机器人 · 待拍）

创新硬件圈要的是**眼见为实**；软件竖切已有 `demo/adopter_av_charge.py`。下列为建议 60–90s 分镜，**不要求**本仓库含真机固件。

| 镜号 | 画面 | 协议落点 |
|------|------|----------|
| 1 | 两台设备亮密钥/Agent Id（或 Manifest QR） | 本地持钥 · 陌生对端 |
| 2 | 无人机/小车接近第三方桩/补给站 | propose / contract（LAN） |
| 3 | 充电/补给进行；仪表或串口显示电流脉冲 | deliverable 计量 · NP-PHYS |
| 4 | 屏幕/串口打印 VDC id + `SETTLED`（或 Outbox「queued confirm」） | 双签；断网则明示 queued≠SETTLED |
| 5 | 拔网线或飞行模式；本地仍持 VDC JSON | Outbox / vault |
| 6 | 恢复网络或拷贝 JSON 到笔记本 → `reverify` / `npm run attest:l0` | 离线复验 · 不依赖原桩 |

口播红线：**不发币、不托管资金**；结算条只说 mock/sandbox/伙伴轨。

验收素材建议：README 或 Trial 页链 1 分钟视频 + 同目录导出的 `settled_vdc.json`。

---

## 8. ROS2 / 飞控（后置，不阻塞）

| 现在 | 以后（有硬件伙伴再开） |
|------|------------------------|
| 控制环继续走 ROS2 / PX4 原状 | `surfaces` 或外部包：Service/Action → Exchange 调用 |
| Topic 只作身体事件 | 适配器翻译为 propose/deliver/confirm，**不**改 CORE 枚举 |

---

## 9. 版本

加性 informative。若未来要把某条升格 MUST，只改 [`NP-LITE.md`](../profiles/NP-LITE.md) 并挂向量，不另起 `NP-EMBEDDED` 拆分 C1。

---

*嵌入边界 · 咬死签验与 Outbox · 勿在 MCU 上假 SETTLED*
