"""Rule-based parser: plain-English construction request -> structured items.

No LLM is used. The pipeline is deterministic:

1. ``normalize``      lower-case, number words -> digits, unify units.
2. labor extraction   several phrasings ("2 days of carpenter and painter
                      labor", "2 carpenters for 3 days", "3 painter days",
                      "electrician: 1 day"). Matched text is blanked out.
3. material extraction every alias is matched; its quantity is looked for
                      right before it ("10 sheets of drywall") or right after
                      it ("drywall x 10"), never crossing a clause delimiter
                      or another item.
4. complexity + set name detection.
5. anything numeric that was not understood is reported as a warning, so the
   user can see what was ignored instead of getting a silently wrong total.
"""

from __future__ import annotations

import math
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.calculator import LaborItem, MaterialItem
from app.catalog import DEFAULT_COMPLEXITY, DISCRETE_UNITS, MATERIALS

MAX_QUANTITY = Decimal(100_000)
MAX_DAYS = Decimal(365)
MAX_WORKERS = 500

# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #

MATERIAL_ALIASES: dict[str, list[str]] = {
    "timber": [r"timbers?", r"plywood", r"ply", r"lumber", r"mdf", r"hardboard"],
    "drywall": [
        r"dry\s?walls?",
        r"plaster\s?boards?",
        r"gypsum\s+boards?",
        r"sheet\s?rocks?",
        r"gyprocks?",
    ],
    "paint": [r"paints?", r"emulsion", r"primer"],
    "wallpaper": [r"wall\s?papers?", r"wall\s+coverings?"],
    "flooring": [
        r"flooring",
        r"floor\s?boards?",
        r"floor\s+tiles?",
        r"floors?",
        r"carpet(?:ing)?",
        r"laminate",
    ],
    "electrical_fit": [
        r"electrical\s+(?:fit(?:ting)?s?(?:\s+points?)?|points?|outlets?|connections?)",
        r"electric\s+points?",
        r"power\s+points?",
        r"light(?:ing)?\s+points?",
        r"outlets?",
        r"sockets?",
    ],
    "scenic_backdrop": [
        r"scenic\s+backdrops?(?:\s+panels?)?",
        r"backdrop\s+panels?",
        r"backdrops?",
        r"backcloths?",
        r"cycloramas?",
    ],
    "prop_furniture": [
        r"prop\s+furniture(?:\s+pieces?)?",
        r"pieces?\s+of\s+(?:prop\s+)?furniture",
        r"furniture\s+props?",
        r"furniture(?:\s+pieces?)?",
        r"props?",
    ],
}

LABOR_ALIASES: dict[str, list[str]] = {
    "scenic_artist": [r"scenic\s+artists?", r"scenic\s+painters?"],
    "carpenter": [r"carpenters?", r"carpentry", r"joiners?", r"joinery", r"chippies", r"chippy"],
    "painter": [r"painters?", r"painting"],
    "electrician": [r"electricians?", r"sparks", r"sparkies", r"sparky", r"gaffers?"],
}

UNIT_WORDS = {
    "sheet": "per_sheet",
    "sheets": "per_sheet",
    "board": "per_sheet",
    "boards": "per_sheet",
    "litres": "per_litre",
    "roll": "per_roll",
    "rolls": "per_roll",
    "sqm": "per_sqm",
    "point": "per_point",
    "points": "per_point",
    "panel": "per_panel",
    "panels": "per_panel",
    "piece": "per_piece",
    "pieces": "per_piece",
    "pcs": "per_piece",
}

UNIT_LABELS = {
    "per_sheet": "sheets",
    "per_litre": "litres",
    "per_roll": "rolls",
    "per_sqm": "sqm",
    "per_point": "points",
    "per_panel": "panels",
    "per_piece": "pieces",
}

# Words that may never sit between a quantity and a material name.
_FILLER_STOP = {"day", "days", "hour", "hours", "for", "per", "by", "at", "each", "over"}

_SMALL_NUMBERS = {
    w: i
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen".split()
    )
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def _alternation(words) -> str:
    return "|".join(sorted(words, key=len, reverse=True))


_SMALL_RE = _alternation(_SMALL_NUMBERS)
_TENS_RE = _alternation(_TENS)
_ONES_RE = _alternation([w for w, n in _SMALL_NUMBERS.items() if 1 <= n <= 9])


