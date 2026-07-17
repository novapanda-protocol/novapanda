"""任务拆解：大任务 → 带依赖的子任务 DAG。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novapanda.hashing import sha256_hex

from .types import SubTask, SubTaskGraph, TaskSpec


@dataclass
class HeuristicTaskDispatcher:
    """Split a goal into a subtask DAG (chain or parallel).

    Strategy (v0):
    1. Non-empty ``spec.steps`` → one subtask per step, chained ``depends_on``;
    2. List payload (or dict ``parts``/``stages``) → parallel subtasks;
    3. Otherwise a single pass-through task.

    Agent Skill: ``novapanda_split_task`` returns a compact graph (no bulky
    payloads unless ``include_payloads=true``).
    """

    default_tokens_per_step: int = 400

    def split_task(self, spec: TaskSpec) -> SubTaskGraph:
        """Build ``SubTaskGraph`` from ``TaskSpec``. Pure / no IO."""
        if spec.steps:
            tasks = self._from_steps(spec)
        else:
            parts = self._extract_parts(spec.payload)
            if parts is not None and len(parts) > 1:
                tasks = self._from_parts(spec, parts, parallel=True)
            elif parts is not None and len(parts) == 1:
                tasks = self._from_parts(spec, parts, parallel=True)
            else:
                tasks = (
                    SubTask(
                        sub_id=self._sid(spec.goal_id, "main"),
                        resource_type=spec.resource_type,
                        payload=spec.payload,
                        depends_on=(),
                        token_estimate=self._estimate_tokens(spec.payload),
                        step_estimate=1,
                        required_tags=spec.required_tags,
                    ),
                )
        return SubTaskGraph(goal_id=spec.goal_id, tasks=tasks)

    def _from_steps(self, spec: TaskSpec) -> tuple[SubTask, ...]:
        out: list[SubTask] = []
        prev: str | None = None
        for i, step in enumerate(spec.steps):
            sid = self._sid(spec.goal_id, f"step-{i}")
            payload = step.get("payload", step)
            rtype = str(step.get("resource_type") or spec.resource_type)
            tags = tuple(step.get("tags") or spec.required_tags)
            tokens = int(step.get("token_estimate") or self._estimate_tokens(payload))
            out.append(
                SubTask(
                    sub_id=sid,
                    resource_type=rtype,
                    payload=payload,
                    depends_on=(prev,) if prev else (),
                    token_estimate=tokens,
                    step_estimate=1,
                    required_tags=tags,
                    rule_id_hint=step.get("rule_id"),
                )
            )
            prev = sid
        return tuple(out)

    def _from_parts(
        self, spec: TaskSpec, parts: list[Any], *, parallel: bool
    ) -> tuple[SubTask, ...]:
        out: list[SubTask] = []
        prev: str | None = None
        for i, part in enumerate(parts):
            sid = self._sid(spec.goal_id, f"part-{i}")
            deps = () if parallel else ((prev,) if prev else ())
            out.append(
                SubTask(
                    sub_id=sid,
                    resource_type=spec.resource_type,
                    payload=part,
                    depends_on=deps,
                    token_estimate=self._estimate_tokens(part),
                    step_estimate=1,
                    required_tags=spec.required_tags,
                )
            )
            prev = sid
        return tuple(out)

    def _extract_parts(self, payload: Any) -> list[Any] | None:
        if isinstance(payload, list):
            return list(payload)
        if isinstance(payload, dict):
            for key in ("parts", "stages", "items", "chunks"):
                if isinstance(payload.get(key), list):
                    return list(payload[key])
        return None

    def _estimate_tokens(self, payload: Any) -> int:
        if payload is None:
            return self.default_tokens_per_step
        if isinstance(payload, str):
            return max(1, len(payload) // 4)
        if isinstance(payload, dict):
            text = str(payload.get("text") or payload.get("content") or payload)
            return max(1, len(text) // 4)
        return max(1, len(str(payload)) // 4)

    def _sid(self, goal_id: str, suffix: str) -> str:
        return "sub-" + sha256_hex(f"{goal_id}|{suffix}".encode())[:12]
