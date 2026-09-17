"""Request / response models (the public API contract)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

# Money is computed with Decimal and serialised as a JSON number.
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
Quantity = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
Rate = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
Complexity = Literal["simple", "moderate", "complex"]

SAMPLE_REQUEST = (
    "Build a moderate complexity living room set with 10 sheets of drywall, 20 litres of paint, "
    "30sqm of flooring, 2 scenic backdrops, and 2 days of carpenter and painter labor"
)


class EstimateRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"text": SAMPLE_REQUEST}]})

    text: str = Field(..., min_length=3, max_length=2000, description="Plain-English construction request")

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("text must contain at least 3 non-space characters")
        return value


class MaterialLineOut(BaseModel):
    material: str
    category: str
    unit: str
    quantity: Quantity
    unit_price: Money
    line_total: Money


class LaborLineOut(BaseModel):
    role: str
    workers: int
    days: Quantity
    person_days: Quantity
    daily_rate: Money
    line_total: Money


class CostSummaryOut(BaseModel):
    material_cost: Money
    complexity: Complexity
    complexity_surcharge_rate: Rate = Field(description="Fraction of material cost, e.g. 0.15")
    complexity_surcharge: Money
    bulk_discount_threshold: Money
    bulk_discount_rate: Rate = Field(description="Fraction of material cost, e.g. 0.08")
    bulk_discount_applied: bool
    bulk_discount: Money
    adjusted_material_cost: Money
    labor_cost: Money
    total: Money


class EstimateOut(BaseModel):
    id: str
    created_at: datetime
    raw_input: str
    set_name: str | None
    complexity: Complexity
    complexity_detected: bool
    materials: list[MaterialLineOut]
    labor: list[LaborLineOut]
    material_cost_by_category: dict[str, Money]
    labor_cost_by_role: dict[str, Money]
    summary: CostSummaryOut
    warnings: list[str]


class EstimateListOut(BaseModel):
    items: list[EstimateOut]
    total: int
    limit: int
    offset: int


class ErrorOut(BaseModel):
    detail: str | dict | list
