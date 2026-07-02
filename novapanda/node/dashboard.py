"""节点只读控制台 + 简易运维页（HTML）。"""

from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any


def _short(text: str, n: int = 28) -> str:
    return text if len(text) <= n else text[:n] + "…"


def collect_status(*, engine, app_state) -> dict[str, Any]:
    exchanges = list(engine._store.values())
    by_state = Counter(ex.state for ex in exchanges)
    recent = sorted(exchanges, key=lambda ex: ex.updated_at, reverse=True)[:15]
    settlement_cls = type(engine._settlement).__name__
    settlement = settlement_cls.replace("Settlement", "").lower() or "unknown"
    return {
        "service": "novapanda-node",
        "protocol": "novapanda",
        "version": "0.0.1",
        "node_id": app_state.node_id,
        "settlement": settlement,
        "auth_enabled": bool(app_state.auth_enabled),
        "exchange_total": len(exchanges),
        "by_state": dict(sorted(by_state.items())),
        "recent": [
            {
                "exchange_id": ex.exchange_id,
                "state": ex.state,
                "client": ex.client,
                "provider": ex.provider,
                "resource_type": ex.resource_type,
                "updated_at": ex.updated_at,
            }
            for ex in recent
        ],
    }


def render_dashboard(status: dict[str, Any], *, admin: bool = False) -> str:
    states = status.get("by_state") or {}
    state_chips = "".join(
        f'<span class="chip"><b>{escape(k)}</b> {v}</span>'
        for k, v in sorted(states.items(), key=lambda kv: -kv[1])
    ) or '<span class="muted">暂无交换记录</span>'

    rows = ""
    for ex in status.get("recent") or []:
        rows += (
            "<tr>"
            f"<td><code>{escape(ex['exchange_id'])}</code></td>"
            f"<td><span class=\"state {escape(ex['state'])}\">{escape(ex['state'])}</span></td>"
            f"<td class=\"mono small\" title=\"{escape(ex['client'])}\">{escape(_short(ex['client']))}</td>"
            f"<td class=\"mono small\" title=\"{escape(ex['provider'])}\">{escape(_short(ex['provider']))}</td>"
            f"<td>{escape(ex['resource_type'])}</td>"
            f"<td class=\"muted\">{escape(ex['updated_at'])}</td>"
            "</tr>"
        )
    if not rows:
        rows = '<tr><td colspan="6" class="muted">尚无交换；可用 <a href="https://novapanda.io/trial.html">Trial</a> 脚本创建</td></tr>'

    admin_block = ""
    if admin:
        admin_block = """
    <section class="card" id="admin">
      <h2>运维操作</h2>
      <p class="muted">输入 <code>NOVAPANDA_ADMIN_TOKEN</code>（仅存于本机浏览器，不会写入 URL）。</p>
      <label class="field">Admin Token
        <input type="password" id="admin-token" placeholder="production.env 中的 token" autocomplete="off">
      </label>
      <div class="actions">
        <button type="button" id="sweep-btn">立即 Sweep（超时清扫）</button>
        <span id="sweep-result" class="muted"></span>
      </div>
    </section>
    <script>
    (function () {
      const key = 'novapanda_admin_token';
      const input = document.getElementById('admin-token');
      const saved = sessionStorage.getItem(key);
      if (saved) input.value = saved;
      input.addEventListener('change', () => sessionStorage.setItem(key, input.value));
      document.getElementById('sweep-btn').addEventListener('click', async () => {
        const token = input.value.trim();
        const out = document.getElementById('sweep-result');
        if (!token) { out.textContent = '请先填写 token'; return; }
        sessionStorage.setItem(key, token);
        out.textContent = '执行中…';
        try {
          const r = await fetch('/admin/sweep', {
            method: 'POST',
            headers: { 'X-Admin-Token': token, 'Content-Type': 'application/json' }
          });
          const body = await r.json().catch(() => ({}));
          if (!r.ok) throw new Error(body.msg || body.detail || r.status);
          const n = (body.expired || []).length;
          out.textContent = '完成：过期清扫 ' + n + ' 笔';
        } catch (e) {
          out.textContent = '失败：' + e.message;
        }
      });
    })();
    </script>
"""

    title = "NovaPanda 节点控制台" if admin else "NovaPanda 节点"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3d9cf5;
      --ok: #3ecf8e;
      --border: #2a3544;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
      background: linear-gradient(160deg, #0b1020 0%, #121a28 40%, #0f1419 100%);
      color: var(--text); line-height: 1.5; min-height: 100vh;
    }}
    .wrap {{ max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
    header {{ display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; margin-bottom: 1.5rem; }}
    h1 {{ font-size: 1.35rem; margin: 0; font-weight: 600; }}
    .badge {{
      display: inline-flex; align-items: center; gap: .4rem;
      background: rgba(62, 207, 142, .15); color: var(--ok);
      border: 1px solid rgba(62, 207, 142, .35); border-radius: 999px;
      padding: .25rem .75rem; font-size: .85rem;
    }}
    .badge::before {{ content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--ok); }}
    nav {{ margin-left: auto; font-size: .9rem; }}
    nav a {{ color: var(--accent); text-decoration: none; margin-left: 1rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1rem; }}
    .card {{
      background: var(--card); border: 1px solid var(--border);
      border-radius: 12px; padding: 1rem 1.1rem;
    }}
    .card h2 {{ font-size: .95rem; margin: 0 0 .75rem; color: var(--muted); font-weight: 500; }}
    .stat {{ font-size: 1.75rem; font-weight: 700; }}
    .muted {{ color: var(--muted); font-size: .9rem; }}
    .mono {{ font-family: ui-monospace, monospace; }}
    .small {{ font-size: .78rem; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
    .chip {{
      background: #243044; border-radius: 8px; padding: .35rem .6rem; font-size: .82rem;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
    th, td {{ text-align: left; padding: .55rem .4rem; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); font-weight: 500; }}
    .state {{ border-radius: 6px; padding: .15rem .45rem; font-size: .75rem; font-weight: 600; }}
    .state.SETTLED {{ background: rgba(62,207,142,.2); color: var(--ok); }}
    .state.PROPOSED, .state.CONTRACTED, .state.ESCROWED {{ background: rgba(61,156,245,.15); color: var(--accent); }}
    .state.EXPIRED_REFUNDED, .state.REJECTED {{ background: rgba(255,120,120,.12); color: #ff9a9a; }}
    .field {{ display: block; margin: .75rem 0; }}
    .field input {{
      display: block; width: 100%; max-width: 420px; margin-top: .35rem;
      padding: .5rem .65rem; border-radius: 8px; border: 1px solid var(--border);
      background: #0f1419; color: var(--text);
    }}
    button {{
      background: var(--accent); color: #fff; border: none; border-radius: 8px;
      padding: .55rem 1rem; font-size: .9rem; cursor: pointer;
    }}
    button:hover {{ filter: brightness(1.08); }}
    .actions {{ display: flex; flex-wrap: wrap; align-items: center; gap: .75rem; margin-top: .5rem; }}
    footer {{ margin-top: 2rem; font-size: .8rem; color: var(--muted); }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>{title}</h1>
      <span class="badge">运行中 · mock 试用</span>
      <nav>
        <a href="/">概览</a>
        <a href="/admin">运维</a>
        <a href="/docs">API 文档</a>
        <a href="https://novapanda.io">官网</a>
      </nav>
    </header>

    <div class="grid">
      <div class="card">
        <h2>交换总数</h2>
        <div class="stat">{status['exchange_total']}</div>
      </div>
      <div class="card">
        <h2>结算模式</h2>
        <div class="stat" style="font-size:1.2rem">{escape(status['settlement'])}</div>
        <div class="muted">无真实资金</div>
      </div>
      <div class="card">
        <h2>鉴权</h2>
        <div class="stat" style="font-size:1.2rem">{'ON' if status['auth_enabled'] else 'OFF'}</div>
      </div>
      <div class="card">
        <h2>协议</h2>
        <div class="mono small">{escape(status['protocol'])} v{escape(status['version'])}</div>
        <div class="mono small muted" style="margin-top:.35rem" title="{escape(status['node_id'])}">{escape(_short(status['node_id'], 44))}</div>
      </div>
    </div>

    <section class="card" style="margin-bottom:1rem">
      <h2>按状态分布</h2>
      <div class="chips">{state_chips}</div>
    </section>

    <section class="card" style="margin-bottom:1rem">
      <h2>最近交换</h2>
      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th>ID</th><th>状态</th><th>Client</th><th>Provider</th><th>资源</th><th>更新</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>

    {admin_block}

    <footer>
      北京青合数智科技有限公司 · 公开 mock 节点 ·
      <a href="https://novapanda.io/trial.html" style="color:var(--accent)">开发者 Quickstart</a> ·
      非银行/支付机构，不托管资金
    </footer>
  </div>
</body>
</html>"""
