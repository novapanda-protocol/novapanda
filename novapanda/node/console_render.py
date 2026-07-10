"""零号节点控制台 — HTML 渲染（只读、不含密钥）。"""

from __future__ import annotations

import html
import json
from typing import Any, Optional


def _short(text: str, n: int = 28) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _esc(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return html.escape(str(value))


def _json_pretty(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    return f'<pre class="json">{_esc(text)}</pre>'


def _trace_block(detail: dict[str, Any]) -> str:
    ext = detail.get("extensions")
    if not isinstance(ext, dict):
        return ""
    trace = ext.get("trace")
    if not isinstance(trace, dict):
        return ""
    parts: list[str] = []
    corr = trace.get("correlation_id")
    if corr:
        parts.append(f"<dt>correlation_id</dt><dd><code>{_esc(corr)}</code></dd>")
    tp = trace.get("traceparent")
    if tp:
        short = _short(str(tp), 36)
        parts.append(
            f'<dt>traceparent</dt><dd><code title="{_esc(tp)}">{_esc(short)}</code></dd>'
        )
    ts = trace.get("tracestate")
    if ts:
        parts.append(f"<dt>tracestate</dt><dd><code>{_esc(ts)}</code></dd>")
    if not parts:
        return ""
    return f'<h3>Trace</h3><dl class="kv">{"".join(parts)}</dl>'


def _state_chip(state: str, count: Optional[int] = None) -> str:
    label = _esc(state)
    if count is not None:
        label = f"<b>{label}</b> {_esc(count)}"
    safe = _esc(state)
    return f'<span class="chip state-chip state-{safe}">{label}</span>'


def _exchange_table_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return (
            '<tr><td colspan="7" class="muted">尚无交换；可前往'
            ' <a href="https://novapanda.io/trial.html">Trial</a> 脚本创建</td></tr>'
        )
    rows: list[str] = []
    for ex in items:
        eid = _esc(ex.get("exchange_id", ""))
        rows.append(
            "<tr>"
            f'<td><a href="/console/exchanges/{eid}"><code>{eid}</code></a></td>'
            f'<td>{_state_chip(ex.get("state", ""))}</td>'
            f'<td class="mono small" title="{_esc(ex.get("client"))}">'
            f'{_esc(_short(str(ex.get("client", ""))))}</td>'
            f'<td class="mono small" title="{_esc(ex.get("provider"))}">'
            f'{_esc(_short(str(ex.get("provider", ""))))}</td>'
            f'<td>{_esc(ex.get("resource_type", ""))}</td>'
            f'<td>{_esc(ex.get("quantity", ""))}</td>'
            f'<td class="muted">{_esc(ex.get("updated_at", ""))}</td>'
            "</tr>"
        )
    return "".join(rows)


_CSS = """
:root {
  --bg: #0f1419;
  --card: #1a2332;
  --text: #e7ecf3;
  --muted: #8b9cb3;
  --accent: #3d9cf5;
  --ok: #3ecf8e;
  --warn: #ffb347;
  --border: #2a3544;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: "Segoe UI", "PingFang SC", system-ui, sans-serif;
  background: linear-gradient(160deg, #0b1020 0%, #121a28 40%, #0f1419 100%);
  color: var(--text); line-height: 1.55; min-height: 100vh;
}
.wrap { max-width: 980px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
header { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; margin-bottom: 1.25rem; }
h1 { font-size: 1.35rem; margin: 0; font-weight: 600; }
h2 { font-size: .95rem; margin: 0 0 .75rem; color: var(--muted); font-weight: 500; }
h3 { font-size: .88rem; margin: 1rem 0 .5rem; color: var(--muted); font-weight: 500; }
.badge {
  display: inline-flex; align-items: center; gap: .4rem;
  background: rgba(62, 207, 142, .15); color: var(--ok);
  border: 1px solid rgba(62, 207, 142, .35); border-radius: 999px;
  padding: .25rem .75rem; font-size: .85rem;
}
.badge::before {
  content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--ok);
}
.banner-hard {
  background: rgba(255, 179, 71, .1); border: 1px solid rgba(255, 179, 71, .35);
  border-radius: 10px; padding: .75rem 1rem; margin-bottom: 1rem; font-size: .88rem;
}
.banner-hard strong { color: var(--warn); }
.banner-sandbox { border-color: rgba(61, 156, 245, .45); background: rgba(61, 156, 245, .08); }
.banner-live { border-color: rgba(255, 107, 107, .45); background: rgba(255, 107, 107, .08); }
.banner-mock { border-color: rgba(255, 179, 71, .35); }
.banner-dispute { border-color: rgba(255, 107, 107, .5); }
.banner-frail { border-color: rgba(255, 107, 107, .55); }
.banner-claims-risk { font-size: .85rem; margin-bottom: .75rem; }
.claim-mock { color: var(--warn); font-weight: 600; }
textarea.tool, input.tool {
  width: 100%; background: #0d1218; color: var(--text); border: 1px solid var(--border);
  border-radius: 8px; padding: .55rem .7rem; font-family: ui-monospace, monospace; font-size: .82rem;
}
button.tool {
  background: var(--accent); color: #061018; border: 0; border-radius: 8px;
  padding: .45rem .9rem; font-weight: 600; cursor: pointer; margin-right: .5rem; margin-top: .5rem;
}
button.tool.secondary { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
nav.top { margin-left: auto; font-size: .9rem; }
nav.top a { color: var(--accent); text-decoration: none; margin-left: 1rem; }
nav.top a:hover { text-decoration: underline; }
.tab-nav {
  display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: 1rem;
  border-bottom: 1px solid var(--border); padding-bottom: .65rem;
}
.tab-nav a {
  color: var(--muted); text-decoration: none; font-size: .88rem;
  padding: .35rem .75rem; border-radius: 8px;
}
.tab-nav a:hover { color: var(--accent); background: rgba(61, 156, 245, .08); }
.tab-nav a.active { color: var(--accent); background: rgba(61, 156, 245, .15); }
.tab-panel[hidden] { display: none !important; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.1rem; margin-bottom: 1rem;
}
.stat { font-size: 1.65rem; font-weight: 700; }
.muted { color: var(--muted); font-size: .9rem; }
.mono { font-family: ui-monospace, "Cascadia Code", monospace; }
.small { font-size: .78rem; }
.chips { display: flex; flex-wrap: wrap; gap: .5rem; }
.chip {
  background: #243044; border-radius: 8px; padding: .35rem .6rem; font-size: .82rem;
}
.state-chip.state-SETTLED { background: rgba(62,207,142,.2); color: var(--ok); }
.state-chip.state-PROPOSED,
.state-chip.state-CONTRACTED,
.state-chip.state-ESCROWED,
.state-chip.state-DELIVERED,
.state-chip.state-VERIFIED { background: rgba(61,156,245,.15); color: var(--accent); }
.state-chip.state-EXPIRED_REFUNDED,
.state-chip.state-REJECTED,
.state-chip.state-DISPUTED { background: rgba(255,120,120,.12); color: #ff9a9a; }
table { width: 100%; border-collapse: collapse; font-size: .85rem; }
th, td { text-align: left; padding: .55rem .4rem; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--muted); font-weight: 500; }
.table-wrap { overflow-x: auto; }
.op-nav { display: flex; flex-wrap: wrap; gap: .5rem; margin: .75rem 0 1rem; }
.op-nav a {
  color: var(--accent); text-decoration: none; font-size: .88rem;
  padding: .35rem .7rem; border: 1px solid var(--border); border-radius: 8px;
}
.op-nav a:hover { background: rgba(61, 156, 245, .1); }
.json {
  background: #0f1419; border: 1px solid var(--border); border-radius: 8px;
  padding: .75rem 1rem; overflow-x: auto; font-size: .78rem; line-height: 1.45;
  max-height: 28rem; overflow-y: auto;
}
.kv { display: grid; grid-template-columns: 9rem 1fr; gap: .35rem .75rem; font-size: .88rem; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; word-break: break-all; }
.field { display: block; margin: .75rem 0; }
.field input {
  display: block; width: 100%; max-width: 420px; margin-top: .35rem;
  padding: .5rem .65rem; border-radius: 8px; border: 1px solid var(--border);
  background: #0f1419; color: var(--text);
}
button {
  background: var(--accent); color: #fff; border: none; border-radius: 8px;
  padding: .55rem 1rem; font-size: .9rem; cursor: pointer;
}
button:hover { filter: brightness(1.08); }
button.secondary {
  background: transparent; color: var(--accent); border: 1px solid var(--border);
}
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: .75rem; margin-top: .5rem; }
.link-list { list-style: none; padding: 0; margin: 0; }
.link-list li { margin: .45rem 0; }
footer { margin-top: 2rem; font-size: .8rem; color: var(--muted); }
footer a { color: var(--accent); }
.pill-row { display: flex; flex-wrap: wrap; gap: .4rem; }
.pill {
  display: inline-block; background: #243044; border-radius: 999px;
  padding: .2rem .55rem; font-size: .78rem;
}
.brand-block .brand-poster {
  width: 100%; max-width: 720px; border-radius: 10px;
  border: 1px solid var(--border); display: block; margin-top: .5rem;
}
header .tagline { margin: .15rem 0 0; font-size: .88rem; color: var(--muted); }
"""


_TAB_SCRIPT = """
(function () {
  const panels = document.querySelectorAll('.tab-panel');
  const links = document.querySelectorAll('.tab-nav a[data-tab]');
  function activate() {
    const hash = (location.hash || '#overview').slice(1);
    panels.forEach(function (p) { p.hidden = p.id !== 'panel-' + hash; });
    links.forEach(function (a) {
      a.classList.toggle('active', a.getAttribute('data-tab') === hash);
    });
  }
  window.addEventListener('hashchange', activate);
  links.forEach(function (a) {
    a.addEventListener('click', function () {
      location.hash = a.getAttribute('data-tab');
    });
  });
  activate();
})();
"""


def _nav(*, admin: bool = False) -> str:
    if admin:
        return (
            '<nav class="top">'
            '<a href="/">控制台</a>'
            '<a href="/admin">运维</a>'
            '<a href="/docs">API 文档</a>'
            '<a href="https://novapanda.io">官网</a>'
            "</nav>"
        )
    tabs = [
        ("overview", "概览"),
        ("discover", "发现"),
        ("scenarios", "场景"),
        ("verify", "验证"),
        ("exchanges", "交换"),
        ("reputation", "信誉"),
        ("trial", "试用"),
        ("api", "API"),
        ("me", "我的"),
    ]
    links = "".join(
        f'<a href="#{tid}" data-tab="{tid}">{label}</a>' for tid, label in tabs
    )
    top = (
        '<nav class="top">'
        '<a href="/admin">运维</a>'
        '<a href="/docs">API 文档</a>'
        '<a href="https://novapanda.io">官网</a>'
        "</nav>"
    )
    return top + f'<nav class="tab-nav">{links}</nav>'


def _layout(
    title: str,
    body: str,
    *,
    admin: bool = False,
    extra_head: str = "",
    extra_script: str = "",
) -> str:
    script_block = f"<script>{extra_script}</script>" if extra_script else ""
    badge = "运行中 · mock 试用" if not admin else "运维面板"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(title)}</title>
  <style>{_CSS}</style>
  {extra_head}
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>{_esc(title)}</h1>
        {'' if admin else '<p class="tagline">智能世界的开放交割语法 · 零号节点</p>'}
      </div>
      <span class="badge">{_esc(badge)}</span>
      {_nav(admin=admin)}
    </header>
    {body}
    <footer>
      北京青合数智科技有限公司 · NovaPanda 零号节点 ·
      <a href="https://novapanda.io/trial.html">开发者 Quickstart</a> ·
      非银行/支付机构，不托管资金
    </footer>
  </div>
  {script_block}
</body>
</html>"""


def _operator_nav(active: str = "") -> str:
    links = [
        ("dashboard", "/operator/dashboard", "概览"),
        ("agents", "/operator/agents-ui", "绑定 Agent"),
        ("exchanges", "/operator/exchanges", "我的交换"),
        ("claims", "/operator/claims", "权柄 Claims"),
        ("reconcile", "/operator/reconcile", "对账"),
        ("disputes", "/operator/disputes-ui", "争议"),
        ("settings", "/operator/settings", "设置"),
        ("help", "/operator/help", "帮助"),
    ]
    parts = []
    for key, href, label in links:
        cls = ' class="active"' if key == active else ""
        parts.append(f'<a href="{href}"{cls}>{_esc(label)}</a>')
    return f'<nav class="op-nav">{"".join(parts)}</nav>'


def _hard_boundary_banner() -> str:
    return """
<div class="banner-hard">
  <strong>Trial 硬边界</strong>：无计费 · 无授权商城 · 无售前 CRM ·
  兼容靠公开向量，不靠本域名 ·
  Operator 登录<strong>不能</strong>替代 Agent 交割签名
</div>"""


def _settlement_honesty_banner(profile: Optional[dict[str, Any]] = None) -> str:
    """G27 · mock / sandbox / live 诚实条。"""
    caps = (profile or {}).get("capabilities") or {}
    status = (profile or {}).get("status") or {}
    env = (
        caps.get("settlement_environment")
        or status.get("settlement_environment")
        or "mock"
    )
    partner = caps.get("settlement_partner") or status.get("settlement_partner") or "partner"
    if env == "sandbox":
        msg = (
            "<strong>沙箱结算</strong>：伙伴测试环境；勿用于生产账务。"
            " VDC 与交割流程为真。"
        )
        cls = "banner-sandbox"
    elif env in ("live", "production"):
        msg = (
            f"<strong>真钱轨</strong>：资金由 {_esc(partner)} 处理；"
            "协议不保管资金。"
        )
        cls = "banner-live"
    else:
        msg = (
            "<strong>模拟结算</strong>：无真实资金移动；"
            "VDC 与交割流程为真。"
        )
        cls = "banner-mock"
    return f'<div class="banner-hard {cls}">{msg}</div>'


def _claims_risk_bar() -> str:
    return """
<div class="banner-hard banner-claims-risk">
  权柄不是协议代币；跟随你所选支付轨；轨上风险由伙伴与合同承担。
</div>"""


def _dispute_banner(ticket: Optional[dict[str, Any]]) -> str:
    if not ticket:
        return ""
    tid = _esc(ticket.get("ticket_id", ""))
    tier = _esc(ticket.get("tier", "D0"))
    return f"""
<div class="banner-hard banner-dispute">
  <strong>争议工单</strong> <code>{tid}</code> · 档 {tier} ·
  本节点不修改 VDC；请导出证据包协商或升级支持。
</div>"""


def _frail_outage_banner() -> str:
    return """
<div class="banner-hard banner-frail">
  <strong>结算轨暂时不可用</strong>：结算权柄（Claim/余额）可能无法兑现或再花；
  <strong>已签 VDC 仍可独立复验</strong>。NovaPanda 不垫付、不修改 VDC。
</div>"""


def _brand_poster_section(*, compact: bool = False) -> str:
    poster = "/static/brand/novapanda-intelligent-open-delivery-protocol-poster-zh.png"
    overview = "/static/brand/novapanda-intelligent-open-delivery-protocol-overview-zh.png"
    poster_en = "/static/brand/novapanda-intelligent-open-delivery-protocol-poster-en.png"
    if compact:
        return (
            f'<p class="muted"><a href="{poster}" target="_blank" rel="noopener">协议海报</a>'
            f' · <a href="{overview}" target="_blank" rel="noopener">一页概览图</a></p>'
        )
    return f"""
  <section class="card brand-block">
    <h2>NovaPanda 智能开放交割协议</h2>
    <p class="muted" style="margin-top:0">智能世界的开放交割语法 · 先统一交割与互认，再谈货币</p>
    <a href="{poster}" target="_blank" rel="noopener">
      <img class="brand-poster" src="{poster}" alt="NovaPanda 智能开放交割协议" loading="lazy" />
    </a>
    <p class="muted small" style="margin-top:.75rem">
      <a href="{overview}" target="_blank" rel="noopener">一页概览图</a>
      · <a href="https://novapanda.io/drafts/one-pager.html" rel="noopener">宣传一页纸</a>
      · EN: <a href="{poster_en}" target="_blank" rel="noopener">poster</a>
    </p>
  </section>"""


def _panel_overview(profile: dict[str, Any]) -> str:
    status = profile.get("status") or {}
    caps = profile.get("capabilities") or {}
    states = status.get("by_state") or {}
    chips = "".join(_state_chip(k, v) for k, v in sorted(states.items(), key=lambda kv: -kv[1]))
    if not chips:
        chips = '<span class="muted">尚无交换记录</span>'
    success = status.get("success_rate")
    success_txt = f"{success * 100:.1f}%" if isinstance(success, (int, float)) else "—"
    auth_on = bool(caps.get("auth", status.get("auth_enabled")))
    return f"""
<section class="tab-panel" id="panel-overview">
  {_brand_poster_section()}
  {_settlement_honesty_banner(profile)}
  {_hard_boundary_banner()}
  <div class="grid">
    <div class="card">
      <h2>交换总数</h2>
      <div class="stat">{_esc(status.get("exchange_total", 0))}</div>
    </div>
    <div class="card">
      <h2>已结算</h2>
      <div class="stat">{_esc(status.get("settled_total", 0))}</div>
      <div class="muted">成功率 {_esc(success_txt)}</div>
    </div>
    <div class="card">
      <h2>结算模式</h2>
      <div class="stat" style="font-size:1.15rem">{_esc(status.get("settlement", caps.get("settlement", "—")))}</div>
      <div class="muted">无真实资金 · mock 非到账</div>
    </div>
    <div class="card">
      <h2>鉴权</h2>
      <div class="stat" style="font-size:1.15rem">{_esc("ON" if auth_on else "OFF")}</div>
    </div>
    <div class="card">
      <h2>协议</h2>
      <div class="mono small">{_esc(status.get("protocol", "novapanda"))} v{_esc(status.get("version", "0.0.1"))}</div>
      <div class="mono small muted" style="margin-top:.35rem" title="{_esc(status.get("node_id"))}">
        {_esc(_short(str(status.get("node_id", "")), 44))}
      </div>
    </div>
    <div class="card">
      <h2>验证中心</h2>
      <div class="muted"><a href="#verify">打开验证 Tab →</a></div>
      <div class="muted" style="margin-top:.35rem">自检请跑 conformance.run</div>
    </div>
  </div>
  <section class="card">
    <h2>按状态分布</h2>
    <div class="chips">{chips}</div>
  </section>
  <section class="card">
    <h2>能力摘要</h2>
    <div class="pill-row">
      <span class="pill">verifier: {_esc(caps.get("verifier", "—"))}</span>
      <span class="pill">witness_v2: {_esc(caps.get("witness_v2", False))}</span>
      <span class="pill">federation_v2: {_esc(caps.get("federation_v2", False))}</span>
      <span class="pill">reputation_gate: {_esc(caps.get("reputation_gate", False))}</span>
    </div>
  </section>
</section>"""


def _panel_verify(profile: dict[str, Any]) -> str:
    links = (profile.get("links") or {})
    return f"""
<section class="tab-panel" id="panel-verify" hidden>
  {_hard_boundary_banner()}
  <section class="card">
    <h2>标准验证中心</h2>
    <p class="muted">参考样例 · 报文规范化 · Bundle 校验 · Claim mock · 结算模拟（均无真钱）。
      兼容证明见 <a href="/docs">OpenAPI</a> 与仓库
      <code>docs/IMPLEMENTER_GUIDE.md</code> / <code>docs/compatibility.md</code>。</p>
    <ul class="link-list">
      <li><a href="#scenarios">场景 Tab</a> — 开源 catalog</li>
      <li><a href="https://novapanda.io/trial.html">Trial 指南</a></li>
      <li>本地：<code>python demo/nested_diligence.py</code> · <code>python -m conformance.run</code></li>
    </ul>
  </section>
  <section class="card">
    <h2>规范化 / 哈希调试</h2>
    <p class="muted">粘贴 JSON；<strong>勿粘贴私钥</strong>。</p>
    <textarea class="tool" id="canon-input" rows="5">{{"b":1,"a":2}}</textarea>
    <button type="button" class="tool" id="canon-btn">计算 canonical + SHA-256</button>
    <pre class="json" id="canon-out">—</pre>
  </section>
  <section class="card">
    <h2>Composer · Bundle 校验（库优先）</h2>
    <p class="muted">节点不代跑编排；仅校验 Bundle 文档字段（NP-BUNDLE）。</p>
    <textarea class="tool" id="bundle-input" rows="6">{{
  "bundle_version": "0.1",
  "goal_id": "demo",
  "correlation_id": "corr-1",
  "exchange_ids": ["ex-a", "ex-b"],
  "success_rule": "all_settled",
  "depends_on": {{"ex-b": ["ex-a"]}}
}}</textarea>
    <button type="button" class="tool" id="bundle-btn">校验 Bundle</button>
    <pre class="json" id="bundle-out">—</pre>
  </section>
  <section class="card">
    <h2>Claim mock（非生产转让）</h2>
    <p class="muted">须有 <code>vdc_id</code> 锚；Manifest 语义上非正式 NP-CLAIM-XFER。</p>
    <input class="tool" id="claim-vdc" placeholder="vdc_id" />
    <input class="tool" id="claim-amount" placeholder="amount" value="10" style="margin-top:.4rem" />
    <button type="button" class="tool" id="claim-issue-btn">发行 mock claim</button>
    <button type="button" class="tool secondary" id="claim-list-btn">列出</button>
    <pre class="json" id="claim-out">—</pre>
  </section>
  <section class="card">
    <h2>结算模拟器（mock rail）</h2>
    <p class="muted">escrow→settle 幂等演示；<strong>不是</strong>银行到账。</p>
    <button type="button" class="tool" id="settle-sim-btn">跑一遍模拟</button>
    <pre class="json" id="settle-out">—</pre>
  </section>
  <section class="card">
    <h2>本机自检说明</h2>
    <p class="muted">完整 C1–C8 请在开发机运行 <code>python -m conformance.run</code>。
      本页不把域名当作兼容真源。自检徽章为说明占位。</p>
    <div class="pill-row">
      <span class="pill">C1–C8 · 见 VECTORS</span>
      <span class="pill">NP-DELEGATE · NP-PRIV · NP-LITE</span>
      <span class="pill">Claim=mock only</span>
      <span class="pill">结算={_esc((profile.get("status") or {}).get("settlement", "mock"))}</span>
    </div>
  </section>
</section>
<script>
(function(){{
  async function jpost(url, body){{
    const r = await fetch(url, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(body)}});
    return {{ok:r.ok, status:r.status, body: await r.json().catch(()=>({{}}))}};
  }}
  const ce = document.getElementById('canon-btn');
  if(!ce) return;
  ce.onclick = async ()=>{{
    let v; try {{ v = JSON.parse(document.getElementById('canon-input').value); }}
    catch(e){{ document.getElementById('canon-out').textContent = 'JSON 解析失败'; return; }}
    const res = await jpost('/node/tools/canonical', {{value:v}});
    document.getElementById('canon-out').textContent = JSON.stringify(res.body, null, 2);
  }};
  document.getElementById('bundle-btn').onclick = async ()=>{{
    let b; try {{ b = JSON.parse(document.getElementById('bundle-input').value); }}
    catch(e){{ document.getElementById('bundle-out').textContent = 'JSON 解析失败'; return; }}
    const res = await jpost('/node/tools/bundle/validate', {{bundle:b}});
    document.getElementById('bundle-out').textContent = JSON.stringify(res.body, null, 2);
  }};
  document.getElementById('claim-issue-btn').onclick = async ()=>{{
    const res = await jpost('/node/claims/issue', {{
      vdc_id: document.getElementById('claim-vdc').value || 'vdc-demo',
      amount: Number(document.getElementById('claim-amount').value||0),
      holder: 'console-demo'
    }});
    document.getElementById('claim-out').textContent = JSON.stringify(res.body, null, 2);
  }};
  document.getElementById('claim-list-btn').onclick = async ()=>{{
    const r = await fetch('/node/claims'); const body = await r.json();
    document.getElementById('claim-out').textContent = JSON.stringify(body, null, 2);
  }};
  document.getElementById('settle-sim-btn').onclick = async ()=>{{
    const res = await jpost('/node/settle/simulate', {{amount:1, currency:'USD'}});
    document.getElementById('settle-out').textContent = JSON.stringify(res.body, null, 2);
  }};
}})();
</script>"""


def _panel_me(profile: dict[str, Any]) -> str:
    pol = (profile.get("operator_policy") or {})
    return f"""
