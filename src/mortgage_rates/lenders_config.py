"""Loads lenders.yaml into LenderConfig objects.

Kept separate from adapters/ so config parsing is a single, testable concern
independent of any particular lender's fetch logic.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mortgage_rates.adapters.base import LenderConfig
from mortgage_rates.models import LenderType


def load_lender_configs(path: Path) -> dict[str, LenderConfig]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    configs: dict[str, LenderConfig] = {}
    for slug, raw in (data.get("lenders") or {}).items():
        configs[slug] = LenderConfig(
            slug=slug,
            name=raw["name"],
            type=LenderType(raw["type"]),
            region=raw.get("region"),
            homepage=raw.get("homepage"),
            rates_url=raw["rates_url"],
            product_map=raw.get("product_map", {}),
            enabled=raw.get("enabled", True),
            row_selector=raw.get("row_selector", "tr"),
            percent_field_order=tuple(raw.get("percent_field_order", ("interest_rate", "apr"))),
        )
    return configs
