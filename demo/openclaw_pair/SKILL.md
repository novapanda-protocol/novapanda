# NovaPanda Pair（车 ↔ OpenClaw）

把 NovaPanda 可验证交割接到本机 Agent。你只编排；**签名与 SETTLED 由本地 CLI 完成**，私钥不进对话。

## When to use

- 用户要「和车做一笔可验证交割 / 跑 NovaPanda / SETTLED / 出 VDC」
- 用户要查 vault、导出仲裁摘要、确认一笔交换

## Setup（安装时改路径）

将下面 `NP_ROOT` / `PAIR_ROOT` / `PYTHON` 换成你机器上的真实路径。

```text
NP_ROOT   = D:/project/jiazhi
PAIR_ROOT = D:/project/jiazhi/demo/out/openclaw_pair
PYTHON    = python
BASE_URL  = http://127.0.0.1:8765
```

节点需已启动（或同机先起 uvicorn）。结算为 **mock**。

## Tools（shell）

### 1) 同机一键交割（推荐演示）

```bash
cd $NP_ROOT
$PYTHON demo/openclaw_pair/pair_cli.py run --root $PAIR_ROOT --base-url $BASE_URL
```

成功：JSON 含 `"ok": true`, `"state": "SETTLED"`。向用户回报 `exchange_id` / `vdc_id`，**不要**粘贴 `identity.hex`。

### 2) 调用 Adopter 产品面工具

```bash
$PYTHON demo/openclaw_pair/pair_cli.py skill --role claw --root $PAIR_ROOT --base-url $BASE_URL \
  --name adopter_vault_stats --args "{}"
```

常用 `--name`：

- `adopter_list_tools`
- `adopter_vault_stats`
- `adopter_export_pack` · args `{"exchange_id":"…"}`
- `adopter_apply_intent` · args `{"exchange_id":"…","text":"确认"}`（车侧确认请用 `--role car`）

### 3) 车侧确认

```bash
$PYTHON demo/openclaw_pair/pair_cli.py car-confirm --root $PAIR_ROOT --base-url $BASE_URL \
  --exchange-id <id> --text 确认
```

### 4) 身份自检

```bash
$PYTHON demo/openclaw_pair/pair_cli.py whoami --role claw --root $PAIR_ROOT --base-url $BASE_URL
```

## Rules

1. NEVER read or print `identity.hex` / private keys into chat.  
2. NEVER claim SETTLED unless CLI JSON says `"state": "SETTLED"` and `"ok": true`.  
3. Always say settlement is **mock** unless user configured a licensed rail.  
4. Text summaries from `adopter_export_pack` are not proof — point user to `reverify` JSON.
