"""AI-7: turn numbers, materials and cut callouts into words a text-to-speech voice reads well.

Everything here is deterministic and lives in code, because spoken build steps must state the real
patched dimensions and never a value the LLM made up (see the AI rules). The instructions route and
the edit message builder call these helpers; Gemini only supplies prose, never the numbers.

Public helpers:
- `material_words("2x6_PT")` -> "two-by-six"
- `length_words(64.5)` -> "sixty-four and a half inches"
- `angle_words(15)` -> "fifteen-degree"
- `cut_callout_spoken("2x6_PT", 64.5)` -> "two-by-six, sixty-four and a half inches"

Lengths are rounded to the nearest 1/16 inch. At 12 inches or more, `length_words` speaks
feet-and-inches when that reads more clearly (e.g. "five feet four and a half inches").
"""

from __future__ import annotations

from fractions import Fraction

# ---------------------------------------------------------------------------------------------
# Cardinal numbers in words (0..999 covers inches and feet).

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

# Spoken forms for sixteenth-based fractions (the finest resolution we round to).
_FRACTION_WORDS = {
    Fraction(1, 16): "one sixteenth",
    Fraction(1, 8): "one eighth",
    Fraction(3, 16): "three sixteenths",
    Fraction(1, 4): "a quarter",
    Fraction(5, 16): "five sixteenths",
    Fraction(3, 8): "three eighths",
    Fraction(7, 16): "seven sixteenths",
    Fraction(1, 2): "a half",
    Fraction(9, 16): "nine sixteenths",
    Fraction(5, 8): "five eighths",
    Fraction(11, 16): "eleven sixteenths",
    Fraction(3, 4): "three quarters",
    Fraction(13, 16): "thirteen sixteenths",
    Fraction(7, 8): "seven eighths",
    Fraction(15, 16): "fifteen sixteenths",
}


def cardinal_words(n: int) -> str:
    """Whole number 0..999 in words. Above that, fall back to the digits (never needed here)."""
    n = int(n)
    if n < 0:
        return "minus " + cardinal_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + ("-" + _ONES[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = _ONES[hundreds] + " hundred"
        return head + (" " + cardinal_words(rest) if rest else "")
    return str(n)


# ---------------------------------------------------------------------------------------------
# Materials


def _material_stem(material: str) -> str:
    """Drop the treatment/type suffix so '2x6_PT' and '2x6_PT_deck' share a stem."""
    stem = material.strip()
    for suffix in ("_PT_deck", "_ext_ply", "_PT", "_deck", "_ply"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem


# Explicit spoken names, keyed by the raw material string. Anything not listed falls back to a
# nominal-dimension reading ("two-by-six") built from the stem.
_MATERIAL_WORDS = {
    "2x4_PT": "two-by-four",
    "2x6_PT": "two-by-six",
    "2x8_PT": "two-by-eight",
    "2x10_PT": "two-by-ten",
    "2x12_PT": "two-by-twelve",
    "4x4_PT": "four-by-four",
    "6x6_PT": "six-by-six",
    "5/4x6_PT_deck": "five-quarter by six decking",
    "3/4_ext_ply": "three-quarter-inch plywood",
    "1/2_ext_ply": "half-inch plywood",
}


def _dimension_words(token: str) -> str | None:
    token = token.strip()
    if token.isdigit():
        return cardinal_words(int(token))
    if "/" in token:  # e.g. "5/4" -> "five-quarter"
        num, _, den = token.partition("/")
        if num.isdigit() and den == "4":
            return cardinal_words(int(num)) + "-quarter"
    return None


def _nominal_words(stem: str) -> str | None:
    """Read a 'AxB' nominal size, where A/B may be a whole number or a quarter fraction."""
    if "x" not in stem:
        return None
    left, _, right = stem.partition("x")
    a, b = _dimension_words(left), _dimension_words(right)
    if a is None or b is None:
        return None
    return f"{a}-by-{b}"


def material_words(material: str) -> str:
    """Spoken name for a lumber material key. Falls back to the nominal size, then the raw key."""
    if material in _MATERIAL_WORDS:
        return _MATERIAL_WORDS[material]
    stem = _material_stem(material)
    if stem in _MATERIAL_WORDS:
        return _MATERIAL_WORDS[stem]
    nominal = _nominal_words(stem)
    if nominal is not None:
        return nominal
    return material.replace("_", " ")


# ---------------------------------------------------------------------------------------------
# Lengths


def _round_to_sixteenth(inches: float) -> Fraction:
    return Fraction(round(inches * 16), 16)


def _inches_phrase(value: Fraction, *, unit: bool = True) -> str:
    """Word form of an inch value like 5-1/2 -> 'five and a half inches'.

    `value` is already rounded to a sixteenth. With `unit=False` the unit word is omitted, for use
    inside a feet-and-inches phrase.
    """
    whole = value.numerator // value.denominator
    frac = value - whole
    if frac == 0:
        words = cardinal_words(whole)
        if not unit:
            return words
        return words + (" inch" if whole == 1 else " inches")
    frac_word = _FRACTION_WORDS[frac]
    if whole == 0:
        if not unit:
            return frac_word
        if frac_word.startswith("a "):
            return frac_word + " inch"  # "a half inch"
        return frac_word + " of an inch"
    body = f"{cardinal_words(whole)} and {frac_word}"
    if not unit:
        return body
    return body + (" inch" if value == 1 else " inches")


def length_words(inches: float, *, prefer_feet_at: float = 12.0) -> str:
    """Spoken length. Rounds to the nearest 1/16 inch.

    At `prefer_feet_at` inches (12 by default) or more, speaks feet-and-inches, e.g.
    64.5 -> 'five feet four and a half inches'. Whole feet drop the inches: 60 -> 'five feet'.
    Below the threshold it stays in inches: 5.375 -> 'five and three eighths inches'.
    """
    value = _round_to_sixteenth(inches)
    if value < prefer_feet_at:
        return _inches_phrase(value)

    feet = int(value // 12)
    rest = value - feet * 12
    feet_word = f"{cardinal_words(feet)} " + ("foot" if feet == 1 else "feet")
    if rest == 0:
        return feet_word
    return f"{feet_word} {_inches_phrase(rest)}"


def inches_words(inches: float) -> str:
    """Spoken length that always stays in inches (no feet), rounded to 1/16."""
    return _inches_phrase(_round_to_sixteenth(inches))


# ---------------------------------------------------------------------------------------------
# Angles


def angle_words(degrees: float) -> str:
    """Spoken angle as an adjective for a cut, e.g. 15 -> 'fifteen-degree', 22.5 -> 'twenty-two
    and a half-degree'. Rounds to the nearest 1/16 of a degree like lengths do."""
    value = _round_to_sixteenth(degrees)
    whole = value.numerator // value.denominator
    frac = value - whole
    if frac == 0:
        return f"{cardinal_words(whole)}-degree"
    frac_word = _FRACTION_WORDS[frac]
    if whole == 0:
        return f"{frac_word}-degree"
    return f"{cardinal_words(whole)} and {frac_word}-degree"


# ---------------------------------------------------------------------------------------------
# Cut callouts (material + length), the spoken string stored on CutCallout.spoken


def cut_callout_spoken(material: str, length_in: float, *, use_feet: bool = False) -> str:
    """"two-by-six, sixty-four and a half inches" — material name, then length.

    Cut callouts are read while measuring against a tape, so they stay in inches by default (the
    tape reads inches). Pass `use_feet=True` for a length that reads more clearly in feet.
    """
    length = length_words(length_in) if use_feet else inches_words(length_in)
    return f"{material_words(material)}, {length}"
