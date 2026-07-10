# NovaPanda NP-V2+ · 扩展与特性开关

> **卷**：NP-V2 · **experimental** 直至特性开关默认开启  
> 默认 `NOVAPANDA_WITNESS_V2=0` / `FEDERATION_V2=0` → 相关写端点 501

---

## 14. Witness + Stake

Schema：`witness-attestation.schema.json`、`stake-lock.schema.json`  
路径：`/v2/witness/*`、`/v2/stake/*`、`/exchanges/{id}/v2/witness/attach`

## 15–16. 持久化与联邦

- SQLite：`vdcs`、`stakes` 表。  
- `/reputation/export`、`/v2/reputation/import`、`/exchanges/{id}/export`

## 17. v1 扩展

- LLM verifier、`/v1/did/*`、`/v1/cbor/canonical`、TS SDK

## 18. 物理 v3 + ISO 15118

- `/v3/physical/validate`、`/v3/iso15118/*`

## 19. 信誉聚合与环境变量

- `POST /v2/reputation/aggregate`  
- 完整 env 列表：`novapanda/config.py`

---

*NP-V2.md · T16 · experimental*
