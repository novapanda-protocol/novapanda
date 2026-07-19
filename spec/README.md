# NovaPanda 规范 · 卷索引

> **协议**：NovaPanda v0 · CC BY 4.0  
> **拆分**：T16 · 2026-07-09（Additive；条款 ID 不变）

---

## 分卷

| 卷 | 文件 | 读者 |
|----|------|------|
| **CORE** | [CORE.md](CORE.md) | 身份、VDC、状态机、验收、一致性原则 |
| **NP-HTTP** | [NP-HTTP.md](NP-HTTP.md) | HTTP 鉴权、授权矩阵、错误码 |
| **NP-OPS** | [NP-OPS.md](NP-OPS.md) | 超时、sweep、recover、Manifest |
| **NP-V2** | [NP-V2.md](NP-V2.md) | Witness、联邦、LLM、物理扩展（特性开关） |

**绑定卷（BINDING · 翻译层，非 CORE）**：

| 卷 | 文件 | 说明 |
|----|------|------|
| **BINDING-MCP** | [BINDING-MCP.md](BINDING-MCP.md) | MCP 工具映射与红线 |
| **BINDING-A2A** | [BINDING-A2A.md](BINDING-A2A.md) | A2A agent_card / action 映射 |
| **BINDING-SKILL** | [BINDING-SKILL.md](BINDING-SKILL.md) | Skill action 映射 |
| **BINDING-OPENCLAW** | [BINDING-OPENCLAW.md](BINDING-OPENCLAW.md) | OpenClaw / 车结对（pair_cli + Skill 壳） |

**合并入口（兼容）**：[SPEC.md](SPEC.md)  
**Profile**：[`../profiles/`](../profiles/README.md)  
**向量**：[../conformance/VECTORS.md](../conformance/VECTORS.md)  
**JSON Schema**：[`schemas/README.md`](schemas/README.md)（VDC · Bundle · Claim · Pod 扩展等）  
**JSON Schema**：[`schemas/README.md`](schemas/README.md)（VDC · Bundle · Claim · Pod 扩展 · v0.1）

---

## 路径建议

| 角色 | 必读 |
|------|------|
| 最小互通 | CORE + NP-MIN |
| 参考节点 | CORE + NP-HTTP + NP-OPS + NP-NODE |
| 结算伙伴 | CORE + NP-SETTLE + NP-HTTP（escrow 段） |

---

*spec/README.md · T16*
