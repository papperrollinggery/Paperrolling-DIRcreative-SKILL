from __future__ import annotations

from .base import AdapterContractError, PromptAdapter, shared_surface_errors
from .generic import GenericAdapter
from .kling import KlingAdapter
from .runway import RunwayAdapter
from .seedance import SeedanceAdapter
from .sora import SoraAdapter
from .veo import VeoAdapter


ADAPTERS: dict[str, type[PromptAdapter]] = {
    "seedance": SeedanceAdapter,
    "kling": KlingAdapter,
    "runway": RunwayAdapter,
    "sora": SoraAdapter,
    "veo": VeoAdapter,
    "generic": GenericAdapter,
    "gpt_image": GenericAdapter,
}


def get_adapter(name: str) -> PromptAdapter:
    adapter_class = ADAPTERS.get(name)
    if adapter_class is None:
        raise AdapterContractError(f"unsupported_adapter: {name}")
    return adapter_class(adapter_name=name)


__all__ = [
    "AdapterContractError",
    "PromptAdapter",
    "get_adapter",
    "shared_surface_errors",
]
