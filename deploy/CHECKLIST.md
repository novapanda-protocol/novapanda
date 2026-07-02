# 参考节点上线检查清单

## A. 部署前

- [ ] 云账号（AWS / 阿里云国际）与公司主体一致或已授权
- [ ] 域名 + HTTPS 证书（Let's Encrypt 或云证书）
- [ ] `TROODON_AUTH=1`
- [ ] `TROODON_ADMIN_TOKEN` 强随机，仅 cron/运维持有
- [ ] `TROODON_DB` 指向 **持久卷**（非容器 ephemeral）
- [ ] 阶段 1：`TROODON_SETTLEMENT=mock`
- [ ] 备份策略（SQLite 文件 snapshot / 卷快照）
- [ ] 监控：`GET /health`、5xx 告警、磁盘用量
- [ ] 限流（反向代理或 WAF）
- [ ] 用户协议 + 隐私政策 URL（可链到 GitHub Pages）

## B. 部署后（mock）

- [ ] 运行冒烟脚本（见 [`MOCK_STABILITY.md`](MOCK_STABILITY.md)）：
  ```bash
  export TROODON_NODE_URL=https://<domain>
  export TROODON_ADMIN_TOKEN=...
  export RUN_TS_LIFECYCLE=1
  ./deploy/scripts/smoke.sh
  ```
- [ ] `curl https://<domain>/health` → `{"status":"ok"}`
- [ ] cron 已配置 [`cron/sweep.sh`](cron/sweep.sh)
- [ ] 重启后 `engine.recover()` 无 pending 泄漏（测一次 kill 进程）
- [ ] manifest / exchange 端点可从外网访问

## C. 切换 x402 sandbox 前

- [ ] 伙伴 sandbox 账号 + API Key
- [ ] 复制 [`env/x402-sandbox.env.example`](env/x402-sandbox.env.example) 并填入 URL/Key
- [ ] **独立 DB** 或新环境，不与 mock 混用
- [ ] 跑通一笔完整 exchange + 超时 void 退款
- [ ] 更新对外文档：当前 rail = x402 sandbox，非生产法币
- [ ] 伙伴 ToS 允许的使用场景已确认

## D. 不建议上线时开启（首版）

- [ ] `TROODON_WITNESS_V2=1`（复杂度高）
- [ ] `TROODON_FEDERATION_V2=1`（多节点再开）
- [ ] 无 `TROODON_ADMIN_TOKEN` 的 `/admin/sweep` 暴露公网