<section class="tab-panel" id="panel-me" hidden>
  {_hard_boundary_banner()}
  <section class="card">
    <h2>我的（Operator · 身体层）</h2>
    <p class="muted">邮箱登录只升配额与视图；<strong>不能</strong>代签 exchange。
      策略：匿名 { _esc(pol.get("anonymous_propose_per_day", 20)) } / 日 ·
      验邮 { _esc(pol.get("verified_propose_per_day", 200)) } / 日。</p>
    <h3>注册</h3>
    <input class="tool" id="me-email" placeholder="email" />
    <input class="tool" id="me-pass" type="password" placeholder="password" style="margin-top:.4rem" />
    <input class="tool" id="me-name" placeholder="display_name" style="margin-top:.4rem" />
    <button type="button" class="tool" id="me-reg">注册</button>
    <button type="button" class="tool secondary" id="me-login">登录</button>
    <pre class="json" id="me-reg-out">—</pre>
    <h3>验邮 OTP</h3>
    <input class="tool" id="me-otp" placeholder="otp_dev from register" />
    <button type="button" class="tool" id="me-verify">验证</button>
    <h3>会话</h3>
    <button type="button" class="tool" id="me-me">刷新 /me + 配额</button>
    <button type="button" class="tool secondary" id="me-quota">匿名配额</button>
    <button type="button" class="tool secondary" id="me-notify">通知收件箱</button>
    <pre class="json" id="me-out">—</pre>
    <h3>导出 / 反馈</h3>
    <p class="muted">导出：使用交换 <code>/exchanges/{{id}}/export</code> 与离线 reverify。
      反馈：GitHub issues · 安全见 SECURITY.md。本页不托管私钥。</p>
    <h3>Operator 门户</h3>
    {_operator_nav("dashboard")}
    <p class="muted">登录后可访问绑定 Agent、我的交换、Claims、对账与注销设置。</p>
    <h3>绑定 Agent（UC-31）</h3>
    <input class="tool" id="bind-agent-id" placeholder="ed25519:… agent_id" />
    <input class="tool" id="bind-label" placeholder="label（可选）" style="margin-top:.4rem" />
    <button type="button" class="tool" id="bind-fetch-payload">获取 claim payload</button>
    <pre class="json" id="bind-payload-out">—</pre>
    <input class="tool" id="bind-sig" placeholder="Agent 本地签名（粘贴）" style="margin-top:.4rem" />
    <button type="button" class="tool" id="bind-submit">提交绑定</button>
    <pre class="json" id="bind-out">—</pre>
  </section>
