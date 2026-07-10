"""W3C traceparent helpers — informative; never in VDC signature scope."""

from __future__ import annotations

import os
import re
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Mapping, Optional

_TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$", re.IGNORECASE)
_CORR_RE = re.compile(r"(?:^|,)np=corr:([^,]+)")

_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar("np_trace", default=None)


def trace_enabled() -> bool:
    return os.environ.get("NOVAPANDA_TRACE", "1").strip().lower() not in ("0", "false", "no")


@dataclass(frozen=True)
class TraceContext:
    traceparent: str
    tracestate: Optional[str] = None
    correlation_id: Optional[str] = None

    def to_extensions(self) -> dict[str, str]:
        out: dict[str, str] = {"traceparent": self.traceparent}
        if self.tracestate:
            out["tracestate"] = self.tracestate
        if self.correlation_id:
            out["correlation_id"] = self.correlation_id
        return out

    def to_storage(self) -> dict[str, str]:
        return self.to_extensions()


def _new_trace_id() -> str:
    return secrets.token_hex(16)


def _new_span_id() -> str:
    return secrets.token_hex(8)


def _format_traceparent(trace_id: str, span_id: str) -> str:
    return f"00-{trace_id.lower()}-{span_id.lower()}-01"


def parse_traceparent(value: str) -> Optional[tuple[str, str]]:
    m = _TRACEPARENT_RE.match(value.strip())
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower()


def parse_correlation_from_tracestate(tracestate: Optional[str]) -> Optional[str]:
    if not tracestate:
        return None
    m = _CORR_RE.search(tracestate)
    return m.group(1) if m else None


def merge_tracestate(existing: Optional[str], correlation_id: str) -> str:
    fragment = f"np=corr:{correlation_id}"
    if not existing:
        return fragment
    if fragment in existing:
        return existing
    return f"{existing},{fragment}"


def from_headers(
    headers: Mapping[str, str],
    *,
    body_correlation_id: Optional[str] = None,
) -> Optional[TraceContext]:
    if not trace_enabled():
        return None

    raw_tp = headers.get("traceparent") or headers.get("Traceparent")
    raw_ts = headers.get("tracestate") or headers.get("Tracestate")

    if raw_tp:
        parsed = parse_traceparent(raw_tp)
        if parsed:
            trace_id, _ = parsed
            tp = _format_traceparent(trace_id, _new_span_id())
        else:
            tp = _format_traceparent(_new_trace_id(), _new_span_id())
    else:
        tp = _format_traceparent(_new_trace_id(), _new_span_id())

    corr = body_correlation_id or parse_correlation_from_tracestate(raw_ts)
    ts = raw_ts
    if body_correlation_id:
        ts = merge_tracestate(raw_ts, body_correlation_id)
    elif corr and (not raw_ts or "np=corr:" not in raw_ts):
        ts = merge_tracestate(raw_ts, corr)

    return TraceContext(traceparent=tp, tracestate=ts, correlation_id=corr)


def set_current_trace(ctx: Optional[TraceContext]) -> None:
    _current_trace.set(ctx)


def get_current_trace() -> Optional[TraceContext]:
    return _current_trace.get()


def outbound_headers() -> dict[str, str]:
    ctx = get_current_trace()
    if ctx is None or not trace_enabled():
        return {}
    headers = {"traceparent": ctx.traceparent}
    if ctx.tracestate:
        headers["tracestate"] = ctx.tracestate
    return headers


def attach_trace_extensions(payload: dict[str, Any], trace_context: Optional[dict[str, str]]) -> dict[str, Any]:
    if not trace_enabled() or not trace_context:
        return payload
    out = dict(payload)
    out.pop("trace_context", None)
    out["extensions"] = {"trace": trace_context}
    return out


def exchange_to_dict(ex: Any) -> dict[str, Any]:
    from dataclasses import asdict

    payload = asdict(ex)
    tc = payload.pop("trace_context", None)
    return attach_trace_extensions(payload, tc)
