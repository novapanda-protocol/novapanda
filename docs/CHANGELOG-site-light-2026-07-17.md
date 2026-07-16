# 官网 Light Mode 重构 + 零号试用台 · 修改记录（2026-07-17）

## 摘要

官网（`docs/`）重构为明亮叙事站；愿景 / 场景切面分离；零号控制台 Light Mode IA 同步进仓。  
漏斗：**官网看图懂故事 → Quickstart → 零号动手试**。

---

## 一、官网（novapanda.io / `docs/`）

### 视觉与信息架构
- Light Mode token：`#F8FAFC` / `#0F172A` / `#E2E8F0` / `#0EA5E9` / `#10B981` / 宪法绯红 `#E11D48`
- 统一顶栏：`协议愿景 | 应用场景 | 生态架构 | 协议宪法 | Quickstart` + 黑钮零号试用台
- 首页：Hero + 品牌海报 + 痛点/解法 + 三支柱 + Cursor Rule / Codex / MCP Skill
- `trial.html` → RFC 式 Quickstart（边界卡 + Phase 1/2/3）
- 宪法页：Design Commitments · Litmus · 五条技术底线（去大蓝渐变）
- 主标题去句号；标题 `word-break: keep-all` / CTA `nowrap`，避免单字落行

### 话术（写入愿景及相关页）
- 「一切智能体与智能 IoT，无需人参与也能自主交割」
- 「人制定规则与终审 · 交换过程可由机器对机器完成」
- 落点：`vision` / `index` / `constitution` / `one-pager` / `why` / `scenarios/README`

### 图与场景切面
| 页 | 图 | 切面 |
|----|-----|------|
| **愿景** | `figures/brand/novapanda-intelligent-everything-exchange-zh.{webp,jpg}` | 智能万物交换（谁在交换 · 无人值守） |
| **场景** | `scenarios/figures/novapanda-exchange-layers-settlement-zh.{webp,jpg}` | **交割怎么叠 · 钱在哪一层**（单笔 / 叠加 / 清算可插拔） |

绘图 brief（给人/智能体重画用）：
- `scenarios/figures/_scenario-hero-redraw.md`
- `scenarios/figures/_scenario-layers-redraw.md`

生态页：改为「4 核心角色 + 4 基础支撑」，告别晦涩「八域」堆砌。

---

## 二、零号试用台（`novapanda/node/`）

- IA v2：首页试用台主路径；运营注册仅控制台内
- Light Mode UI（`console_render.py` 等）与相关测试更新
- 与官网分工：调试输入 / 交换表留在零号，不进官网

涉及文件（摘要）：`app.py` · `console_render.py` · `dashboard.py` · `operators.py` · `tests/test_*console*` · `test_zero_node_portal.py` 等

---

## 三、刻意未做 / 后续

- 官网 GitHub Pages / novapanda.io 需随 `main` 或 Pages 工作流发布后才在公网可见（本地 `http://127.0.0.1:5500` 已可验）
- 零号：`deploy/scripts/update-node.sh`（EC2 上 `git pull` + docker compose）
- `_originals/` 大图源文件入库作存档；网页用 webp/jpg

---

## 四、发布状态（2026-07-17）

| 项 | 状态 |
|----|------|
| 本地 commit | ✅ `cb2387d` · `e869b64` · `bc83a57` |
| `git push origin main` | ✅ |
| 零号 EC2 升级 | ✅ 用户确认 · 外网 Light 试用台 |
| 官网 novapanda.io | ✅ 外网已见新 IA |
| 官网是否拆出公开仓 | ⏸ 下次再定（现状：`docs/` 已在公开仓） |

### 网络恢复后：推送

```bash
git push origin main
```

### Instance Connect：零号升级（push 成功后）

```bash
sudo bash /opt/novapanda/src/deploy/scripts/update-node.sh
```

或：

```bash
sudo git -C /opt/novapanda/src fetch origin main
sudo git -C /opt/novapanda/src reset --hard origin/main
cd /opt/novapanda/src/deploy/docker
sudo docker compose --env-file ../env/production.env build
sudo docker compose --env-file ../env/production.env up -d
sleep 8
curl -fsS https://node.novapanda.io/health
git -C /opt/novapanda/src log -1 --oneline   # 期望 cb2387d 或更新
```

### 验收清单

- [ ] 本地：`docs/index.html` · `vision.html` · `scenarios/overview.html` · `trial.html`
- [ ] `git push` 成功，`origin/main` 含 `cb2387d`
- [ ] 零号：`health` 200；首页为 Light 试用台（非深色旧壳）
- [ ] 官网生产：同步 `docs/` 后顶栏与新图生效