</section>
<script>
(function(){{
  const tokKey = 'novapanda_operator_token';
  let bindPayload = null;
  async function jpost(url, body, token){{
    const h = {{'Content-Type':'application/json'}};
    if(token) h['Authorization'] = 'Bearer '+token;
    const r = await fetch(url, {{method:'POST', headers:h, body: JSON.stringify(body)}});
    return {{ok:r.ok, body: await r.json().catch(()=>({{}}))}};
  }}
  const regBtn = document.getElementById('me-reg');
  if(!regBtn) return;
  regBtn.onclick = async ()=>{{
    const res = await jpost('/operator/register', {{
      email: document.getElementById('me-email').value,
      password: document.getElementById('me-pass').value,
      display_name: document.getElementById('me-name').value,
      accept_terms: true
    }});
    document.getElementById('me-reg-out').textContent = JSON.stringify(res.body, null, 2);
    if(res.body.otp_dev) document.getElementById('me-otp').value = res.body.otp_dev;
  }};
  document.getElementById('me-verify').onclick = async ()=>{{
    const res = await jpost('/operator/verify', {{
      email: document.getElementById('me-email').value,
      otp: document.getElementById('me-otp').value
    }});
    document.getElementById('me-out').textContent = JSON.stringify(res.body, null, 2);
  }};
  document.getElementById('me-login').onclick = async ()=>{{
    const res = await jpost('/operator/login', {{
      email: document.getElementById('me-email').value,
      password: document.getElementById('me-pass').value
    }});
    if(res.body.session_token) sessionStorage.setItem(tokKey, res.body.session_token);
    document.getElementById('me-out').textContent = JSON.stringify(res.body, null, 2);
  }};
  document.getElementById('me-me').onclick = async ()=>{{
    const t = sessionStorage.getItem(tokKey);
    const r = await fetch('/operator/me', {{headers: t?{{Authorization:'Bearer '+t}}:{{}}}});
    document.getElementById('me-out').textContent = JSON.stringify(await r.json(), null, 2);
  }};
  document.getElementById('me-quota').onclick = async ()=>{{
    const r = await fetch('/operator/quota');
    document.getElementById('me-out').textContent = JSON.stringify(await r.json(), null, 2);
  }};
  document.getElementById('me-notify').onclick = async ()=>{{
    const t = sessionStorage.getItem(tokKey);
    const r = await fetch('/node/notify', {{headers: t?{{Authorization:'Bearer '+t}}:{{}}}});
    document.getElementById('me-out').textContent = JSON.stringify(await r.json(), null, 2);
  }};
  const fetchBtn = document.getElementById('bind-fetch-payload');
  if(fetchBtn) fetchBtn.onclick = async ()=>{{
    const t = sessionStorage.getItem(tokKey);
    const aid = document.getElementById('bind-agent-id').value.trim();
    const r = await fetch('/operator/agents/claim-payload?agent_id='+encodeURIComponent(aid), {{
      headers: t?{{Authorization:'Bearer '+t}}:{{}}
    }});
    const body = await r.json();
    bindPayload = body.payload || null;
    document.getElementById('bind-payload-out').textContent = JSON.stringify(body, null, 2);
  }};
  const bindBtn = document.getElementById('bind-submit');
  if(bindBtn) bindBtn.onclick = async ()=>{{
    const t = sessionStorage.getItem(tokKey);
    if(!bindPayload) {{ document.getElementById('bind-out').textContent = '请先获取 payload'; return; }}
    const res = await jpost('/operator/agents/bind', {{
      agent_id: bindPayload.agent_id,
      label: document.getElementById('bind-label').value,
      signature: document.getElementById('bind-sig').value.trim(),
      issued_at: bindPayload.issued_at
    }}, t);
    document.getElementById('bind-out').textContent = JSON.stringify(res.body, null, 2);
  }};
}})();
</script>"""


def _panel_discover(profile: dict[str, Any]) -> str:
    discovery = profile.get("discovery") or {}
    manifest = discovery.get("manifest") or {}
    active = discovery.get("active_types") or []
    reserved = discovery.get("reserved_types") or []
    rules = discovery.get("rules") or []

    type_rows = "".join(
        "<tr>"
        f"<td><code>{_esc(t.get('type_id'))}</code></td>"
        f"<td>{_esc(t.get('unit', ''))}</td>"
        f"<td class=\"muted\">{_esc(t.get('description', ''))}</td>"
        "</tr>"
        for t in active[:40]
    ) or '<tr><td colspan="3" class="muted">无活跃资源类型</td></tr>'

    reserved_pills = "".join(
        f'<span class="pill">{_esc(t.get("type_id"))}</span>' for t in reserved
    ) or '<span class="muted">无</span>'

    rule_rows = "".join(
        "<tr>"
        f"<td><code>{_esc(r.get('rule_id'))}</code></td>"
        f"<td>{_esc(r.get('resource_type', ''))}</td>"
        f"<td class=\"muted\">{_esc(r.get('description', ''))}</td>"
        "</tr>"
        for r in rules[:30]
    ) or '<tr><td colspan="3" class="muted">暂无规则</td></tr>'

    endpoints = manifest.get("endpoints") or {}
    ep_lines = "".join(
        f"<li><code>{_esc(k)}</code> → {_esc(v)}</li>"
        for k, v in sorted(endpoints.items())
        if not isinstance(v, list)
    )
    caps = profile.get("capabilities") or {}
    transports = endpoints.get("transport") or list(caps.get("transports") or [])
    transport_pills = "".join(f'<span class="pill">{_esc(t)}</span>' for t in transports)

    return f"""
