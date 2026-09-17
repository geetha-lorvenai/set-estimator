"""Pricing catalogue, copied verbatim from the candidate brief.

These are the single source of truth for all pricing rules. Nothing else in
the codebase hard-codes a price, rate, surcharge or threshold.
"""

MATERIALS = {
    "timber": {"unit_price": 50.00, "unit": "per_sheet", "category": "structural"},
    "drywall": {"unit_price": 30.00, "unit": "per_sheet", "category": "structural"},
    "paint": {"unit_price": 25.00, "unit": "per_litre", "category": "finish"},
    "wallpaper": {"unit_price": 40.00, "unit": "per_roll", "category": "finish"},
    "flooring": {"unit_price": 60.00, "unit": "per_sqm", "category": "finish"},
    "electrical_fit": {"unit_price": 120.00, "unit": "per_point", "category": "electrical"},
    "scenic_backdrop": {"unit_price": 200.00, "unit": "per_panel", "category": "scenic"},
    "prop_furniture": {"unit_price": 150.00, "unit": "per_piece", "category": "scenic"},
}

LABOR = {
    "carpenter": {"daily_rate": 180.00},
    "painter": {"daily_rate": 120.00},
    "electrician": {"daily_rate": 200.00},
    "scenic_artist": {"daily_rate": 160.00},
}

COMPLEXITY_SURCHARGE = {
    "simple": {"surcharge": 0.00},
    "moderate": {"surcharge": 0.15},  # 15% of total material cost
    "complex": {"surcharge": 0.30},  # 30% of total material cost
}

BULK_DISCOUNT = {
    "threshold": 5000.00,  # applies when material cost exceeds this
    "discount_percent": 8,
}

DEFAULT_COMPLEXITY = "simple"

# Units that can only be bought in whole numbers.
DISCRETE_UNITS = frozenset({"per_sheet", "per_roll", "per_point", "per_panel", "per_piece"})
