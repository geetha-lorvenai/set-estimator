from decimal import Decimal

import pytest

from app.calculator import LaborItem, MaterialItem, PricingError, calculate

D = Decimal


def test_sample_brief_estimate():
    result = calculate(
        [
            MaterialItem("drywall", D(10)),
            MaterialItem("paint", D(20)),
            MaterialItem("flooring", D(30)),
            MaterialItem("scenic_backdrop", D(2)),
        ],
        [LaborItem("carpenter", D(2)), LaborItem("painter", D(2))],
        "moderate",
    )
    s = result.summary
    assert s.material_cost == D("3000.00")
    assert s.complexity_surcharge == D("450.00")
    assert s.bulk_discount_applied is False
    assert s.bulk_discount == D("0.00")
    assert s.labor_cost == D("600.00")
    assert s.total == D("4050.00")
    assert result.material_cost_by_category == {
        "structural": D("300.00"),
        "finish": D("2300.00"),
        "scenic": D("400.00"),
    }
    assert result.labor_cost_by_role == {"carpenter": D("360.00"), "painter": D("240.00")}


def test_line_items_are_priced_from_catalogue():
    result = calculate([MaterialItem("electrical_fit", D(3))], [LaborItem("electrician", D("1.5"), workers=2)], "simple")
    material, labor = result.materials[0], result.labor[0]
    assert (material.unit_price, material.line_total, material.category) == (D("120.00"), D("360.00"), "electrical")
    assert (labor.person_days, labor.daily_rate, labor.line_total) == (D("3.0"), D("200.00"), D("600.00"))


@pytest.mark.parametrize(
    ("complexity", "surcharge"),
    [("simple", D("0.00")), ("moderate", D("150.00")), ("complex", D("300.00"))],
)
def test_complexity_surcharge_applies_to_material_cost_only(complexity, surcharge):
    result = calculate([MaterialItem("timber", D(20))], [LaborItem("carpenter", D(10))], complexity)
    assert result.summary.complexity_surcharge == surcharge
    assert result.summary.total == D("1000.00") + surcharge + D("1800.00")


def test_bulk_discount_not_applied_at_threshold():
    result = calculate([MaterialItem("timber", D(100))], [], "simple")  # exactly 5000
    assert result.summary.bulk_discount_applied is False
    assert result.summary.total == D("5000.00")


def test_bulk_discount_applied_above_threshold_with_surcharge():
    result = calculate([MaterialItem("timber", D(101))], [LaborItem("carpenter", D(1))], "complex")
    s = result.summary
    assert s.material_cost == D("5050.00")
    assert s.complexity_surcharge == D("1515.00")
    assert s.bulk_discount_applied is True
    assert s.bulk_discount == D("404.00")
    assert s.adjusted_material_cost == D("6161.00")
    assert s.total == D("6341.00")


def test_labor_cost_does_not_trigger_bulk_discount():
    result = calculate([MaterialItem("paint", D(1))], [LaborItem("electrician", D(100))], "simple")
    assert result.summary.bulk_discount_applied is False


def test_fractional_quantities_round_half_up_to_cents():
    result = calculate([MaterialItem("paint", D("0.123"))], [], "moderate")
    assert result.materials[0].line_total == D("3.08")  # 3.075 -> 3.08
    assert result.summary.complexity_surcharge == D("0.46")  # 0.462


def test_empty_request_totals_zero():
    assert calculate([], [], "simple").summary.total == D("0.00")


@pytest.mark.parametrize(
    ("materials", "labor", "complexity"),
    [
        ([MaterialItem("marble", D(1))], [], "simple"),
        ([MaterialItem("paint", D(0))], [], "simple"),
        ([], [LaborItem("gaffer", D(1))], "simple"),
        ([], [LaborItem("painter", D(-1))], "simple"),
        ([], [LaborItem("painter", D(1), workers=0)], "simple"),
        ([], [], "extreme"),
    ],
)
def test_invalid_inputs_raise(materials, labor, complexity):
    with pytest.raises(PricingError):
        calculate(materials, labor, complexity)