<section class="tab-panel" id="panel-discover" hidden>
  <div class="grid">
    <div class="card">
      <h2>资源类型</h2>
      <div class="stat">{_esc(discovery.get("type_count", len(active) + len(reserved)))}</div>
      <div class="muted">活跃 {len(active)} · 保留 {len(reserved)}</div>
    </div>
    <div class="card">
      <h2>规则</h2>
      <div class="stat">{_esc(discovery.get("rule_count", len(rules)))}</div>
    </div>
    <div class="card">
      <h2>节点 ID</h2>
      <div class="mono small">{_esc(manifest.get("node_id", "—"))}</div>
    </div>
    <div class="card">
      <h2>运营方</h2>
      <div class="small">{_esc(manifest.get("operator", "—"))}</div>
    </div>
  </div>
  <section class="card">
    <h2>传输面</h2>
    <div class="pill-row">{transport_pills or '<span class="muted">—</span>'}</div>
  </section>
  <section class="card">
    <h2>Manifest 端点</h2>
    <ul class="link-list">{ep_lines or '<li class="muted">—</li>'}</ul>
  </section>
  <section class="card">
    <h2>活跃资源类型</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>类型</th><th>单位</th><th>说明</th></tr></thead>
        <tbody>{type_rows}</tbody>
      </table>
    </div>
  </section>
  <section class="card">
    <h2>保留类型</h2>
    <div class="pill-row">{reserved_pills}</div>
  </section>
  <section class="card">
    <h2>规则注册表</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>规则</th><th>资源</th><th>说明</th></tr></thead>
        <tbody>{rule_rows}</tbody>
      </table>
    </div>
  </section>
