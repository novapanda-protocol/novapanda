# NovaPanda 当前主线（节点已上线后）

> 状态基线：`node.novapanda.io` mock 节点已启动并可访问 `/health`。

## P0（当天完成）

- [x] 节点上线：`novapanda-node` + `novapanda-caddy`
- [x] `node.novapanda.io` 指向节点公网 IP
- [ ] 记录并妥善保存 `TROODON_ADMIN_TOKEN`
- [ ] 在服务器执行一次 smoke（见 `deploy/scripts/smoke.sh`）

## P1（发布就绪）

- [ ] 创建 GitHub 组织：`novapanda-protocol`
- [ ] 创建仓库：`novapanda`
- [ ] push 本地代码到 `novapanda-protocol/novapanda`
- [ ] 开启 Pages：`main` + `/docs`
- [ ] 绑定 `novapanda.io`，开启 HTTPS

## P2（稳定运行）

- [ ] 给实例绑定 Elastic IP（避免重启换 IP）
- [ ] 每 5 分钟执行 `/admin/sweep`（见 `deploy/cron/sweep.sh`）
- [ ] 每日快照备份 `/data` 或宿主卷
- [ ] 安全组 22 仅保留固定 IP（或关闭）

## 30 秒验收命令

```bash
curl -fsS https://node.novapanda.io/health
curl -fsS https://node.novapanda.io/.well-known/troodon.json || true
```