def _build_alias_regex(table: dict[str, list[str]]) -> tuple[re.Pattern, list[tuple[str, re.Pattern]]]:
    pairs = [(key, pattern) for key, patterns in table.items() for pattern in patterns]
    pairs.sort(key=lambda kp: len(kp[1]), reverse=True)
    combined = re.compile(r"\b(?:" + "|".join(f"(?:{p})" for _, p in pairs) + r")\b")
    lookup = [(key, re.compile(p)) for key, p in pairs]
    return combined, lookup


MATERIAL_RE, _MATERIAL_LOOKUP = _build_alias_regex(MATERIAL_ALIASES)
ROLE_RE, _ROLE_LOOKUP = _build_alias_regex(LABOR_ALIASES)


def _lookup(text: str, table: list[tuple[str, re.Pattern]]) -> str:
    for key, pattern in table:
        if pattern.fullmatch(text):
            return key
    raise KeyError(text)  # pragma: no cover - combined regex guarantees a hit


# --------------------------------------------------------------------------- #
# Labor regexes
# --------------------------------------------------------------------------- #

_ROLE = ROLE_RE.pattern[len(r"\b(?:") : -len(r")\b")]
_ITEM = rf"(?:(?:\d+|an?)\s+)?(?:{_ROLE})"
_SEP = r"\s*(?:,\s*(?:and\s+)?|\band\b|&|\+|/)\s*"
_ROLE_LIST = rf"\b{_ITEM}(?:{_SEP}{_ITEM})*\b"
_LABOR_WORD = r"(?:labor|work|crew|time|services?|hire)"
_DAYS = r"(?P<days>\d+(?:\.\d+)?|an?)\s+(?:full\s+|working\s+|work\s+|build\s+)?days?\b"
_APPROX = r"(?:about\s+|approximately\s+|around\s+|roughly\s+)?"

ITEM_RE = re.compile(rf"\b(?:(?P<count>\d+|an?)\s+)?(?P<alias>{_ROLE})\b")

LABOR_PATTERNS = [
    # "2 days of carpenter and painter labor", "a day of 2 electricians"
    re.compile(rf"\b{_DAYS}\s+(?:of\s+)?(?P<roles>{_ROLE_LIST})(?:\s+{_LABOR_WORD})?"),
    # "3 carpenter days", "4 painter person days"
    re.compile(rf"\b(?P<days>\d+(?:\.\d+)?)\s+(?P<roles>{_ROLE_LIST})\s+(?:(?:person|man|crew)\s+)?days?\b"),
    # "2 carpenters for 3 days", "painter: 2 days", "electrician labor x 1 day"
    re.compile(
        rf"(?P<roles>{_ROLE_LIST})(?:\s+{_LABOR_WORD})?\s*"
        rf"(?:,|:|-|\(|\bx\b|\bfor\b|\bat\b|\bover\b|\bon\s+site\s+for\b)?\s*{_APPROX}\b{_DAYS}"
    ),
]

GLOBAL_DAYS_RE = re.compile(
    rf"\b(?:for|over|lasting|duration(?:\s+of)?|total(?:\s+of)?|across)\s+{_APPROX}{_DAYS}"
)
ANY_DAYS_RE = re.compile(rf"\b{_DAYS}")

# --------------------------------------------------------------------------- #
# Material / complexity / misc regexes
# --------------------------------------------------------------------------- #

DELIM_RE = re.compile(
    r",|;|:(?!\s*\d)|\.(?!\d)|\band\b|\bwith\b|\bplus\b|\bincluding\b|\balso\b|\bthen\b|\bas\s+well\s+as\b"
)
QTY_BEFORE_RE = re.compile(r"(?:^|(?<=\s)|(?<=\())(?P<num>\d+(?:\.\d+)?|an?)\s+(?P<fill>(?:[a-z.']+\s+){0,4})$")
QTY_AFTER_RE = re.compile(
    r"^\s*(?:\bx\b|:|=|-|\(|\bqty\b\.?|\bquantity\b)?\s*(?P<num>\d+(?:\.\d+)?)(?:\s+(?P<unit>[a-z]+))?"
)
LEFTOVER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s+([a-z]+(?:\s+[a-z]+)?)")

