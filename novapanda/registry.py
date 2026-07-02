"""注册表：资源本体（Ontology）与规则（Rule）。

本体与规则是「共域·可扩展」的语义层：任何人可提交新类型/新规则，
节点只是发布与解析它们，不拥有、不垄断语义。
默认从 `spec/ontology.v0.json` / `spec/rules.v0.json` 加载。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

# 包内 spec 默认路径（相对仓库根）
_PKG_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ONTOLOGY_PATH = _PKG_ROOT / "spec" / "ontology.v0.json"
DEFAULT_RULES_PATH = _PKG_ROOT / "spec" / "rules.v0.json"


class OntologyRegistry:
    """资源类型注册表，如 data.extraction.structured / energy.electric.dc。"""

    def __init__(self) -> None:
        self._types: dict[str, dict] = {}

    def register(self, type_id: str, *, unit: str, description: str = "",
                 **extra) -> dict:
        entry = {"type_id": type_id, "unit": unit, "description": description, **extra}
        self._types[type_id] = entry
        return entry

    def get(self, type_id: str) -> Optional[dict]:
        return self._types.get(type_id)

    def list(self) -> list[dict]:
        return list(self._types.values())

    @classmethod
    def load(cls, source: Union[str, Path]) -> "OntologyRegistry":
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        reg = cls()
        for t in data.get("types", []):
            tid = t["type_id"]
            reg._types[tid] = dict(t)
        return reg


class RuleRegistry:
    """验收规则注册表：rule_id -> {rule_id, resource_type, schema, ...}。"""

    def __init__(self) -> None:
        self._rules: dict[str, dict] = {}

    def register(self, rule: dict) -> dict:
        if "rule_id" not in rule:
            raise ValueError("rule 缺少 rule_id")
        self._rules[rule["rule_id"]] = rule
        return rule

    def get(self, rule_id: str) -> Optional[dict]:
        return self._rules.get(rule_id)

    def list(self) -> list[dict]:
        return list(self._rules.values())

    @classmethod
    def load(cls, source: Union[str, Path]) -> "RuleRegistry":
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        reg = cls()
        for r in data.get("rules", []):
            reg.register(r)
        return reg


def load_default_registries(
    ontology_path: Optional[Union[str, Path]] = None,
    rules_path: Optional[Union[str, Path]] = None,
) -> tuple[OntologyRegistry, RuleRegistry]:
    """加载 spec 目录下的 v0 注册表（可被节点配置覆盖路径）。"""
    return (
        OntologyRegistry.load(ontology_path or DEFAULT_ONTOLOGY_PATH),
        RuleRegistry.load(rules_path or DEFAULT_RULES_PATH),
    )


def load_or_seed_registries(
    store,
    ontology_path: Optional[Union[str, Path]] = None,
    rules_path: Optional[Union[str, Path]] = None,
) -> tuple[OntologyRegistry, RuleRegistry]:
    """从持久化 store 加载注册表；空库时从 JSON 种子并写入 store。"""
    if hasattr(store, "registry_load"):
        loaded = store.registry_load()
        if loaded is not None:
            return loaded
    onto, rules = load_default_registries(ontology_path, rules_path)
    if hasattr(store, "registry_save"):
        store.registry_save(onto, rules)
    return onto, rules
