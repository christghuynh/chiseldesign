import json
from pathlib import Path

import pytest

from app.util.units import format_fraction, format_ft_in, parse_length

CASES = json.loads((Path(__file__).resolve().parents[2] / "fixtures" / "units" / "cases.json").read_text("utf-8"))


@pytest.mark.parametrize(("inches", "expected"), CASES["format_ft_in"])
def test_format_ft_in(inches, expected):
    assert format_ft_in(inches) == expected


@pytest.mark.parametrize(("inches", "expected"), CASES["format_fraction"])
def test_format_fraction(inches, expected):
    assert format_fraction(inches) == expected


@pytest.mark.parametrize(("text", "expected"), CASES["parse_length"])
def test_parse_length(text, expected):
    assert parse_length(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", CASES["parse_length_errors"])
def test_parse_length_rejects(text):
    with pytest.raises(ValueError):
        parse_length(text)


@pytest.mark.parametrize("bad", [-1, -0.001, float("nan"), float("inf")])
def test_format_rejects_invalid_lengths(bad):
    with pytest.raises(ValueError):
        format_ft_in(bad)
    with pytest.raises(ValueError):
        format_fraction(bad)


def test_round_trip_at_sixteenth_resolution():
    for sixteenths in range(0, 16 * 12 * 25):
        inches = sixteenths / 16
        assert parse_length(format_ft_in(inches)) == inches


def test_carry_when_rounding_up_to_a_full_foot():
    # 11-63/64" rounds to 12", which must carry into the feet column.
    assert format_ft_in(11.99) == "1' 0\""
