"""生态适配器登记：社区 adapters/ 的机器可读索引。

不改变 CORE；适配器只翻译到 surfaces / SDK / Adopter。
"""

from .registry import AdapterManifest, iter_adapters, load_adapter, list_adapter_summaries

__all__ = [
    "AdapterManifest",
    "iter_adapters",
    "load_adapter",
    "list_adapter_summaries",
]
