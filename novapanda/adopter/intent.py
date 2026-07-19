"""IntentMap：轻量确认 / 异议 → Exchange 操作名（签仍在本地 Client）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class IntentMatch:
    action: str  # confirm | dispute | verify | export | status
    reason: str = ""
    confidence: float = 1.0
    raw: str = ""


# 顺序：更具体的模式在前
_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("dispute", re.compile(
        r"^(不对|有异议|拒绝|dispute|reject|不对劲|电量不对|金额不对)",
        re.I,
    ), "user_dispute"),
    ("confirm", re.compile(
        r"^(确认|同意|ok|okay|confirm|settled?|没问题|可以结算)",
        re.I,
    ), ""),
    ("verify", re.compile(r"^(验收|verify|检查交付)", re.I), ""),
    ("export", re.compile(r"^(导出|export|仲裁包)", re.I), ""),
    ("status", re.compile(r"^(状态|status|查一下)", re.I), ""),
]


class IntentMap:
    """将自然语言 / 一键文案映射为协议动作。"""

    def parse(self, text: str) -> Optional[IntentMatch]:
        raw = (text or "").strip()
        if not raw:
            return None
        for action, pat, default_reason in _PATTERNS:
            m = pat.search(raw)
            if not m:
                continue
            reason = default_reason
            if action == "dispute":
                # 允许「不对：少了字段」
                if ":" in raw or "：" in raw:
                    reason = re.split(r"[:：]", raw, maxsplit=1)[1].strip() or default_reason
                elif len(raw) > m.end():
                    reason = raw[m.end():].strip(" ：:") or default_reason
            return IntentMatch(action=action, reason=reason, raw=raw)
        return None

    def require(self, text: str) -> IntentMatch:
        hit = self.parse(text)
        if hit is None:
            raise ValueError(f"无法识别意图: {text!r}")
        return hit

    def describe(self) -> list[dict[str, Any]]:
        return [
            {"action": "confirm", "examples": ["确认", "ok", "没问题"]},
            {"action": "dispute", "examples": ["不对", "有异议：少了 currency"]},
            {"action": "verify", "examples": ["验收", "verify"]},
            {"action": "export", "examples": ["导出", "仲裁包"]},
            {"action": "status", "examples": ["状态", "查一下"]},
        ]
