"""AI-7 tests: spoken numbers, materials, lengths, angles and cut callouts.

No AI or network here; numwords is pure code.
"""

import pytest

from app.ai.numwords import (
    angle_words,
    cardinal_words,
    cut_callout_spoken,
    inches_words,
    length_words,
    material_words,
)

# --- Materials -------------------------------------------------------------------------------

MATERIAL_CASES = [
    ("2x4_PT", "two-by-four"),
    ("2x6_PT", "two-by-six"),
    ("2x8_PT", "two-by-eight"),
    ("2x10_PT", "two-by-ten"),
    ("4x4_PT", "four-by-four"),
    ("6x6_PT", "six-by-six"),
    ("5/4x6_PT_deck", "five-quarter by six decking"),
    ("3/4_ext_ply", "three-quarter-inch plywood"),
    ("1/2_ext_ply", "half-inch plywood"),
]


@pytest.mark.parametrize(("material", "expected"), MATERIAL_CASES)
def test_material_words(material, expected):
    assert material_words(material) == expected


def test_material_words_falls_back_to_nominal_for_an_unlisted_stem():
    assert material_words("2x2_PT") == "two-by-two"


def test_material_words_falls_back_to_the_raw_key_when_unparseable():
    assert material_words("mystery_stock") == "mystery stock"


# --- Lengths (inches only) -------------------------------------------------------------------

# 20+ cases across whole, half, quarter, eighth and sixteenth resolutions.
INCHES_CASES = [
    (0, "zero inches"),
    (1, "one inch"),
    (2, "two inches"),
    (0.5, "a half inch"),
    (0.25, "a quarter inch"),
    (0.0625, "one sixteenth of an inch"),
    (0.375, "three eighths of an inch"),
    (1.5, "one and a half inches"),
    (3.5, "three and a half inches"),
    (5.375, "five and three eighths inches"),
    (7.25, "seven and a quarter inches"),
    (11.9375, "eleven and fifteen sixteenths inches"),
    (12, "twelve inches"),
    (36, "thirty-six inches"),
    (42.625, "forty-two and five eighths inches"),
    (57, "fifty-seven inches"),
    (64.5, "sixty-four and a half inches"),
    (78.25, "seventy-eight and a quarter inches"),
    (84, "eighty-four inches"),
    (90.3125, "ninety and five sixteenths inches"),
    (90.75, "ninety and three quarters inches"),
    (144, "one hundred forty-four inches"),
]


@pytest.mark.parametrize(("inches", "expected"), INCHES_CASES)
def test_inches_words(inches, expected):
    assert inches_words(inches) == expected


def test_inches_words_rounds_to_the_nearest_sixteenth():
    assert inches_words(5.37) == "five and three eighths inches"  # 5.37 -> 5.375
    assert inches_words(0.03) == "zero inches"  # rounds down to 0
    assert inches_words(0.04) == "one sixteenth of an inch"  # rounds to 1/16


# --- Lengths (feet and inches) ---------------------------------------------------------------

FEET_CASES = [
    (12, "one foot"),
    (24, "two feet"),
    (60, "five feet"),
    (64.5, "five feet four and a half inches"),
    (125.0625, "ten feet five and one sixteenth inches"),
    (144, "twelve feet"),
    (252, "twenty-one feet"),
    (13, "one foot one inch"),
]


@pytest.mark.parametrize(("inches", "expected"), FEET_CASES)
def test_length_words_uses_feet_at_or_above_twelve(inches, expected):
    assert length_words(inches) == expected


def test_length_words_stays_in_inches_below_twelve():
    assert length_words(11.5) == "eleven and a half inches"
    assert length_words(5.375) == "five and three eighths inches"


# --- Angles ----------------------------------------------------------------------------------

ANGLE_CASES = [
    (0, "zero-degree"),
    (15, "fifteen-degree"),
    (22.5, "twenty-two and a half-degree"),
    (30, "thirty-degree"),
    (45, "forty-five-degree"),
    (7.25, "seven and a quarter-degree"),
    (0.5, "a half-degree"),
]


@pytest.mark.parametrize(("degrees", "expected"), ANGLE_CASES)
def test_angle_words(degrees, expected):
    assert angle_words(degrees) == expected


# --- Cardinals -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "zero"),
        (7, "seven"),
        (13, "thirteen"),
        (20, "twenty"),
        (21, "twenty-one"),
        (78, "seventy-eight"),
        (90, "ninety"),
        (100, "one hundred"),
        (144, "one hundred forty-four"),
    ],
)
def test_cardinal_words(n, expected):
    assert cardinal_words(n) == expected


# --- Cut callouts ----------------------------------------------------------------------------


def test_cut_callout_spoken_matches_the_shipped_instructions_fixture():
    # These strings appear verbatim in fixtures/instructions/ramp_switchback.json.
    assert cut_callout_spoken("2x6_PT", 90.75) == "two-by-six, ninety and three quarters inches"
    assert cut_callout_spoken("2x6_PT", 78.25) == "two-by-six, seventy-eight and a quarter inches"
    assert cut_callout_spoken("4x4_PT", 42.625) == "four-by-four, forty-two and five eighths inches"
    assert cut_callout_spoken("5/4x6_PT_deck", 60) == "five-quarter by six decking, sixty inches"
    assert cut_callout_spoken("2x4_PT", 90.3125) == "two-by-four, ninety and five sixteenths inches"


def test_cut_callout_spoken_can_use_feet():
    assert cut_callout_spoken("2x6_PT", 90.75, use_feet=True) == "two-by-six, seven feet six and three quarters inches"
