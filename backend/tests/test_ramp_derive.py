"""GEO-3: ramp derive() (runs, landings, layout choice, lumber fit).

The stock-length policy: a stringer must be buyable as ONE board (2x6/2x8 stock tops out at 192 in), so
`layout: auto` picks straight only when the straight ramp fits the site AND the lumber. A straight
21 in ramp needs ~241 in stringers, so it is NOT straight even with no length limit.
"""

import math
from dataclasses import replace

import pytest

from app.templates.ramp import Params, derive, derive_layout


def P(**kw) -> Params:
    kw.setdefault("total_rise_in", 21)
    return Params(**kw)


def test_rise_21_with_no_limit_is_a_switchback_because_the_straight_stringers_are_too_long():
    d = derive(P())
    assert d.layout == "switchback" and d.requested_layout == "auto"
    assert d.run_count == 2 and [r.rise_in for r in d.runs] == [10.5, 10.5]
    assert d.stringers_fit_stock and d.max_stringer_length_in <= 192
    straight = derive_layout(P(), "straight")
    assert straight.run_count == 1 and not straight.stringers_fit_stock
    assert straight.max_stringer_length_in == pytest.approx(240.8, abs=0.2)


def test_rise_21_in_a_144_in_yard_does_not_fit_even_as_a_switchback():
    """Documented consequence of the placeholder rules (1:12 slope, 60 in landings): 126 + 60 = 186 in."""
    d = derive(P(available_length_in=144))
    assert d.layout == "switchback" and d.run_count == 2
    assert d.footprint_length_in == pytest.approx(186)
    assert not d.fits_site
    assert derive_layout(P(available_length_in=144), "straight").footprint_length_in == pytest.approx(252)


def test_rise_12_no_limit_is_a_plain_straight_ramp():
    d = derive(P(total_rise_in=12))
    assert d.layout == "straight" and d.run_count == 1 and not d.landings
    assert d.total_run_in == 144 and d.runs[0].run_in == 144 and d.fits_site and d.stringers_fit_stock
    assert d.slope_angle_deg == pytest.approx(4.7636, abs=1e-3)


def test_rise_15_in_a_160_in_yard_switches_back_and_fits():
    d = derive(P(total_rise_in=15, available_length_in=160))
    assert d.layout == "switchback" and d.footprint_length_in == pytest.approx(150) and d.fits_site
    assert derive_layout(P(total_rise_in=15, available_length_in=160), "straight").footprint_length_in == pytest.approx(180)


def test_rise_31_is_two_straight_runs_with_an_intermediate_landing():
    d = derive(P(total_rise_in=31))
    assert d.layout == "straight" and d.run_count == 2
    assert [r.rise_in for r in d.runs] == [15.5, 15.5]
    (landing,) = d.landings
    assert landing.kind == "intermediate" and landing.elevation_in == 15.5
    assert (landing.x_min, landing.x_max) == (186, 246) and (landing.z_min, landing.z_max) == (-18, 18)
    assert d.runs[1].x_start == 246 and d.runs[1].y_start == 15.5
    assert d.footprint_length_in == pytest.approx(432)


def test_forcing_straight_at_rise_31_still_derives():
    assert derive(P(total_rise_in=31, layout="straight")).run_count == 2


def test_run_splitting_boundary_is_exactly_30_in():
    assert derive_layout(P(total_rise_in=30), "straight").run_count == 1
    assert derive_layout(P(total_rise_in=30.5), "straight").run_count == 2
    assert derive_layout(P(total_rise_in=30), "switchback").run_count == 2  # a switchback always has two runs


def test_rise_60_cannot_be_built_from_single_boards_either_way():
    d = derive(P(total_rise_in=60))
    assert d.layout == "switchback" and not d.stringers_fit_stock
    assert not derive_layout(P(total_rise_in=60), "straight").stringers_fit_stock


def test_switchback_geometry_the_second_run_returns_beside_the_first():
    d = derive(P(total_rise_in=15, available_length_in=160))
    r0, r1 = d.runs
    assert (r0.direction, r1.direction) == (1, -1)
    assert (r0.x_start, r0.x_end, r1.x_start, r1.x_end) == (0, 90, 90, 0)
    assert (r0.y_start, r0.y_end, r1.y_start, r1.y_end) == (0, 7.5, 7.5, 15)
    assert (r0.z_center, r1.z_center) == (0, 48)  # width 36 + 12 gap
    (landing,) = d.landings
    assert landing.kind == "turn" and landing.elevation_in == 7.5
    assert (landing.x_min, landing.x_max) == (90, 150) and (landing.z_min, landing.z_max) == (-18, 66)
    assert d.footprint_width_in == pytest.approx(84)


