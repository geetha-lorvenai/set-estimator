"""Deterministic, rule-based cost calculation.

Pricing rules (all driven by ``app.catalog``):

* material line  = quantity x unit_price
* labor line     = workers x days x daily_rate
* surcharge      = material_cost x complexity rate
* bulk discount  = material_cost x discount_percent, only when
                   material_cost is strictly greater than the threshold
* total          = material_cost + surcharge - bulk_discount + labor_cost

The surcharge and the discount are both calculated on the undiscounted total
material cost, so the result does not depend on the order they are applied.
All arithmetic uses ``Decimal`` and rounds half-up to cents.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from app.catalog import BULK_DISCOUNT, COMPLEXITY_SURCHARGE, LABOR, MATERIALS

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(value: float | int | str | Decimal) -> Decimal:
    """Convert without inheriting binary float noise (50.1 -> Decimal('50.1'))."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


class PricingError(ValueError):
    """Raised when an item cannot be priced with the catalogue."""


@dataclass(frozen=True)
class MaterialItem:
    material: str
    quantity: Decimal


@dataclass(frozen=True)
class LaborItem:
    role: str
    days: Decimal
    workers: int = 1


@dataclass(frozen=True)
class MaterialLine:
    material: str
    category: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class LaborLine:
    role: str
    workers: int
    days: Decimal
    person_days: Decimal
    daily_rate: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class CostSummary:
    material_cost: Decimal
    complexity: str
    complexity_surcharge_rate: Decimal
    complexity_surcharge: Decimal
    bulk_discount_threshold: Decimal
    bulk_discount_rate: Decimal
    bulk_discount_applied: bool
    bulk_discount: Decimal
    adjusted_material_cost: Decimal
    labor_cost: Decimal
    total: Decimal


@dataclass(frozen=True)
class CostBreakdown:
    materials: list[MaterialLine]
    labor: list[LaborLine]
    summary: CostSummary
    material_cost_by_category: dict[str, Decimal] = field(default_factory=dict)
    labor_cost_by_role: dict[str, Decimal] = field(default_factory=dict)


def _price_material(item: MaterialItem) -> MaterialLine:
    spec = MATERIALS.get(item.material)
    if spec is None:
        raise PricingError(f"Unknown material: {item.material!r}")
    quantity = to_decimal(item.quantity)
    if quantity <= 0:
        raise PricingError(f"Quantity for {item.material} must be positive, got {quantity}")
    unit_price = money(to_decimal(spec["unit_price"]))
    return MaterialLine(
        material=item.material,
        category=spec["category"],
        unit=spec["unit"],
        quantity=quantity,
        unit_price=unit_price,
        line_total=money(quantity * unit_price),
    )


def _price_labor(item: LaborItem) -> LaborLine:
    spec = LABOR.get(item.role)
    if spec is None:
        raise PricingError(f"Unknown labor role: {item.role!r}")
    days = to_decimal(item.days)
    if days <= 0:
        raise PricingError(f"Days for {item.role} must be positive, got {days}")
    if item.workers < 1:
        raise PricingError(f"Workers for {item.role} must be at least 1, got {item.workers}")
    daily_rate = money(to_decimal(spec["daily_rate"]))
    person_days = days * item.workers
    return LaborLine(
        role=item.role,
        workers=item.workers,
        days=days,
        person_days=person_days,
        daily_rate=daily_rate,
        line_total=money(person_days * daily_rate),
    )


def calculate(
    materials: Iterable[MaterialItem],
    labor: Iterable[LaborItem],
    complexity: str,
) -> CostBreakdown:
    if complexity not in COMPLEXITY_SURCHARGE:
        raise PricingError(f"Unknown complexity: {complexity!r}")

    material_lines = [_price_material(m) for m in materials]
    labor_lines = [_price_labor(item) for item in labor]

    material_cost = money(sum((line.line_total for line in material_lines), ZERO))
    labor_cost = money(sum((line.line_total for line in labor_lines), ZERO))

    surcharge_rate = to_decimal(COMPLEXITY_SURCHARGE[complexity]["surcharge"])
    surcharge = money(material_cost * surcharge_rate)

    threshold = money(to_decimal(BULK_DISCOUNT["threshold"]))
    discount_rate = to_decimal(BULK_DISCOUNT["discount_percent"]) / Decimal(100)
    discount_applied = material_cost > threshold
    discount = money(material_cost * discount_rate) if discount_applied else ZERO

    adjusted_material_cost = money(material_cost + surcharge - discount)
    total = money(adjusted_material_cost + labor_cost)

    by_category: dict[str, Decimal] = OrderedDict()
    for line in material_lines:
        by_category[line.category] = by_category.get(line.category, ZERO) + line.line_total

    by_role: dict[str, Decimal] = OrderedDict()
    for line in labor_lines:
        by_role[line.role] = by_role.get(line.role, ZERO) + line.line_total

    return CostBreakdown(
        materials=material_lines,
        labor=labor_lines,
        material_cost_by_category=dict(by_category),
        labor_cost_by_role=dict(by_role),
        summary=CostSummary(
            material_cost=material_cost,
            complexity=complexity,
            complexity_surcharge_rate=surcharge_rate,
            complexity_surcharge=surcharge,
            bulk_discount_threshold=threshold,
            bulk_discount_rate=discount_rate,
            bulk_discount_applied=discount_applied,
            bulk_discount=discount,
            adjusted_material_cost=adjusted_material_cost,
            labor_cost=labor_cost,
            total=total,
        ),
    )
