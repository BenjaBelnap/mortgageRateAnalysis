"""Helpers for turning raw lender text into structured, canonical values.

Kept adapter-agnostic and pure (no I/O) so it is trivially unit-testable and
guarantees determinism: identical raw input always yields identical output.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from mortgage_rates.models import LoanAttributes

_PERCENT_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_percent(raw: str | float | Decimal) -> Decimal:
    """Parse a rate/APR/points figure like '6.375%' or '6.375' into a Decimal."""
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    match = _PERCENT_RE.search(raw)
    if not match:
        raise ValueError(f"Could not parse a numeric rate from {raw!r}")
    try:
        return Decimal(match.group())
    except InvalidOperation as exc:
        raise ValueError(f"Could not parse a numeric rate from {raw!r}") from exc


def loan_attributes_from_label(label: str, mapping: dict[str, dict]) -> LoanAttributes:
    """Look up a raw product label in a lender's configured mapping.

    `mapping` comes from lenders.yaml's `product_map` block: raw label ->
    dict of LoanAttributes fields. Keeps adapters free of hardcoded product
    logic — all label interpretation lives in config.
    """
    key = label.strip()
    if key not in mapping:
        raise KeyError(f"Unrecognized product label {label!r}; add it to lenders.yaml product_map")
    return LoanAttributes(**mapping[key])