</section>"""


def _panel_scenarios(profile: dict[str, Any]) -> str:
    sc = profile.get("scenarios") or {}
    scenarios = sc.get("scenarios") or []
    links = profile.get("links") or {}
    overview = links.get("scenarios") or "https://novapanda.io/scenarios/overview.html"
    err = sc.get("error")
    if err:
        return (
            f'<section class="tab-panel card" id="panel-scenarios">'
            f"<h2>交换场景</h2>"
            f'<p class="muted">未能加载 catalog：{_esc(err)}</p>'
            f'<p><a href="{_esc(overview)}">官网场景图谱</a></p>'
            f"</section>"
        )
    status_chips = "".join(
        _state_chip(k, v) for k, v in sorted((sc.get("by_status") or {}).items())
    )
    rows: list[str] = []
    if not scenarios:
        rows.append('<tr><td colspan="6" class="muted">catalog 为空</td></tr>')
    else:
        for item in scenarios:
            sid = _esc(item.get("id", ""))
            title = _esc(item.get("title") or item.get("title_en") or "")
            status = _esc(item.get("status", ""))
            tier = _esc(item.get("tier", ""))
            uc = _esc(item.get("uc") or "—")
            oneshot = _esc(item.get("onesentence") or "")
            bundle = "✓" if item.get("bundle") else ""
            try_list = item.get("try") or []
            try_html = ", ".join(f"<code>{_esc(t)}</code>" for t in try_list[:3])
            rows.append(
                "<tr>"
                f"<td><code>{sid}</code></td>"
                f"<td>{title}"
                f'<div class="muted small">{oneshot}</div></td>'
                f"<td>{_state_chip(status)} <span class=\"muted small\">{tier}</span></td>"
                f"<td><code>{uc}</code></td>"
                f"<td>{bundle}</td>"
                f'<td class="small">{try_html}</td>'
                "</tr>"
            )
    return f"""
<section class="tab-panel card" id="panel-scenarios">
  <h2>交换场景 <span class="muted">({_esc(sc.get("total", 0))})</span></h2>
  <p class="muted">与开源 <code>docs/scenarios/catalog.json</code> 同源 ·
    更新 {_esc(sc.get("updated") or "—")} ·
    <a href="{_esc(overview)}">图谱总览</a> ·
    <a href="/node/scenarios">JSON</a></p>
  <div class="chips" style="margin-bottom:.75rem">{status_chips or '<span class="muted">—</span>'}</div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>UC</th><th>Bundle</th><th>试跑</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</section>"""


def _panel_exchanges(profile: dict[str, Any]) -> str:
    status = profile.get("status") or {}
    ex_block = profile.get("exchanges") or {}
    items = ex_block.get("items") or status.get("recent") or []
    total = ex_block.get("total", status.get("exchange_total", len(items)))
    rows = _exchange_table_rows(items)
    return f"""
<section class="tab-panel" id="panel-exchanges" hidden>
  <section class="card">
    <h2>交换列表</h2>
    <p class="muted">共 {_esc(total)} 条 · 点击 ID 查看详情</p>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>ID</th><th>状态</th><th>Client</th><th>Provider</th>
          <th>资源</th><th>数量</th><th>更新</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </section>
</section>"""


def _panel_reputation(profile: dict[str, Any]) -> str:
    rep = profile.get("reputation") or {}
    outcomes = rep.get("by_outcome") or {}
    outcome_chips = "".join(_state_chip(k, v) for k, v in sorted(outcomes.items(), key=lambda kv: -kv[1]))
    if not outcome_chips:
        outcome_chips = '<span class="muted">暂无信誉条目</span>'
    chain_ok = rep.get("chain_valid", True)
    chain_badge = (
        '<span class="badge">链校验通过</span>'
        if chain_ok
        else '<span class="badge badge-warn">链校验异常</span>'
    )
    agent_rows = "".join(
        "<tr>"
        f"<td class=\"mono small\">{_esc(a.get('agent_id'))}</td>"
        f"<td>{_esc(a.get('entries', 0))}</td>"
        "</tr>"
        for a in rep.get("top_agents") or []
    ) or '<tr><td colspan="2" class="muted">暂无 Agent 记录</td></tr>'
    return f"""