COMPLEXITY_RULES: list[tuple[str, re.Pattern]] = [
    (level, re.compile(p))
    for level, p in [
        ("complex", r"\b(?:highly|very|extremely|quite|really)\s+complex\b"),
        ("moderate", r"\b(?:moderately|fairly|somewhat|reasonably|medium)\s+complex\b"),
        ("simple", r"\b(?:not\s+(?:very\s+|too\s+)?complex|low\s+(?:complexity|difficulty))\b"),
        ("moderate", r"\b(?:medium|mid|intermediate|average|standard|moderate)(?:\s+level)?\s+(?:complexity|difficulty)\b"),
        ("complex", r"\b(?:high|complex)(?:\s+level)?\s+(?:complexity|difficulty)\b"),
        ("simple", r"\b(?:simple|basic|easy)(?:\s+level)?\s+(?:complexity|difficulty)\b"),
        ("simple", r"\bcomplexity\s*(?::|=|of|is|level)?\s*(?:simple|low|basic|easy)\b"),
        ("moderate", r"\bcomplexity\s*(?::|=|of|is|level)?\s*(?:moderate|medium|mid)\b"),
        ("complex", r"\bcomplexity\s*(?::|=|of|is|level)?\s*(?:complex|high)\b"),
        ("complex", r"\b(?:complex|complicated|elaborate|intricate)\b"),
        ("moderate", r"\bmoderate\b"),
        ("simple", r"\b(?:simple|basic|straightforward)\b"),
    ]
]

_NAME_STOP = {
    "a", "an", "the", "build", "builds", "construct", "create", "make", "need", "needs", "want",
    "please", "for", "with", "our", "my", "your", "complexity", "level", "difficulty", "moderate",
    "moderately", "simple", "complex", "complicated", "elaborate", "intricate", "basic", "easy",
    "medium", "high", "low", "highly", "very", "fairly", "to", "of", "and", "i", "we", "us", "me",
    "estimate", "quote", "cost", "on", "in", "is", "this", "that",
}


# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #


@dataclass
class ParseResult:
    set_name: str | None
    complexity: str
    complexity_detected: bool
    materials: list[MaterialItem] = field(default_factory=list)
    labor: list[LaborItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.materials and not self.labor


class _Warnings(list):
    def add(self, message: str) -> None:
        if message not in self:
            self.append(message)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def normalize(text: str) -> str:
    t = text.lower()
    t = t.replace("\u00b2", "2").replace("\u00d7", " x ").replace("\u2019", "'").replace("_", " ")
    t = re.sub(r"[\r\n]+", " ; ", t)
    t = re.sub(r"[\u2013\u2014]", " - ", t)
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)  # 1,000 -> 1000
    t = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", t)  # painter-days -> painter days
    t = re.sub(r"(?<=\d)-(?=[a-z])", " ", t)  # 3-day -> 3 day
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)  # 30sqm -> 30 sqm
    t = re.sub(r"\bx(?=\d)", "x ", t)  # x10 -> x 10
    t = re.sub(r"\bm2\b", "sqm", t)
    t = re.sub(r"\bsq(?:uare)?\.?\s*(?:m|met(?:re|er)s?|mtrs?)\b\.?", "sqm", t)
    t = re.sub(r"\b(?:litres?|liters?|ltrs?|lts?)\b", "litres", t)
    t = re.sub(r"(?<=\d )l\b", "litres", t)
    t = re.sub(r"\blabou?rers?\b|\blabour\b", "labor", t)
    t = re.sub(r"\bmen\b|\bpeople\b", "", t)  # "2 carpenter men" noise

    # number words
    t = re.sub(
        rf"\b({_TENS_RE})\s+({_ONES_RE})\b",
        lambda m: str(_TENS[m[1]] + _SMALL_NUMBERS[m[2]]),
        t,
    )
    t = re.sub(
        rf"\b({_TENS_RE}|{_SMALL_RE})\b",
        lambda m: str(_TENS.get(m[1], _SMALL_NUMBERS.get(m[1]))),
        t,
    )
    t = re.sub(r"\bhalf\s+an?\s+dozen\b", "6", t)
    t = re.sub(r"\b(\d+)\s+dozen\b", lambda m: str(int(m[1]) * 12), t)
    t = re.sub(r"\ban?\s+dozen\b", "12", t)
    t = re.sub(r"\b(\d+)\s+hundred\b", lambda m: str(int(m[1]) * 100), t)
    t = re.sub(r"\ba\s+hundred\b", "100", t)
    t = re.sub(r"\ba\s+(?:couple|pair)(?:\s+of)?\b", "2", t)
    t = re.sub(r"\bhalf\s+a\s+day\b", "0.5 day", t)

    return re.sub(r"\s+", " ", t).strip()


