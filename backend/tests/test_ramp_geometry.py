"""Slope math and the stringer profile."""

import math

import pytest

from app.templates.geometry import signed_area
from app.templates.ramp_geometry import (
    deck_underside,
    sloped_length,
    slope_angle,
    stringer_bottom,
    stringer_length,
    stringer_profile,
    surface_point,
)

D, W = 1.0, 5.5  # deck thickness, 2x6 width


def test_slope_angle_of_1_in_12():
    assert math.degrees(slope_angle(12)) == pytest.approx(4.7636, abs=1e-3)


def test_sloped_length_of_a_21_foot_run():
    assert sloped_length(252, 12) == pytest.approx(252.873, abs=1e-3)


def test_surface_point_is_on_the_slope_and_offset_is_perpendicular():
    x, y = surface_point(100, 0, 12)
    assert y / x == pytest.approx(1 / 12)
    ox, oy = surface_point(100, 5, 12)
    assert math.dist((x, y), (ox, oy)) == pytest.approx(5)


def test_deck_and_stringer_offsets_are_vertical_distances_along_the_slope():
    assert deck_underside(0, 12, D) == pytest.approx(-1.00347, abs=1e-4)
    assert stringer_bottom(0, 12, D, W) == pytest.approx(-6.52247, abs=1e-4)


def test_stringer_on_the_ground_has_a_level_cut_and_a_plumb_cut():
    """A 15 in rise at 1:12 starting on the ground: the shape the fixtures were built from."""
    profile = stringer_profile(180, 12, D, W, 0)
    expected = {(12.042, 0.0), (78.27, 0.0), (180.0, 8.477), (180.0, 13.997)}
    assert len(profile) == 4
    for x, y in profile:
        assert any(math.dist((x, y), e) < 0.01 for e in expected), (x, y)
    assert signed_area(profile) > 0
    assert min(y for _, y in profile) == 0  # clipped at grade
    ys = sorted({y for x, y in profile if x == 180})
    assert len(ys) == 2 and (ys[1] - ys[0]) == pytest.approx(5.5 / math.cos(slope_angle(12)), abs=2e-3)  # plumb cut


def test_stringer_length_is_the_extent_along_the_slope():
    assert stringer_length(180, 12, D, W, 0) == pytest.approx(168.54, abs=0.02)
    assert stringer_length(252, 12, D, W, 0) == pytest.approx(240.79, abs=0.02)  # a 21 in straight ramp: too long for any board


def test_a_raised_run_is_a_plain_quadrilateral_with_two_plumb_cuts():
    profile = stringer_profile(90, 12, D, W, 7.5)
    assert len(profile) == 4
    xs = sorted({x for x, _ in profile})
    assert xs == [0.0, 90.0]
    assert min(y for _, y in profile) < 0  # local y; it sits above the ground because the run starts at 7.5
    # length = run/cos + a small end-cut allowance
    assert stringer_length(90, 12, D, W, 7.5) == pytest.approx(90 * math.cos(slope_angle(12)) + (90 / 12 + 5.5 / math.cos(slope_angle(12))) * math.sin(slope_angle(12)), abs=0.02)


def test_a_run_only_high_enough_to_avoid_the_clip_is_unclipped():
    assert stringer_length(90, 12, D, W, 7.5) > stringer_length(90, 12, D, W, 0)


def test_stringer_length_grows_with_run_and_shrinks_with_a_thicker_deck():
    assert stringer_length(200, 12, D, W, 0) > stringer_length(180, 12, D, W, 0)
    assert stringer_length(180, 12, 0.703, W, 0) > stringer_length(180, 12, 1.0, W, 0)  # thinner deck: less clipped wedge


def test_steeper_slopes_give_a_bigger_angle_and_still_a_valid_profile():
    assert slope_angle(8) > slope_angle(12)
    assert signed_area(stringer_profile(96, 8, D, W, 0)) > 0


def test_a_very_low_run_has_no_stringer():
    assert stringer_profile(12, 12, D, W, 0) == []  # 1 in rise: smaller than the deck itself
    assert stringer_length(12, 12, D, W, 0) == 0.0
    assert stringer_profile(2.4 * 12, 12, D, W, 0) == []  # end depth 1.39 in < 1.5
    assert stringer_profile(3 * 12, 12, D, W, 0) != []  # end depth 2.0 in


def test_ground_clip_makes_the_length_independent_of_board_width_but_a_raised_run_is_not():
    assert stringer_length(180, 12, D, 5.5, 0) == stringer_length(180, 12, D, 7.25, 0)
    assert stringer_length(90, 12, D, 7.25, 7.5) > stringer_length(90, 12, D, 5.5, 7.5)