<section class="tab-panel" id="panel-reputation" hidden>
  <div class="grid">
    <div class="card">
      <h2>信誉条目</h2>
      <div class="stat">{_esc(rep.get("total_entries", 0))}</div>
    </div>
    <div class="card">
      <h2>独立 Agent</h2>
      <div class="stat">{_esc(rep.get("unique_agents", 0))}</div>
    </div>
    <div class="card">
      <h2>链完整性</h2>
      <div style="margin-top:.5rem">{chain_badge}</div>
    </div>
  </div>
  <section class="card">
    <h2>按结果分布</h2>
    <div class="chips">{outcome_chips}</div>
  </section>
  <section class="card">
    <h2>活跃 Agent（Top）</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Agent</th><th>条目数</th></tr></thead>
        <tbody>{agent_rows}</tbody>
      </table>
    </div>
  </section>
</section>"""


def _panel_trial(profile: dict[str, Any]) -> str:
    links = profile.get("links") or {}
    discovery = profile.get("discovery") or {}
    manifest = discovery.get("manifest") or {}
    mock = manifest.get("mock_trial", True)
    settlement = manifest.get("settlement") or (profile.get("status") or {}).get("settlement", "mock")
    link_items = "".join(
        f'<li><a href="{_esc(url)}" rel="noopener">{_esc(label)}</a></li>'
        for label, url in [
            ("开发者 Trial 指南", links.get("trial", "https://novapanda.io/trial.html")),
            ("协议宪法", links.get("constitution", "https://novapanda.io/constitution.html")),
            ("规范 SPEC", links.get("spec", "")),
            ("GitHub 仓库", links.get("github", "")),
        ]
        if url
    )
    return f"""
<section class="tab-panel" id="panel-trial" hidden>
  <section class="card">
    <h2>公开 mock 试用</h2>
    <p class="muted">
      本节点为 NovaPanda 参考实现的零号运营实例，结算模式为
      <code>{_esc(settlement)}</code>，{'启用 mock 试用' if mock else '非 mock 环境'}。
      不涉及真实资金托管。
    </p>
    <h3>快速开始</h3>
    <ol class="muted">
      <li>阅读 Trial 文档，获取 SDK 与示例脚本</li>
      <li>向本节点 <code>POST /exchanges</code> 发起 propose</li>
      <li>完成 contract → escrow → deliver → verify → confirm 生命周期</li>
      <li>在「交换」页查看 VDC 与状态流转</li>
    </ol>
    <ul class="link-list">{link_items}</ul>
    {_brand_poster_section(compact=True)}
  </section>
  <section class="card">
    <h2>条款</h2>
    <p class="muted">
      用户协议：<a href="{_esc(manifest.get('terms_url', 'https://novapanda.io/terms.html'))}">terms</a> ·
      隐私政策：<a href="{_esc(manifest.get('privacy_url', 'https://novapanda.io/privacy.html'))}">privacy</a>
    </p>
  </section>
</section>"""


def _panel_api(profile: dict[str, Any]) -> str:
    discovery = profile.get("discovery") or {}
    manifest = discovery.get("manifest") or {}
    endpoints = manifest.get("endpoints") or {}
    caps = profile.get("capabilities") or {}
    transports = endpoints.get("transport") or caps.get("transports") or []
    transport_list = "".join(f"<li><code>{_esc(t)}</code></li>" for t in transports)
    api_links = "".join(
        f'<li><a href="{_esc(path)}">{_esc(label)}</a></li>'
        for label, path in [
            ("OpenAPI / Swagger", "/docs"),
            ("健康检查", endpoints.get("health", "/health")),
            ("节点 Manifest", endpoints.get("manifest", "/.well-known/novapanda.json")),
            ("节点信息 JSON", endpoints.get("node_info", "/node/info")),
            ("交换 API", endpoints.get("exchange", "/exchanges")),
        ]
        if path
    )
    features = manifest.get("features") or {}
    feature_pills = "".join(
        f'<span class="pill">{_esc(k)}: {_esc(v)}</span>'
        for k, v in sorted(features.items())
    )
    return f"""
<section class="tab-panel" id="panel-api" hidden>
  <section class="card">
    <h2>HTTP 端点</h2>
    <ul class="link-list">{api_links}</ul>
  </section>
  <section class="card">
    <h2>传输面</h2>
    <ul class="link-list">{transport_list or '<li class="muted">—</li>'}</ul>
  </section>
  <section class="card">
    <h2>Manifest 特性</h2>
    <div class="pill-row">{feature_pills or '<span class="muted">—</span>'}</div>
  </section>
  <section class="card">
    <h2>默认超时（秒）</h2>
    {_json_pretty(caps.get("default_timeouts") or {})}
  </section>
  <section class="card">
    <h2>完整 Manifest（只读）</h2>
    {_json_pretty(manifest)}
  </section>
</section>"""


def _admin_body() -> str:
    return """
<section class="card" id="admin">
  <h2>运维操作</h2>
  <p class="muted">输入 <code>NOVAPANDA_ADMIN_TOKEN</code>（仅存于本机浏览器）。匿名用户不可重置整站。</p>
  <label class="field">Admin Token
    <input type="password" id="admin-token" placeholder="production.env 中的 token" autocomplete="off">
  </label>
  <div class="actions">
    <button type="button" id="sweep-btn">立即 Sweep</button>
    <button type="button" class="secondary" id="info-btn">刷新节点信息</button>
    <button type="button" class="secondary" id="audit-btn">审计日志</button>
    <button type="button" class="secondary" id="alerts-btn">告警快照</button>
    <button type="button" class="secondary" id="reconcile-btn">对账导出 CSV</button>
    <button type="button" class="secondary" id="reset-btn">基线重置（试验）</button>
    <span id="sweep-result" class="muted"></span>
  </div>
</section>
<section class="card">
  <h2>输出 <span class="muted" id="info-status"></span></h2>
  <pre class="json" id="node-info">点击按钮加载…</pre>
