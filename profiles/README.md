# Profiles · 能力档目录

实现通过 Manifest `profiles` 数组宣告已支持的档。兼容性以档 + [conformance](../conformance/) 为准，不以单一代码库为准。

| ID | 文档 | 意图 |
|----|------|------|
| **NP-MIN** | [NP-MIN.md](NP-MIN.md) | 最小可互通交割（Litmus） |
| **NP-NODE** | [NP-NODE.md](NP-NODE.md) | 可运营参考节点 |
| **NP-BUNDLE** | [NP-BUNDLE.md](NP-BUNDLE.md) | 组合编排（多 VDC） |
| **NP-CLAIM-XFER** | [NP-CLAIM-XFER.md](NP-CLAIM-XFER.md) | 结算权柄转让（默认关） |
| **NP-PHYS** | [NP-PHYS.md](NP-PHYS.md) | 物理证据交割 |
| **NP-SETTLE** | [NP-SETTLE.md](NP-SETTLE.md) | 结算旁路适配（国际多轨协商） |
| **NP-DELEGATE** | [NP-DELEGATE.md](NP-DELEGATE.md) | 临时委托 + 支付约束域（限价/周期/轨白名单；非资金账户） |
| **NP-PRIV** | [NP-PRIV.md](NP-PRIV.md) | 隐私姿态（hash_only·地理分级·跨境/留存标签；非合规证书） |
| **NP-LITE** | [NP-LITE.md](NP-LITE.md) | 弱网/边缘姿态（**勿撕 C1**；lite/edge/full 叙述映射） |

规划中：`NP-REP` · `NP-WITNESS`。

结算旁路现行：[`NP-SETTLE.md`](NP-SETTLE.md)（钩子层；显式禁止二清资金池）。  
Claim mock vs 生产边界：内部 `T03a-Claim-mock边界.md`。  
取舍档案：内部 `标准建议-结算二清隔离-评议与吸收.md` 等。

宣告示例：

```json
"profiles": ["NP-MIN", "NP-NODE"]
```

未见宣告的行为，对端 MUST NOT 假设可用。