def test_run_geometry_invariants_hold_across_many_inputs():
    for rise in (1, 6, 6.5, 12, 21, 29.9, 30, 31, 45, 60):
        for layout in ("auto", "straight", "switchback"):
            for width in (30, 36, 60):
                d = derive(P(total_rise_in=rise, layout=layout, clear_width_in=width))
                assert sum(r.rise_in for r in d.runs) == pytest.approx(rise)
                assert d.runs[-1].y_end == pytest.approx(rise)
                for r in d.runs:
                    assert abs(r.x_end - r.x_start) == pytest.approx(r.run_in)
                    assert r.run_in == pytest.approx(r.rise_in * d.slope_ratio)
                    assert r.sloped_in >= r.run_in and r.stringer_length_in >= 0
                    assert r.direction in (1, -1)
                for prev, nxt in zip(d.runs, d.runs[1:], strict=False):
                    assert nxt.y_start == pytest.approx(prev.y_end)
                for landing, prev in zip(d.landings, d.runs, strict=False):
                    assert landing.elevation_in == pytest.approx(prev.y_end)
                    assert landing.x_max - landing.x_min == pytest.approx(d.landing_length_in)
                assert d.footprint_length_in > 0 and d.footprint_width_in >= width


@pytest.mark.parametrize(
    ("rise", "handrails", "required", "included"),
    [(6, "auto", False, False), (6.01, "auto", True, True), (3, "yes", False, True), (21, "no", True, False), (21, "auto", True, True)],
)
def test_handrails_required_versus_included(rise, handrails, required, included):
    d = derive(P(total_rise_in=rise, handrails=handrails))
    assert (d.handrails_required, d.handrails_included) == (required, included)


def test_stringer_count_follows_width_and_spacing():
    assert derive(P(total_rise_in=12)).stringer_count == 4  # ceil(36/16) + 1
    assert derive(P(total_rise_in=12, clear_width_in=48, stringer_spacing_in=12)).stringer_count == 5


def test_framing_and_deck_dimensions_come_from_lumber_data():
    d = derive(P(total_rise_in=12, framing="2x8_PT", decking="3/4_ext_ply"))
    assert (d.framing_thickness_in, d.framing_width_in, d.deck_thickness_in) == (1.5, 7.25, 0.703)
    assert d.max_stock_length_in == 192


def test_a_wider_framing_board_lengthens_a_raised_stringer_but_not_one_clipped_at_grade():
    on_ground = lambda framing: derive(P(total_rise_in=12, framing=framing)).max_stringer_length_in
    assert on_ground("2x6_PT") == on_ground("2x8_PT")
    raised = lambda framing: derive(P(total_rise_in=15, layout="switchback", framing=framing)).runs[1].stringer_length_in
    assert raised("2x8_PT") > raised("2x6_PT")


def test_a_very_low_ramp_has_no_stringers_but_still_derives():
    low = derive(P(total_rise_in=2))
    assert low.layout == "straight" and not low.runs[0].has_stringers and low.runs[0].stringer_length_in == 0
    assert low.stringers_fit_stock and low.footprint_length_in == 24
    assert derive(P(total_rise_in=3)).runs[0].has_stringers


def test_a_one_inch_switchback_has_a_stringerless_run():
    d = derive(P(total_rise_in=1, layout="switchback"))
    assert not d.runs[0].has_stringers and not d.runs[1].has_stringers  # the raised run's band is also below ground


def test_derive_is_deterministic_and_immutable():
    a, b = derive(P()), derive(P())
    assert a == b
    with pytest.raises(Exception):
        a.layout = "straight"  # frozen dataclass
    assert replace(a, layout="straight") != a


def test_derive_layout_matches_derive_for_a_forced_layout():
    forced = derive(P(total_rise_in=15, layout="switchback"))
    assert derive_layout(P(total_rise_in=15, layout="switchback"), "switchback") == forced


def test_steeper_slope_shortens_the_ramp():
    assert derive(P(total_rise_in=12, slope_ratio=8)).total_run_in == 96
    assert derive(P(total_rise_in=12, slope_ratio=8)).slope_angle_rad > derive(P(total_rise_in=12)).slope_angle_rad


def test_available_length_exactly_equal_to_the_footprint_fits():
    assert derive(P(total_rise_in=15, available_length_in=150, layout="switchback")).fits_site
    assert not derive(P(total_rise_in=15, available_length_in=149.9, layout="switchback")).fits_site


def test_no_nan_or_inf_anywhere():
    d = derive(P(total_rise_in=1, slope_ratio=40, landing_length_in=240))
    for value in (d.total_run_in, d.footprint_length_in, d.max_stringer_length_in, *(r.stringer_length_in for r in d.runs)):
        assert math.isfinite(value)