</section>
<script>
(function () {
  const key = 'novapanda_admin_token';
  const input = document.getElementById('admin-token');
  const saved = sessionStorage.getItem(key);
  if (saved) input.value = saved;
  input.addEventListener('change', function () {
    sessionStorage.setItem(key, input.value);
  });
  function tokenHeaders() {
    const token = input.value.trim();
    sessionStorage.setItem(key, token);
    return { 'X-Admin-Token': token, 'Content-Type': 'application/json' };
  }
  document.getElementById('sweep-btn').addEventListener('click', async function () {
    const out = document.getElementById('sweep-result');
    if (!input.value.trim()) { out.textContent = '请先填写 token（若未配置 ADMIN_TOKEN 可留空仅本地）'; }
    out.textContent = '执行中…';
    try {
      const r = await fetch('/admin/sweep', { method: 'POST', headers: tokenHeaders() });
      const body = await r.json().catch(function () { return {}; });
      if (!r.ok) throw new Error(body.msg || body.detail || r.status);
      out.textContent = '完成：过期清扫 ' + ((body.expired || []).length) + ' 条';
    } catch (e) { out.textContent = '失败：' + e.message; }
  });
  async function showJson(url, method) {
    const el = document.getElementById('node-info');
    const st = document.getElementById('info-status');
    st.textContent = '加载中…';
    try {
      const r = await fetch(url, { method: method || 'GET', headers: tokenHeaders() });
      const body = await r.json();
      if (!r.ok) throw new Error(body.msg || body.detail || r.status);
      el.textContent = JSON.stringify(body, null, 2);
      st.textContent = '· 已更新';
    } catch (e) {
      el.textContent = '失败：' + e.message;
      st.textContent = '';
    }
  }
  document.getElementById('info-btn').addEventListener('click', function(){ showJson('/node/info'); });
  document.getElementById('audit-btn').addEventListener('click', function(){ showJson('/admin/audit'); });
  document.getElementById('alerts-btn').addEventListener('click', function(){ showJson('/admin/alerts'); });
  document.getElementById('reconcile-btn').addEventListener('click', async function(){
    const el = document.getElementById('node-info');
    const st = document.getElementById('info-status');
    st.textContent = '导出中…';
    try {
      const r = await fetch('/admin/reconcile/export?format=csv', { headers: tokenHeaders() });
      const text = await r.text();
      if (!r.ok) throw new Error(text);
      el.textContent = text.slice(0, 12000) + (text.length > 12000 ? '\\n…(truncated)' : '');
      st.textContent = '· CSV';
    } catch (e) { el.textContent = '失败：' + e.message; st.textContent = ''; }
  });
  document.getElementById('reset-btn').addEventListener('click', function(){
    if (!confirm('确认基线重置？仅清 mock claim/通知/配额计数')) return;
    showJson('/admin/baseline-reset', 'POST');
  });
  showJson('/node/info');
})();
</script>"""


def render_console(profile: dict[str, Any], *, admin: bool = False) -> str:
    """渲染零号节点控制台 HTML。"""
    if admin:
        title = "NovaPanda 零号节点 · 运维"
        return _layout(title, _admin_body(), admin=True)

    title = "NovaPanda 智能开放交割协议"
    panels = "".join([
        _panel_overview(profile),
        _panel_discover(profile),
        _panel_scenarios(profile),
        _panel_verify(profile),
        _panel_exchanges(profile),
        _panel_reputation(profile),
        _panel_trial(profile),
        _panel_api(profile),
        _panel_me(profile),
    ])
    body = panels
    return _layout(title, body, admin=False, extra_script=_TAB_SCRIPT)


def render_exchange_detail(detail: dict[str, Any]) -> str:
    """渲染单条交换详情页。"""
    eid = _esc(detail.get("exchange_id", ""))
    state = detail.get("state", "")
    skip = frozenset({"verify_result", "settlement_receipt", "extensions", "dispute_ticket", "dispute_info"})
    rows = "".join(
        f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>"
        for k, v in sorted(detail.items())
        if k not in skip
    )
    extra = _trace_block(detail)
    if detail.get("verify_result") is not None:
        extra += f"<h3>verify_result</h3>{_json_pretty(detail['verify_result'])}"
    if detail.get("settlement_receipt") is not None:
        extra += f"<h3>settlement_receipt</h3>{_json_pretty(detail['settlement_receipt'])}"
    if detail.get("dispute_info"):
        extra += f"<h3>dispute_info</h3>{_json_pretty(detail['dispute_info'])}"
    vdc_link = ""
    if detail.get("vdc_lookup"):
        vdc_link = f'<p><a href="{_esc(detail["vdc_lookup"])}">查看 VDC</a></p>'
    dispute = _dispute_banner(detail.get("dispute_ticket"))
    frail = _frail_outage_banner() if detail.get("settlement_rail_down") else ""
    body = f"""
<p><a href="/#exchanges">← 返回控制台</a></p>
{dispute}
{frail}
<section class="card">
  <h2>交换 <code>{eid}</code></h2>
  <p>{_state_chip(state)}</p>
  {vdc_link}
  <dl class="kv">{rows}</dl>
  {extra}
</section>"""
    return _layout(f"交换 {detail.get('exchange_id', '')}", body, admin=False)


def _operator_layout(title: str, active: str, inner: str) -> str:
    return _layout(
        title,
        f'<p><a href="/">← 控制台</a> · <a href="/#me">我的 Tab</a></p>{_operator_nav(active)}{inner}',
        admin=False,
    )


def render_operator_claims(claims: list[dict[str, Any]], *, mock: bool = True) -> str:
    rows: list[str] = []
    for c in claims:
        mock_badge = '<span class="claim-mock">mock</span>' if c.get("mock") else ""
        cid = _esc(c.get("claim_id", ""))
        vdc = _esc(c.get("vdc_id", ""))
        rows.append(
            "<tr>"
            f'<td><a href="/operator/claims/{cid}"><code>{cid}</code></a></td>'
            f'<td>{_esc(c.get("status", ""))}</td>'
            f'<td>{_esc(c.get("amount", ""))} {_esc(c.get("currency", ""))}</td>'
            f'<td>{_esc(c.get("rail", ""))} {mock_badge}</td>'
            f'<td class="mono small"><a href="/vdc/{vdc}"><code>{_esc(_short(str(c.get("vdc_id", ""))))}</code></a></td>'
            f'<td class="muted">{_esc(c.get("issued_at") or c.get("created_at", ""))}</td>'
            "</tr>"
        )
    table = "".join(rows) or '<tr><td colspan="6" class="muted">尚无结算权柄</td></tr>'
    inner = f"""
{_claims_risk_bar()}
<section class="card">
  <h2>我的权柄（Claims）</h2>
  <p class="muted">只读视图；再花须 Agent 签名。{'模拟环境' if mock else '生产登记'}</p>
  <table class="data">
    <thead><tr>
      <th>claim_id</th><th>status</th><th>amount</th><th>rail</th><th>vdc_id</th><th>时间</th>
    </tr></thead>
    <tbody>{table}</tbody>
  </table>
</section>"""
    return _operator_layout("Operator · Claims", "claims", inner)


def render_claim_detail(claim: dict[str, Any]) -> str:
    cid = _esc(claim.get("claim_id", ""))
    vdc = claim.get("vdc_id", "")
    vdc_link = f'<p><a href="/vdc/{_esc(vdc)}" target="_blank">复验锚定 VDC</a></p>' if vdc else ""
    inner = f"""
{_claims_risk_bar()}
<section class="card">
  <h2>权柄 <code>{cid}</code></h2>
  {vdc_link}
  {_json_pretty(claim)}
</section>"""
    return _operator_layout(f"Claim {claim.get('claim_id', '')}", "claims", inner)


def render_operator_reconcile(meta: dict[str, Any], preview_rows: list[dict]) -> str:
    inner = f"""
<section class="card">
  <h2>T14 对账预览</h2>
  <p class="muted">选择日期范围后导出 CSV（须已登录 Session）。</p>
  <label class="field">from <input type="text" id="rec-from" placeholder="2026-07-01T00:00:00Z" /></label>
  <label class="field">to <input type="text" id="rec-to" placeholder="2026-07-10T23:59:59Z" /></label>
  <button type="button" id="rec-export">导出 CSV</button>
  <pre class="json" id="rec-msg">—</pre>
  {_json_pretty(meta)}
  <h3>样例行（最多 20）</h3>
  {_json_pretty(preview_rows[:20])}
