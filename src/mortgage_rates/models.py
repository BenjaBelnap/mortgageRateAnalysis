"""Core domain models shared by adapters, pipeline, and repository."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class LenderType(StrEnum):
    LOCAL = "local"
    NATIONAL = "national"


class LoanAttributes(BaseModel):
    """The decomposed loan "product" — every dimension a rate can vary on."""

    model_config = ConfigDict(frozen=True)

    loan_term_years: int
    is_fixed: bool = True
    arm_fixed_period_years: int | None = None
    is_fha: bool = False
    is_va: bool = False
    is_usda: bool = False
    is_jumbo: bool = False

    @property
    def product_label(self) -> str:
        if self.is_fha:
            kind = "FHA"
        elif self.is_va:
            kind = "VA"
        elif self.is_usda:
            kind = "USDA"
        elif self.is_jumbo:
            kind = "Jumbo"
        else:
            kind = "Conventional"
        rate_kind = "Fixed" if self.is_fixed else f"{self.arm_fixed_period_years}/1 ARM"
        return f"{kind} {self.loan_term_years}yr {rate_kind}"


class RateObservation(BaseModel):
    """A single lender/product/day rate reading, as produced by an adapter."""

    lender_slug: str
    observed_date: dt.date
    loan: LoanAttributes
    interest_rate: Decimal
    apr: Decimal | None = None
    points: Decimal | None = None
    source_url: str
    fetched_at: dt.datetime
    raw: dict | None = None
