# GitHub 占坑发布指南（NovaPanda）

> **占位策略**：public 仓库 + **`/docs` 极简 Pages** → **https://novapanda.io**  
> **注意**：GitHub 用户名 `novapanda`（@NoVaPanda）已被他人占用，**必须使用组织** `novapanda-protocol`。

---

## 0. DNS（必改 CNAME）

**`novapanda.github.io` 属于别人账号，不能用。** 请把 Namecheap Advanced DNS 里 `www` 的 CNAME 改为：

| Type | Host | Value |
|------|------|--------|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| **CNAME** | **`www`** | **`novapanda-protocol.github.io`** |

**novapanda.io → Domain → Redirect**：保持 **空**。

**novapanda.xyz → Redirect**：根域 + `www` → `https://novapanda.io`。

---

## 1. 创建 GitHub 组织与仓库

1. [GitHub](https://github.com) → **New organization** → 名称 **`novapanda-protocol`**
2. **New repository** → 名称 **`novapanda`** → **Public**
3. 不要勾选「Add README」（本地已有代码）

---

## 2. 推送本地仓库

```powershell
cd d:\project\jiazhi

git remote add origin https://github.com/novapanda-protocol/novapanda.git
git branch -M main

git add -A
git status
git commit -m "NovaPanda: open reference impl, docs site, deploy guides"
git push -u origin main
```

若 `origin` 已存在：

```powershell
git remote set-url origin https://github.com/novapanda-protocol/novapanda.git
git push -u origin main
```

---

## 3. 启用 GitHub Pages

1. 仓库 **Settings** → **Pages**
2. Source: **Deploy from a branch** → **`main`** / **`/docs`**
3. **Custom domain**：`novapanda.io` → Save
4. DNS check 变绿后 → **Enforce HTTPS**

仓库内 **`docs/CNAME`** 内容为 `novapanda.io`（自定义域名，与 org 名无关）。

---

## 4. 验证

```text
https://novapanda.io
https://www.novapanda.io
https://novapanda.xyz          → 应跳到 novapanda.io
https://github.com/novapanda-protocol/novapanda
```

---

## 5. 公开表述

- **NovaPanda 中国商标已提交**（受理后写申请号）；核准前 **勿用 ®**
- 见 [`conformance/PRE_PUBLISH_CHECKLIST.md`](conformance/PRE_PUBLISH_CHECKLIST.md)

---

## 6. 下一步

- [ ] 改 Namecheap CNAME → `novapanda-protocol.github.io`
- [ ] 创建组织并 push
- [ ] 境外 mock 节点 → `node.novapanda.io`
- [ ] 商标缴费 / 受理通知书
