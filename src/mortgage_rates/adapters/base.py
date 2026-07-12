"""Adapter contract + self-registering registry.

Adding a new lender = drop a module in this package decorated with
`@register` and a block in lenders.yaml. Nothing else needs to change —
`load_adapters()` discovers every module in this package automatically.
"""

from __future__ import annotations

import datetime as dt
import importlib
import pkgutil
from dataclasses import dataclass
from typing import Protocol

import httpx

from mortgage_rates.models import LenderType, RateObservation


@dataclass(frozen=True)
class LenderConfig:
    slug: str
    name: str
    type: LenderType
    region: str | None
    homepage: str | None
    rates_url: str
    product_map: dict[str, dict]
    enabled: bool = True


@dataclass(frozen=True)
class FetchContext:
    target_date: dt.date
    config: LenderConfig
    http_client: httpx.Client


class LenderAdapter(Protocol):
    slug: str

    def fetch(self, ctx: FetchContext) -> list[RateObservation]: ...


_REGISTRY: dict[str, LenderAdapter] = {}


def register(cls: type[LenderAdapter]) -> type[LenderAdapter]:
    """Class decorator: instantiate and register an adapter by its slug."""
    instance = cls()
    _REGISTRY[instance.slug] = instance
    return cls


def get_registry() -> dict[str, LenderAdapter]:
    return dict(_REGISTRY)


def load_adapters() -> None:
    """Import every module in mortgage_rates.adapters to trigger registration."""
    import mortgage_rates.adapters as adapters_pkg

    for module_info in pkgutil.iter_modules(adapters_pkg.__path__):
        name = module_info.name
        if name in {"base"} or name.startswith("_"):
            continue
        importlib.import_module(f"mortgage_rates.adapters.{name}")
