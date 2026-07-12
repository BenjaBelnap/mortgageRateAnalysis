from __future__ import annotations

from mortgage_rates.adapters.base import register
from mortgage_rates.adapters.html_table import HtmlTableLenderAdapter


@register
class GoldenwestAdapter(HtmlTableLenderAdapter):
    slug = "goldenwest"
