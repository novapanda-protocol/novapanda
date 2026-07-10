#!/usr/bin/env python3
"""Rewrite docs/scenarios/figures/*.svg with valid UTF-8 Chinese."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "scenarios" / "figures"

SVG = {
    "01-lifecycle.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 280" role="img">
  <defs><style>
    .bg{fill:#0f1624}.box{fill:#1a2740;stroke:#3d9cf5;stroke-width:1.5}
    .ok{fill:#143528;stroke:#3ecf8e}.bad{fill:#3a1e24;stroke:#ff8f8f}
    .lbl{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:13px;font-weight:600;text-anchor:middle}
    .sub{fill:#8fa3bc;font-family:system-ui,sans-serif;font-size:11px;text-anchor:middle}
    .title{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:16px;font-weight:700}
    .arrow{stroke:#5b7ea6;stroke-width:2;fill:none;marker-end:url(#m)}
    .ab{stroke:#c57a7a;stroke-width:1.5;fill:none;marker-end:url(#mb);stroke-dasharray:4 3}
  </style>
  <marker id="m" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#5b7ea6"/></marker>
  <marker id="mb" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#c57a7a"/></marker></defs>
  <rect class="bg" width="960" height="280" rx="16"/>
  <text class="title" x="24" y="36">标准生命周期 / Shared lifecycle</text>
  <text class="sub" x="480" y="36">所有场景共用同一状态机</text>
  <g transform="translate(40,70)"><rect class="box" width="120" height="52" rx="10"/><text class="lbl" x="60" y="24">PROPOSED</text><text class="sub" x="60" y="42">要约</text></g>
  <path class="arrow" d="M165 96 H195"/>
  <g transform="translate(200,70)"><rect class="box" width="120" height="52" rx="10"/><text class="lbl" x="60" y="24">CONTRACTED</text><text class="sub" x="60" y="42">缔约</text></g>
  <path class="arrow" d="M325 96 H355"/>
  <g transform="translate(360,70)"><rect class="box" width="120" height="52" rx="10"/><text class="lbl" x="60" y="24">ESCROWED</text><text class="sub" x="60" y="42">托管</text></g>
  <path class="arrow" d="M485 96 H515"/>
  <g transform="translate(520,70)"><rect class="box" width="120" height="52" rx="10"/><text class="lbl" x="60" y="24">DELIVERED</text><text class="sub" x="60" y="42">交付</text></g>
  <path class="arrow" d="M645 96 H675"/>
  <g transform="translate(680,70)"><rect class="box" width="110" height="52" rx="10"/><text class="lbl" x="55" y="24">VERIFIED</text><text class="sub" x="55" y="42">验收</text></g>
  <path class="arrow" d="M795 96 H825"/>
  <g transform="translate(830,70)"><rect class="ok box" width="100" height="52" rx="10"/><text class="lbl" x="50" y="24">SETTLED</text><text class="sub" x="50" y="42">终局</text></g>
  <text class="sub" x="480" y="265">Truth = dual-signed VDC · 节点可替代</text>
</svg>""",
    "02-strangers.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 320" role="img">
  <defs><style>
    .bg{fill:#0f1624}.agent{fill:#1a2740;stroke:#4da3ff;stroke-width:2}
    .node{fill:#182033;stroke:#8fa3bc;stroke-width:1.5;stroke-dasharray:5 4}
    .vdc{fill:#143528;stroke:#3ecf8e;stroke-width:2}
    .lbl{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:14px;font-weight:650;text-anchor:middle}
    .sub{fill:#8fa3bc;font-family:system-ui,sans-serif;font-size:12px;text-anchor:middle}
    .title{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:16px;font-weight:700}
    .arrow{stroke:#5b7ea6;stroke-width:2;fill:none;marker-end:url(#m)}
  </style><marker id="m" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#5b7ea6"/></marker></defs>
  <rect class="bg" width="960" height="320" rx="16"/>
  <text class="title" x="24" y="36">陌生人也能交割 / Strangers can settle</text>
  <text class="sub" x="24" y="58">无共用账号 · 无预建关系</text>
  <ellipse class="agent" cx="160" cy="160" rx="110" ry="70"/>
  <text class="lbl" x="160" y="155">Client Agent</text>
  <ellipse class="agent" cx="800" cy="160" rx="110" ry="70"/>
  <text class="lbl" x="800" y="155">Provider Agent</text>
  <rect class="node" x="380" y="100" width="200" height="120" rx="14"/>
  <text class="lbl" x="480" y="145">兼容节点</text>
  <text class="sub" x="480" y="168">可替代 · 非闸门</text>
  <path class="arrow" d="M270 145 H375"/><path class="arrow" d="M585 145 H690"/>
  <rect class="vdc" x="355" y="250" width="250" height="48" rx="10"/>
  <text class="lbl" x="480" y="280">双签 VDC · reverify</text>
</svg>""",
    "03-layers.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 300" role="img">
  <defs><style>
    .bg{fill:#0f1624}.top{fill:#1a2740;stroke:#4da3ff;stroke-width:2}
    .bot{fill:#182033;stroke:#8fa3bc;stroke-width:1.5}.chip{fill:#243044;stroke:#3a4d66}
    .lbl{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:14px;font-weight:650;text-anchor:middle}
    .sub{fill:#8fa3bc;font-family:system-ui,sans-serif;font-size:12px;text-anchor:middle}
    .title{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:16px;font-weight:700}
    .tag{fill:#3ecf8e;font-family:system-ui,sans-serif;font-size:11px;font-weight:700}
  </style></defs>
  <rect class="bg" width="960" height="300" rx="16"/>
  <text class="title" x="24" y="36">先统一交割，再谈货币 / VDC above settlement</text>
  <rect class="top" x="60" y="80" width="840" height="90" rx="14"/>
  <text class="tag" x="90" y="108">L1 FIRST CITIZEN</text>
  <text class="lbl" x="480" y="125">VDC · 可验证交付 · 开放语法</text>
  <rect class="bot" x="60" y="190" width="840" height="80" rx="14"/>
  <text class="tag" x="90" y="218" style="fill:#8fa3bc">L4 PLUGGABLE</text>
  <text class="sub" x="200" y="244">mock</text><text class="sub" x="320" y="244">x402</text>
  <text class="sub" x="440" y="244">AP2</text><text class="sub" x="560" y="244">法币伙伴</text>
</svg>""",
    "04-matrix.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 520" role="img">
  <defs><style>
    .bg{fill:#0f1624}.now{fill:#1a2740;stroke:#4da3ff;stroke-width:1.5}
    .lh{fill:#2a2418;stroke:#f0b429;stroke-width:1.5}.core{fill:#143528;stroke:#3ecf8e;stroke-width:1.5}
    .lbl{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:13px;font-weight:650}
    .sub{fill:#8fa3bc;font-family:system-ui,sans-serif;font-size:11px}
    .title{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:16px;font-weight:700}
    .h{fill:#8fa3bc;font-family:system-ui,sans-serif;font-size:12px;font-weight:600}
  </style></defs>
  <rect class="bg" width="1000" height="520" rx="16"/>
  <text class="title" x="24" y="36">场景矩阵 / Scenario matrix</text>
  <text class="sub" x="24" y="56">蓝=现在可演示 · 金=灯塔 · 绿=共用语法</text>
  <rect class="core" x="40" y="80" width="920" height="56" rx="10"/>
  <text class="lbl" x="60" y="110">共用语法 · 生命周期 · 陌生人 · 接入面</text>
  <text class="h" x="60" y="170">领域</text><text class="h" x="280" y="170">dual_signed</text><text class="h" x="640" y="170">metered</text>
  <text class="lbl" x="60" y="215">软件 Agent</text>
  <rect class="now" x="220" y="190" width="360" height="50" rx="8"/>
  <text class="lbl" x="240" y="220">抽取 · 通用任务 · LLM · Token</text>
  <text class="lbl" x="60" y="285">能源 / 机器人</text>
  <rect class="lh" x="600" y="260" width="340" height="50" rx="8"/>
  <text class="lbl" x="620" y="290">S-energy-dc · S-robot-task</text>
  <text class="sub" x="40" y="490">嵌套尽调 S-nested-soft-diligence · 拒绝/超时/联邦</text>
</svg>""",
    "05-iot-ecosystem.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 640" role="img">
  <defs><style>
    .bg{fill:#0f1624}.core{fill:#143528;stroke:#3ecf8e;stroke-width:2.5}
    .n{fill:#1a2740;stroke:#4da3ff;stroke-width:1.8}.lh{fill:#2a2418;stroke:#f0b429;stroke-width:1.8}
    .lbl{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:14px;font-weight:700;text-anchor:middle}
    .sub{fill:#8fa3bc;font-family:system-ui,sans-serif;font-size:11px;text-anchor:middle}
    .title{fill:#e8eef6;font-family:system-ui,sans-serif;font-size:17px;font-weight:700}
    .link{stroke:#5b7ea6;stroke-width:1.5;fill:none}
  </style></defs>
  <rect class="bg" width="1000" height="640" rx="16"/>
  <text class="title" x="28" y="36">智能万物交换 / One IoT grammar</text>
  <text class="sub" x="28" y="56">车 · 无人机 · 机器人 · 软件 Agent</text>
  <ellipse class="core" cx="500" cy="320" rx="150" ry="88"/>
  <text class="lbl" x="500" y="315">VDC 交割语法</text>
  <rect class="n" x="40" y="120" width="200" height="90" rx="12"/><text class="lbl" x="140" y="165">Software</text>
  <rect class="lh" x="760" y="120" width="200" height="90" rx="12"/><text class="lbl" x="860" y="165">Vehicles</text>
  <rect class="lh" x="40" y="430" width="200" height="90" rx="12"/><text class="lbl" x="140" y="475">Drones</text>
  <rect class="lh" x="760" y="430" width="200" height="90" rx="12"/><text class="lbl" x="860" y="475">Robots</text>
  <path class="link" d="M240 165 Q370 240 370 280"/><path class="link" d="M760 165 Q630 240 630 280"/>
  <path class="link" d="M240 475 Q370 400 370 360"/><path class="link" d="M760 475 Q630 400 630 360"/>
</svg>""",
    "06-poster-nested.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img">
  <defs><style>
    .bg{fill:#070b14}.soft{fill:#152238;stroke:#4da3ff;stroke-width:1.6}
    .phys{fill:#231c12;stroke:#f0b429;stroke-width:1.6}.vdc{fill:#143528;stroke:#3ecf8e;stroke-width:1.4}
    .goal{fill:#1a2740;stroke:#e8eef6;stroke-width:1.2;stroke-dasharray:5 4}
    .lbl{fill:#e8eef6;font-family:system-ui,sans-serif;font-weight:700}
    .sub{fill:#8fa3bc;font-family:system-ui,sans-serif}
    .tag{fill:#3ecf8e;font-size:11px;font-weight:700;font-family:system-ui,sans-serif}
    .tag2{fill:#f0b429;font-size:11px;font-weight:700;font-family:system-ui,sans-serif}
    .brand{fill:#4da3ff;font-family:system-ui,sans-serif;font-weight:800;font-size:22px}
    .panel{fill:#121a2a;stroke:#2a3a52;stroke-width:1.5}
  </style></defs>
  <rect class="bg" width="1200" height="760" rx="20"/>
  <text class="brand" x="48" y="48">NovaPanda</text>
  <text class="lbl" x="48" y="84" style="font-size:28px">一笔业务，多张收据</text>
  <text class="sub" x="48" y="112" style="font-size:15px">多笔 Exchange · 多张 VDC · Bundle 不推倒状态机</text>
  <rect class="soft" x="40" y="140" width="540" height="480" rx="16"/>
  <text class="tag" x="60" y="168">NOW · 软件排练</text>
  <text class="lbl" x="60" y="198" style="font-size:18px">嵌套 B · 供应商尽调包</text>
  <rect class="goal" x="70" y="245" width="480" height="44" rx="8"/>
  <text class="lbl" x="90" y="273" style="font-size:14px">Goal · 尽调包 · correlation_id</text>
  <rect class="vdc" x="90" y="310" width="200" height="56" rx="8"/><text class="lbl" x="110" y="340" style="font-size:13px">VDC1 抽取</text>
  <rect class="vdc" x="320" y="310" width="200" height="56" rx="8"/><text class="lbl" x="340" y="340" style="font-size:13px">VDC2 合规</text>
  <rect class="vdc" x="205" y="390" width="210" height="56" rx="8"/><text class="lbl" x="225" y="420" style="font-size:13px">VDC3 LLM</text>
  <rect class="phys" x="620" y="140" width="540" height="480" rx="16"/>
  <text class="tag2" x="640" y="168">LIGHTHOUSE · 物理灯塔</text>
  <text class="lbl" x="640" y="198" style="font-size:18px">嵌套 A · 到场巡检闭环</text>
  <rect class="goal" x="650" y="245" width="480" height="44" rx="8"/>
  <text class="lbl" x="670" y="273" style="font-size:14px">Goal · 车·无人机·机器人·可选充电</text>
  <rect class="vdc" x="660" y="310" width="130" height="50" rx="8"/><text class="lbl" x="675" y="340" style="font-size:12px">VDC1 车</text>
  <rect class="vdc" x="810" y="310" width="130" height="50" rx="8"/><text class="lbl" x="825" y="340" style="font-size:12px">VDC2 无人机</text>
  <rect class="vdc" x="960" y="310" width="130" height="50" rx="8"/><text class="lbl" x="975" y="340" style="font-size:12px">VDC3 机器人</text>
  <rect class="panel" x="40" y="650" width="1120" height="80" rx="14"/>
  <text class="lbl" x="60" y="690" style="font-size:15px">组合层 Exchange Bundle · 见 bundle.md</text>
</svg>""",
}


def main() -> None:
    for name, content in SVG.items():
        path = ROOT / name
        path.write_text(content, encoding="utf-8")
        read_back = path.read_text(encoding="utf-8")
        assert len(read_back) > 200
        print("wrote", name)


if __name__ == "__main__":
    main()