</section>
<script>
(function(){{
  const tokKey = 'novapanda_operator_token';
  const btn = document.getElementById('rec-export');
  if(!btn) return;
  btn.onclick = async ()=>{{
    const t = sessionStorage.getItem(tokKey);
    if(!t) {{ document.getElementById('rec-msg').textContent = '请先登录'; return; }}
    const from = document.getElementById('rec-from').value.trim();
    const to = document.getElementById('rec-to').value.trim();
    let url = '/operator/reconcile/export?format=csv';
    if(from) url += '&from_ts=' + encodeURIComponent(from);
    if(to) url += '&to_ts=' + encodeURIComponent(to);
    const r = await fetch(url, {{headers: {{Authorization: 'Bearer '+t}}}});
    const text = await r.text();
    document.getElementById('rec-msg').textContent = r.ok ? text.slice(0, 800) + (text.length>800?'…':'') : text;
  }};
}})();
</script>"""
    return _operator_layout("Operator · 对账", "reconcile", inner)


def render_operator_disputes(tickets: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for t in tickets:
        tid = _esc(t.get("ticket_id", ""))
        rows.append(
            "<tr>"
            f"<td><code>{tid}</code></td>"
            f'<td><a href="/console/exchanges/{_esc(t.get("exchange_id", ""))}">'
            f'<code>{_esc(_short(str(t.get("exchange_id", ""))))}</code></a></td>'
            f'<td>{_esc(t.get("tier", ""))}</td>'
            f'<td>{_esc(t.get("state", ""))}</td>'
            f'<td class="muted">{_esc(t.get("opened_at", ""))}</td>'
            "</tr>"
        )
    table = "".join(rows) or '<tr><td colspan="5" class="muted">暂无争议工单</td></tr>'
    inner = f"""
<section class="card">
  <h2>争议工单（只读）</h2>
  <table class="data">
    <thead><tr><th>ticket</th><th>exchange</th><th>tier</th><th>state</th><th>opened</th></tr></thead>
    <tbody>{table}</tbody>
  </table>
</section>"""
    return _operator_layout("Operator · 争议", "disputes", inner)


def render_operator_dashboard(operator: dict[str, Any], quota: dict[str, Any], bindings: list[dict]) -> str:
    bind_rows = "".join(
        f"<li><code>{_esc(b.get('agent_id', ''))}</code> {_esc(b.get('label', ''))}</li>"
        for b in bindings
    ) or "<li class=\"muted\">尚未绑定 Agent</li>"
    inner = f"""
<section class="card">
  <h2>Operator 概览</h2>
  <p>{_esc(operator.get('display_name', ''))} · <code>{_esc(operator.get('email', ''))}</code></p>
  <p class="muted">配额：已用 {_esc(quota.get('used', 0))} / {_esc(quota.get('limit', 0))}（剩余 {_esc(quota.get('remaining', 0))}）</p>
  <h3>已绑定 Agent</h3>
  <ul>{bind_rows}</ul>
</section>"""
    return _operator_layout("Operator · 概览", "dashboard", inner)


def render_operator_agents_ui(bindings: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td><code>{_esc(b.get('agent_id', ''))}</code></td>"
        f"<td>{_esc(b.get('label', ''))}</td>"
        f"<td>{_esc(b.get('bound_at', ''))}</td>"
        f"<td>{'✓' if b.get('verified') else '—'}</td>"
        "</tr>"
        for b in bindings
    ) or '<tr><td colspan="4" class="muted">无绑定</td></tr>'
    inner = f"""
<section class="card">
  <h2>绑定 Agent（UC-31）</h2>
  <p class="muted">须在 Agent 本地对 <code>novapanda.operator_claim</code> payload 签名。快捷入口见控制台「我的」Tab。</p>
  <table class="data">
    <thead><tr><th>agent_id</th><th>label</th><th>bound_at</th><th>verified</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""
    return _operator_layout("Operator · 绑定", "agents", inner)


def render_operator_exchanges(items: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f'<td><a href="/console/exchanges/{_esc(ex.get("exchange_id", ""))}"><code>{_esc(_short(str(ex.get("exchange_id", ""))))}</code></a></td>'
        f'<td>{_state_chip(ex.get("state", ""))}</td>'
        f'<td class="mono small">{_esc(_short(str(ex.get("client", ""))))}</td>'
        f'<td class="mono small">{_esc(_short(str(ex.get("provider", ""))))}</td>'
        f'<td class="muted">{_esc(ex.get("updated_at", ""))}</td>'
        "</tr>"
        for ex in items
    ) or '<tr><td colspan="5" class="muted">无匹配交换（请先绑定 Agent）</td></tr>'
    inner = f"""
<section class="card">
  <h2>我的交换</h2>
  <p class="muted">仅显示已绑定 Agent 作为 client 或 provider 的交换。</p>
  <table class="data">
    <thead><tr><th>id</th><th>state</th><th>client</th><th>provider</th><th>updated</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""
    return _operator_layout("Operator · 交换", "exchanges", inner)


def render_operator_settings(operator: dict[str, Any]) -> str:
    del_at = operator.get("deletion_requested_at")
    status = f"已申请注销：{_esc(del_at)}" if del_at else "未申请注销"
    inner = f"""
<section class="card">
  <h2>账户设置（UC-34）</h2>
  <p>{_esc(operator.get('display_name', ''))} · {_esc(status)}</p>
  <p class="muted">注销抹除 Operator PII 与绑定；<strong>不</strong>废除已签 VDC。冷静期 14 日（本节点 stub：立即记录申请）。</p>
  <p class="muted">导出：在交换列表使用 <code>/exchanges/{{id}}/export</code>；Claim 包见 Claims 详情。</p>
  <button type="button" class="tool" id="del-req">申请注销</button>
  <button type="button" class="tool secondary" id="del-cancel">撤销注销申请</button>
  <pre class="json" id="del-out">—</pre>
</section>
<script>
(function(){{
  const tokKey = 'novapanda_operator_token';
  async function post(path) {{
    const t = sessionStorage.getItem(tokKey);
    const r = await fetch(path, {{method:'POST', headers: t?{{Authorization:'Bearer '+t}}:{{}}}});
    document.getElementById('del-out').textContent = JSON.stringify(await r.json(), null, 2);
  }}
  document.getElementById('del-req').onclick = ()=> post('/operator/settings/deletion-request');
  document.getElementById('del-cancel').onclick = ()=> post('/operator/settings/deletion-cancel');
}})();
</script>"""
    return _operator_layout("Operator · 设置", "settings", inner)


def render_operator_help() -> str:
    inner = """
<section class="card">
  <h2>帮助 · Litmus</h2>
  <ul class="link-list">
    <li><a href="https://novapanda.io/trial.html">Trial 指南</a></li>
    <li><a href="/docs">OpenAPI</a></li>
    <li><code>docs/IMPLEMENTER_GUIDE.md</code>（仓库）</li>
    <li><code>docs/compatibility.md</code>（兼容登记）</li>
    <li><code>python -m conformance.run</code>（本机自检）</li>
  </ul>
  <p class="muted">Operator 登录不替代 Agent 签名；注册仅升配额与「我的」视图。</p>
</section>"""
    return _operator_layout("Operator · 帮助", "help", inner)


def render_operator_bundles() -> str:
    inner = """
<section class="card">
  <h2>Bundle 索引</h2>
  <p class="muted">Bundle 由 Composer 客户端持有；节点不垄断编排。可用验证 Tab 校验 Bundle JSON。</p>
  <p><a href="/#verify">打开 Bundle 校验 →</a></p>
</section>"""
    return _operator_layout("Operator · Bundle", "bundles", inner)


def render_steward_certifications(items: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td><code>{_esc(c.get('cert_id', ''))}</code></td>"
        f"<td>{_esc(c.get('level', ''))}</td>"
        f"<td>{_esc(c.get('status', ''))}</td>"
        f'<td class="muted">{_esc(c.get("granted_at", ""))}</td>'
        "</tr>"
        for c in items
    ) or '<tr><td colspan="4" class="muted">暂无名录</td></tr>'
    body = f"""
<p><a href="/admin">← 运维</a></p>
<section class="card">
  <h2>Steward · 兼容认证名录</h2>
  <p class="muted">发号须 <code>X-Steward-Token</code>；公开名录见 <code>/public/certifications</code>。</p>
  <label class="field">Steward Token
    <input type="password" id="steward-token" autocomplete="off" />
  </label>
  <table class="data">
    <thead><tr><th>id</th><th>level</th><th>status</th><th>granted</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""
    return _layout("Steward · 认证", body, admin=False)
