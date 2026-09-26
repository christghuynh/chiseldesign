"""Inches <-> feet-and-inches display.

Everything internal is inches. Display rounds to the nearest 1/16" (halves round up).
The TypeScript mirror is frontend/src/util/units.ts; both are tested against the same
cases in fixtures/units/cases.json, so change them together.
"""

import math
import re

SIXTEENTHS_PER_INCH = 16
SIXTEENTHS_PER_FOOT = 12 * SIXTEENTHS_PER_INCH


def _to_sixteenths(inches: float) -> int:
    if not math.isfinite(inches) or inches < 0:
        raise ValueError(f"length must be a non-negative finite number, got {inches!r}")
    return math.floor(inches * SIXTEENTHS_PER_INCH + 0.5)


def _inch_text(sixteenths: int) -> str:
    """Whole inches plus a reduced fraction: 24 -> "1-1/2", 8 -> "1/2", 32 -> "2"."""
    whole, rem = divmod(sixteenths, SIXTEENTHS_PER_INCH)
    if rem == 0:
        return str(whole)
    divisor = math.gcd(rem, SIXTEENTHS_PER_INCH)
    fraction = f"{rem // divisor}/{SIXTEENTHS_PER_INCH // divisor}"
    return fraction if whole == 0 else f"{whole}-{fraction}"


def format_fraction(inches: float) -> str:
    """Inches as a mixed number with no unit mark, for dimensions: 5.5 -> "5-1/2"."""
    return _inch_text(_to_sixteenths(inches))


def format_ft_in(inches: float) -> str:
    """Inches as feet and inches: 64.5 -> `5' 4-1/2"`, 60 -> `5' 0"`, 4.5 -> `4-1/2"`."""
    feet, rem = divmod(_to_sixteenths(inches), SIXTEENTHS_PER_FOOT)
    text = _inch_text(rem)
    return f'{text}"' if feet == 0 else f"{feet}' {text}\""


_NUMBER = r"\d+(?:\.\d+)?"
_INCHES = rf"(?:\d+[-\s]+\d+/\d+|\d+/\d+|{_NUMBER})"
_LENGTH_RE = re.compile(rf"^\s*(?:(?P<feet>{_NUMBER})\s*')?\s*(?:(?P<inches>{_INCHES})\s*\"?)?\s*$", re.ASCII)
_MIXED_RE = re.compile(r"^(?:(?P<whole>\d+)[-\s]+)?(?P<num>\d+)/(?P<den>\d+)$", re.ASCII)


def _parse_inches(token: str) -> float:
    mixed = _MIXED_RE.match(token)
    if mixed is None:
        return float(token)
    denominator = int(mixed["den"])
    if denominator == 0:
        raise ValueError(f"zero denominator in {token!r}")
    return int(mixed["whole"] or 0) + int(mixed["num"]) / denominator


def parse_length(text: str) -> float:
    """Parse `5' 4-1/2"`, `5'`, `4 1/2"`, `1/2"`, `64.5` or `2.5'` into inches.

    A bare number is inches. Raises ValueError on anything else (including negatives).
    """
    normalized = text.replace("″", '"').replace("′", "'")
    match = _LENGTH_RE.match(normalized)
    if match is None or (match["feet"] is None and match["inches"] is None):
        raise ValueError(f"cannot parse length: {text!r}")
    feet = float(match["feet"]) if match["feet"] is not None else 0.0
    inches = _parse_inches(match["inches"]) if match["inches"] is not None else 0.0
    return feet * 12 + inches
