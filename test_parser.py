from decimal import Decimal

import pytest

from app.parser import normalize, parse_request

SAMPLE = (
    "Build a moderate complexity living room set with 10 sheets of drywall, 20 litres of paint, "
    "30sqm of flooring, 2 scenic backdrops, and 2 days of carpenter and painter labor"
)


def materials(result):
    return {m.material: m.quantity for m in result.materials}


def labor(result):
    return {item.role: (item.workers, item.days) for item in result.labor}


def test_sample_input():
    result = parse_request(SAMPLE)
    assert result.set_name == "Living Room"
    assert result.complexity == "moderate"
    assert result.complexity_detected is True
    assert materials(result) == {"drywall": 10, "paint": 20, "flooring": 30, "scenic_backdrop": 2}
    assert labor(result) == {"carpenter": (1, 2), "painter": (1, 2)}
    assert result.warnings == []


@pytest.mark.parametrize(
    "text",
    [
        "I need a medium complexity living room set: drywall x10, paint 20L, flooring 30 m2, "
        "backdrops: 2. Carpenter and painter for 2 days.",
        "Moderately complex living room set - ten sheets of plasterboard, twenty litres of paint, "
        "30 square metres of flooring, two scenic backdrops; 2 days each of carpentry and painting",
        "Living room set (complexity: moderate)\n- 10 drywall sheets\n- 20 liters paint\n"
        "- 30 sq m flooring\n- 2 backdrop panels\n- carpenter: 2 days\n- painter: 2 days",
    ],
)
def test_wording_variations_parse_to_the_same_request(text):
    result = parse_request(text)
    assert result.complexity == "moderate"
    assert materials(result) == {"drywall": 10, "paint": 20, "flooring": 30, "scenic_backdrop": 2}
    assert labor(result) == {"carpenter": (1, 2), "painter": (1, 2)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a complex set with 5 sheets of timber", "complex"),
        ("highly complex set, 5 sheets of timber", "complex"),
        ("high complexity set with 5 sheets of timber", "complex"),
        ("simple set with 5 sheets of timber", "simple"),
        ("low complexity set with 5 sheets of timber", "simple"),
        ("fairly complex set with 5 sheets of timber", "moderate"),
        ("complexity: moderate. 5 sheets of timber", "moderate"),
        ("an elaborate castle set with 5 sheets of timber", "complex"),
    ],
)
def test_complexity_detection(text, expected):
    assert parse_request(text).complexity == expected


def test_missing_complexity_defaults_to_simple_with_warning():
    result = parse_request("5 sheets of timber")
    assert result.complexity == "simple"
    assert result.complexity_detected is False
    assert any("defaulted to simple" in w for w in result.warnings)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2 carpenters for 3 days", {"carpenter": (2, 3)}),
        ("a carpenter and 2 painters for 4 days", {"carpenter": (1, 4), "painter": (2, 4)}),
        ("3 painter days", {"painter": (1, 3)}),
        ("electrician: 1 day, scenic artist x 2 days", {"electrician": (1, 1), "scenic_artist": (1, 2)}),
        ("a day of electrician work", {"electrician": (1, 1)}),
        ("a scenic artist for half a day", {"scenic_artist": (1, Decimal("0.5"))}),
        ("one gaffer for 2 days", {"electrician": (1, 2)}),
        ("2 days of carpenter, painter and electrician labour", {
            "carpenter": (1, 2), "painter": (1, 2), "electrician": (1, 2)}),
    ],
)
def test_labor_phrasings(text, expected):
    assert labor(parse_request(text)) == expected


def test_roles_without_own_duration_use_overall_duration():
    result = parse_request("Kitchen set with 4 sheets of timber. Crew: carpenter, painter. Build over 3 days.")
    assert labor(result) == {"carpenter": (1, 3), "painter": (1, 3)}
    assert any("overall duration" in w for w in result.warnings)


def test_role_without_any_duration_is_reported_not_costed():
    result = parse_request("5 sheets of timber and a carpenter")
    assert result.labor == []
    assert any("no number of days" in w for w in result.warnings)


def test_repeated_role_with_different_days_is_combined():
    result = parse_request("carpenter 2 days, painter 1 day, carpenter 1 day")
    assert labor(result) == {"carpenter": (1, 3), "painter": (1, 1)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12 sheets of plywood", {"timber": 12}),
        ("6 rolls of wallpaper", {"wallpaper": 6}),
        ("4 electrical points and 3 power outlets", {"electrical_fit": 7}),
        ("half a dozen prop furniture pieces", {"prop_furniture": 6}),
        ("3 pieces of furniture", {"prop_furniture": 3}),
        ("a scenic backdrop", {"scenic_backdrop": 1}),
        ("paint: 15 l", {"paint": 15}),
        ("1,200 litres of paint", {"paint": 1200}),
        ("twenty five sqm of hardwood flooring", {"flooring": 25}),
        ("12.5 m2 of flooring", {"flooring": Decimal("12.5")}),
        ("prop_furniture x 2, electrical_fit x 3", {"prop_furniture": 2, "electrical_fit": 3}),
    ],
)
def test_material_phrasings(text, expected):
    assert materials(parse_request(text)) == expected


def test_quantity_never_leaks_between_items():
    result = parse_request("drywall 10 paint 20")
    assert materials(result) == {"drywall": 10, "paint": 20}


def test_paint_is_not_confused_with_painter():
    result = parse_request("20 litres of paint and 2 days of painter labor")
    assert materials(result) == {"paint": 20}
    assert labor(result) == {"painter": (1, 2)}


def test_discrete_units_are_rounded_up_with_warning():
    result = parse_request("2.5 scenic backdrops")
    assert materials(result) == {"scenic_backdrop": 3}
    assert any("rounded 2.5 up to 3" in w for w in result.warnings)


def test_unit_mismatch_is_flagged():
    result = parse_request("10 rolls of drywall")
    assert materials(result) == {"drywall": 10}
    assert any("priced per sheet" in w for w in result.warnings)


def test_unknown_items_are_reported():
    result = parse_request("5 chandeliers and 2 sheets of timber")
    assert materials(result) == {"timber": 2}
    assert any("5 chandeliers" in w for w in result.warnings)


def test_material_without_quantity_is_reported():
    result = parse_request("some paint and 3 sheets of timber")
    assert materials(result) == {"timber": 3}
    assert any("'paint'" in w for w in result.warnings)


def test_nothing_priceable_is_empty():
    assert parse_request("please make it look nice").is_empty


@pytest.mark.parametrize(
    ("text", "name"),
    [
        (SAMPLE, "Living Room"),
        ("Build a western saloon set with 3 sheets of timber", "Western Saloon"),
        ("5 sheets of timber", None),
    ],
)
def test_set_name(text, name):
    assert parse_request(text).set_name == name


def test_normalize_units_and_numbers():
    assert normalize("Thirty-Two SQ. M and 5L") == "32 sqm and 5 litres"
