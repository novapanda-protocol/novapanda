# 零号节点品牌静态资源

运行时由 `novapanda/node/app.py` 挂载为 `/static/brand/*`。

**真源（文档站）**：仓库根 `docs/figures/brand/`。更新图后请同步复制：

```powershell
Copy-Item docs\figures\brand\*.png novapanda\node\static\brand\ -Force
```

或使用 `python scripts/update_brand_titles.py`（若已配置同步）。