def _to_decimal(token: str) -> Decimal | None:
    if token in ("a", "an"):
        return Decimal(1)
    try:
        value = Decimal(token)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _blank(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def _fmt(value: Decimal) -> str:
    return format(value.normalize(), "f")


# --------------------------------------------------------------------------- #
# Extraction steps
# --------------------------------------------------------------------------- #


def _roles_in(roles_text: str) -> list[tuple[str, int]]:
    found = []
    for m in ITEM_RE.finditer(roles_text):
        count = 1 if m["count"] in (None, "a", "an") else int(m["count"])
        found.append((_lookup(m["alias"], _ROLE_LOOKUP), count))
    return found


def _add_labor(items, role, workers, days, warnings) -> None:
    if days is None or days <= 0:
        warnings.add(f"Ignored {role.replace('_', ' ')} labor with a non-positive duration.")
        return
    if days > MAX_DAYS:
        warnings.add(f"Ignored {role.replace('_', ' ')} labor: {_fmt(days)} days exceeds the {MAX_DAYS}-day limit.")
        return
    if not 1 <= workers <= MAX_WORKERS:
        warnings.add(f"Ignored {role.replace('_', ' ')} labor: crew size {workers} is out of range.")
        return
    items.append((role, workers, days))


def _extract_labor(text: str, warnings: _Warnings) -> tuple[list[LaborItem], str]:
    raw: list[tuple[str, int, Decimal]] = []

    for pattern in LABOR_PATTERNS:
        spans = []
        for m in pattern.finditer(text):
            days = _to_decimal(m["days"])
            for role, workers in _roles_in(m["roles"]):
                _add_labor(raw, role, workers, days, warnings)
            spans.append(m.span())
        text = _blank(text, spans)

    # Roles mentioned without their own duration: fall back to an overall duration.
    orphans = list(ITEM_RE.finditer(text))
    if orphans:
        duration = GLOBAL_DAYS_RE.search(text)
        all_days = list(ANY_DAYS_RE.finditer(text))
        if duration is None and len(all_days) == 1:
            duration = all_days[0]
        if duration is not None:
            days = _to_decimal(duration["days"])
            names = []
            for m in orphans:
                role = _lookup(m["alias"], _ROLE_LOOKUP)
                workers = 1 if m["count"] in (None, "a", "an") else int(m["count"])
                _add_labor(raw, role, workers, days, warnings)
                names.append(role.replace("_", " "))
            warnings.add(
                f"Applied the overall duration of {_fmt(days)} day(s) to: {', '.join(dict.fromkeys(names))}."
            )
            text = _blank(text, [m.span() for m in orphans] + [duration.span()])
        else:
            for m in orphans:
                role = _lookup(m["alias"], _ROLE_LOOKUP).replace("_", " ")
                warnings.add(f"'{m.group(0)}' ({role}) has no number of days, so it was not costed.")
            text = _blank(text, [m.span() for m in orphans])

    # Merge repeated roles into a single line.
    merged: OrderedDict[str, list[tuple[int, Decimal]]] = OrderedDict()
    for role, workers, days in raw:
        merged.setdefault(role, []).append((workers, days))

    items: list[LaborItem] = []
    for role, entries in merged.items():
        if len(entries) == 1:
            workers, days = entries[0]
            items.append(LaborItem(role=role, workers=workers, days=days))
            continue
        day_values = {d for _, d in entries}
        if len(day_values) == 1:
            items.append(LaborItem(role=role, workers=sum(w for w, _ in entries), days=day_values.pop()))
        else:
            person_days = sum((w * d for w, d in entries), Decimal(0))
            items.append(LaborItem(role=role, workers=1, days=person_days))
            warnings.add(
                f"{role.replace('_', ' ').capitalize()} was requested more than once; "
                f"combined into {_fmt(person_days)} person-days."
            )
    return items, text


def _extract_materials(text: str, warnings: _Warnings) -> tuple[list[MaterialItem], str]:
    delimiters = [m.span() for m in DELIM_RE.finditer(text)]
    matches = list(MATERIAL_RE.finditer(text))
    totals: OrderedDict[str, Decimal] = OrderedDict()
    consumed: list[tuple[int, int]] = []
    last_consumed_end = 0

    for i, m in enumerate(matches):
        key = _lookup(m.group(0), _MATERIAL_LOOKUP)
        spec_unit = MATERIALS[key]["unit"]

        left = max([e for _, e in delimiters if e <= m.start()] + [last_consumed_end])
        if i > 0:
            left = max(left, matches[i - 1].end())
        right = min([s for s, _ in delimiters if s >= m.end()] + [len(text)])
        if i + 1 < len(matches):
            right = min(right, matches[i + 1].start())

        quantity: Decimal | None = None
        unit_words: list[str] = []
        span: tuple[int, int] | None = None

        before = QTY_BEFORE_RE.search(text[left : m.start()])
        if before:
            fillers = before["fill"].split()
            if not _FILLER_STOP.intersection(fillers):
                quantity = _to_decimal(before["num"])
                unit_words = fillers
                span = (left + before.start("num"), m.end())

        if quantity is None:
            after = QTY_AFTER_RE.match(text[m.end() : right])
            if after and after["unit"] not in ("day", "days", "hour", "hours"):
                quantity = _to_decimal(after["num"])
                unit_words = [after["unit"]] if after["unit"] else []
                span = (m.start(), m.end() + after.end())

        label = key.replace("_", " ")
        if quantity is None or span is None:
            warnings.add(f"'{m.group(0)}' ({label}) was mentioned without a quantity, so it was not costed.")
            continue
        if quantity <= 0:
            warnings.add(f"Ignored {label}: quantity must be greater than zero.")
            consumed.append(span)
            continue
        if quantity > MAX_QUANTITY:
            warnings.add(f"Ignored {label}: quantity {_fmt(quantity)} exceeds the limit of {MAX_QUANTITY}.")
            consumed.append(span)
            continue

        for word in unit_words:
            canonical = UNIT_WORDS.get(word)
            if canonical and canonical != spec_unit:
                warnings.add(
                    f"{label.capitalize()} is priced {spec_unit.replace('_', ' ')}; "
                    f"'{word}' was read as {UNIT_LABELS[spec_unit]}."
                )
                break

        if spec_unit in DISCRETE_UNITS and quantity != quantity.to_integral_value():
            rounded = Decimal(math.ceil(quantity))
            warnings.add(
                f"{label.capitalize()} is sold in whole {UNIT_LABELS[spec_unit]}; "
                f"rounded {_fmt(quantity)} up to {rounded}."
            )
            quantity = rounded

        totals[key] = totals.get(key, Decimal(0)) + quantity
        consumed.append(span)
        last_consumed_end = span[1]

    items = [MaterialItem(material=k, quantity=q) for k, q in totals.items()]
    return items, _blank(text, consumed)


def _detect_complexity(text: str) -> tuple[str, bool]:
    for level, pattern in COMPLEXITY_RULES:
        if pattern.search(text):
            return level, True
    return DEFAULT_COMPLEXITY, False


def _detect_set_name(text: str) -> str | None:
    for m in re.finditer(r"\bset\b(?!\s+(?:of|up|design|dressing)\b)", text):
        words = re.sub(r"[^a-z' ]", " ", text[: m.start()]).split()
        name: list[str] = []
        for word in reversed(words):
            if word in _NAME_STOP or len(name) == 4:
                break
            name.insert(0, word)
        if name:
            return " ".join(name).title()
    return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def parse_request(raw_text: str) -> ParseResult:
    warnings = _Warnings()
    text = normalize(raw_text)

    complexity, detected = _detect_complexity(text)
    set_name = _detect_set_name(text)

    labor, remaining = _extract_labor(text, warnings)
    materials, remaining = _extract_materials(remaining, warnings)

    for m in LEFTOVER_RE.finditer(remaining):
        warnings.add(f"Could not match '{m.group(0).strip()}' to the catalogue, so it was not costed.")

    if not detected:
        warnings.add("No complexity level was given, so it defaulted to simple (no surcharge).")

    return ParseResult(
        set_name=set_name,
        complexity=complexity,
        complexity_detected=detected,
        materials=materials,
        labor=labor,
        warnings=list(warnings),
    )
