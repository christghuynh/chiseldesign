"""GEO-5: landings and switchback geometry."""

import math

import pytest

from app.engine_errors import ParamValidationError
from app.templates.ramp import Params, derive
from app.templates.ramp_parts import build_parts
from tests.test_ramp_support import assert_invariants, bbox, make, named, world_points

LANDING_NAMES = ("Landing rim (end)", "Landing rim (side)", "Landing joist", "Landing deck board", "Landing deck panel", "Landing post")


def landing_parts(parts, group="landing_1"):
    return [p for p in parts if p.group == group]


def test_switchback_builds_two_runs_and_a_landing():
    params, derived, parts = make(total_rise_in=20, layout="switchback")
    assert derived.layout == "switchback" and derived.run_count == 2
    assert {p.group for p in parts} == {"run_1", "run_2", "landing_1"}
    assert len(named(parts, "Ledger")) == 1 and named(parts, "Ledger")[0].group == "run_2"
    assert_invariants(parts)


def test_landing_length_and_footprint():
    params, derived, parts = make(total_rise_in=20, layout="switchback", landing_length_in=72)
    landing = derived.landings[0]
    (x0, _, z0), (x1, y1, z1) = bbox(landing_parts(parts))
    assert x1 - x0 == pytest.approx(72) == pytest.approx(params.landing_length_in)
    assert (x0, x1) == (pytest.approx(landing.x_min), pytest.approx(landing.x_max))
    assert (z0, z1) == (pytest.approx(landing.z_min), pytest.approx(landing.z_max))
    assert y1 == pytest.approx(landing.elevation_in, abs=1e-3)


def test_landing_frame_pieces():
    params, derived, parts = make(total_rise_in=20, layout="switchback")
    landing = derived.landings[0]
    frame = landing_parts(parts)
    ends, sides, joists = named(frame, "Landing rim (end)"), named(frame, "Landing rim (side)"), named(frame, "Landing joist")
    assert len(ends) == 2 and len(sides) == 2
    width = landing.z_max - landing.z_min
    assert all(e.thickness == pytest.approx(width) for e in ends)
    assert all(s.thickness == 1.5 for s in sides)
    assert bbox([ends[0]])[0][0] == pytest.approx(landing.x_min) and bbox([ends[1]])[1][0] == pytest.approx(landing.x_max)
    for s in sides:
        (sx0, _, _), (sx1, _, _) = bbox([s])
        assert (sx0, sx1) == (pytest.approx(landing.x_min + 1.5), pytest.approx(landing.x_max - 1.5))
    for j in joists:
        assert j.thickness == pytest.approx(width - 3)
        assert bbox([j])[0][2] == pytest.approx(landing.z_min + 1.5)
    # frame top is the deck underside; frame depth is the full 2x6 here
    (_, lo, _), (_, hi, _) = bbox(ends)
    assert hi == pytest.approx(landing.elevation_in - 1.0) and hi - lo == pytest.approx(5.5)


@pytest.mark.parametrize(("spacing", "landing_len", "expected"), [(16, 60, 3), (12, 60, 4), (24, 60, 2), (16, 36, 2), (16, 240, 14)])
def test_joist_spacing(spacing, landing_len, expected):
    _, derived, parts = make(total_rise_in=20, layout="switchback", stringer_spacing_in=spacing, landing_length_in=landing_len)
    landing = derived.landings[0]
    joists = named(landing_parts(parts), "Landing joist")
    assert len(joists) == expected
    centers = [(bbox([j])[0][0] + bbox([j])[1][0]) / 2 for j in joists]
    assert centers == [pytest.approx(landing.x_min + spacing * (k + 1)) for k in range(expected)]
    far_end_rim_start = landing.x_max - 1.5
    assert all(c + 0.75 < far_end_rim_start for c in centers)


def test_landing_posts_reach_the_ground():
    _, derived, parts = make(total_rise_in=31, layout="straight")
    landing = derived.landings[0]
    posts = named(parts, "Landing post")
    assert len(posts) == 4 and all(p.group == "landing_1" and p.material == "4x4_PT" for p in posts)
    corners = set()
    for p in posts:
        (x0, y0, z0), (x1, y1, z1) = bbox([p])
        assert y0 == pytest.approx(0, abs=1e-3) and y1 == pytest.approx(landing.elevation_in - 1.0 - 5.5, abs=1e-3)
        assert x1 - x0 == pytest.approx(3.5) and z1 - z0 == pytest.approx(3.5)
        corners.add((round(x0 - landing.x_min, 1), round(z0 - landing.z_min, 1)))
    assert corners == {(0.0, 0.0), (0.0, landing.z_max - landing.z_min - 3.5), (landing.x_max - landing.x_min - 3.5, 0.0), (landing.x_max - landing.x_min - 3.5, landing.z_max - landing.z_min - 3.5)}


def test_low_landing_frame_sits_on_the_ground_without_posts():
    _, derived, parts = make(total_rise_in=12, layout="switchback")  # landing at 6 in: frame is 5 in deep, bottom at 0
    frame = landing_parts(parts)
    assert not named(frame, "Landing post")
    assert bbox(named(frame, "Landing rim (end)"))[0][1] == pytest.approx(0, abs=1e-3)
    assert_invariants(parts)


def test_intermediate_landing_on_a_straight_ramp():
    params, derived, parts = make(total_rise_in=31, layout="straight")
    assert derived.run_count == 2 and derived.landings[0].kind == "intermediate"
    frame = landing_parts(parts)
    assert {p.name for p in frame} == {"Landing rim (end)", "Landing rim (side)", "Landing joist", "Landing deck board", "Landing post"}
    (x0, _, z0), (x1, y1, z1) = bbox(frame)
    assert (x1 - x0, z1 - z0) == (pytest.approx(60), pytest.approx(36))
    assert y1 == pytest.approx(15.5, abs=1e-3)
    assert named(parts, "Ledger")[0].group == "run_2"
    assert not named(parts, "Landing deck panel")


def test_landing_deck_boards_run_along_x_and_cover_the_width():
    _, derived, parts = make(total_rise_in=20, layout="switchback")
    landing = derived.landings[0]
    boards = named(landing_parts(parts), "Landing deck board")
    assert all(b.material == "5/4x6_PT_deck" for b in boards)
    spans = sorted((bbox([b])[0][2], bbox([b])[1][2]) for b in boards)
    assert spans[0][0] == pytest.approx(landing.z_min) and spans[-1][1] == pytest.approx(landing.z_max)
    assert all(b0 - a1 >= 0.125 - 1e-3 for (_, a1), (b0, _) in zip(spans, spans[1:], strict=False))
    for b in boards:
        (x0, y0, _), (x1, y1, _) = bbox([b])
        assert (x0, x1) == (pytest.approx(landing.x_min), pytest.approx(landing.x_max))
        assert y1 - y0 == pytest.approx(1.0)
        assert 2 <= b.thickness <= 5.5 + 1e-9
    assert sum(1 for b in boards if b.thickness < 5.5 - 1e-6) <= 1


@pytest.mark.parametrize(("width", "columns"), [(36, 1), (60, 2)])
def test_landing_plywood_panels_stay_within_a_sheet(width, columns):
    # straight landing is `width` wide; switchback landing is 2 * width + 12
    _, derived, parts = make(total_rise_in=31, layout="straight", clear_width_in=width, decking="3/4_ext_ply", landing_length_in=200)
    panels = named(landing_parts(parts), "Landing deck panel")
    assert len(panels) == columns * 3  # 200 in long -> 3 pieces of at most 96
    for p in panels:
        (x0, y0, _), (x1, y1, _) = bbox([p])
        assert x1 - x0 <= 96 and p.thickness <= 48 and y1 - y0 == pytest.approx(0.703, abs=1e-3)
    assert sum(p.thickness for p in panels) / 3 == pytest.approx(width)


def test_very_long_landing_is_cut_into_buyable_pieces():
    _, derived, parts = make(total_rise_in=20, layout="switchback", landing_length_in=240)
    for p in landing_parts(parts):
        (x0, _, z0), (x1, _, z1) = bbox([p])
        assert max(x1 - x0, z1 - z0, p.thickness) <= 192 + 1e-6, p.name
    sides = named(landing_parts(parts), "Landing rim (side)")
    assert len(sides) == 4 and all(s.cut_notes == ["Splice: butt joint"] for s in sides)


def test_switchback_runs_do_not_overlap_in_plan():
    params, derived, parts = make(total_rise_in=20, layout="switchback")
    (ax0, _, az0), (ax1, _, az1) = bbox([p for p in parts if p.group == "run_1"])
    (bx0, _, bz0), (bx1, _, bz1) = bbox([p for p in parts if p.group == "run_2"])
    assert az1 - bz0 < 0  # separated in z, with the 12 in gap between the runs
    assert not (ax0 < bx1 and bx0 < ax1 and az0 < bz1 and bz0 < az1)
    assert (az0, az1) == (pytest.approx(-18), pytest.approx(18))
    assert (bz0, bz1) == (pytest.approx(30), pytest.approx(66))  # 48 - 18 .. 48 + 18


def test_second_run_stringers_are_mirrored_and_inside_its_width():
    params, derived, parts = make(total_rise_in=20, layout="switchback")
    run = derived.runs[1]
    assert run.direction == -1
    stringers = named(parts, "Stringer", "run_2")
    assert len(stringers) == 4
    assert all(s.transform.rot[1] == pytest.approx(math.pi) for s in stringers)
    for s in stringers:
        pts = world_points(s)
        assert min(p[2] for p in pts) >= 30 - 1e-6 and max(p[2] for p in pts) <= 66 + 1e-6
        assert min(p[0] for p in pts) >= -1e-6 and max(p[0] for p in pts) == pytest.approx(run.x_start, abs=1e-3)
        # the low end is at the landing edge (high world x), the top end at world x = 0
        top_y = max(p[1] for p in pts)
        assert top_y == pytest.approx(20 - 1.0 / math.cos(derived.slope_angle_rad), abs=1e-3)
        assert min(p[0] for p in pts if abs(p[1] - top_y) < 1e-6) == pytest.approx(0, abs=1e-3)
    spans = sorted((bbox([s])[0][2], bbox([s])[1][2]) for s in stringers)
    assert spans[0][0] == pytest.approx(30) and spans[-1][1] == pytest.approx(66)  # outer stringers flush with the edges
    decking = [p for p in parts if p.group == "run_2" and p.name == "Deck board"]
    assert bbox(decking)[1][1] == pytest.approx(20, abs=1 / 16)
    assert bbox(decking)[0][0] >= -0.4


def test_too_small_a_rise_for_a_switchback_is_an_error():
    params = Params(total_rise_in=3, layout="switchback")
    with pytest.raises(ParamValidationError, match="each landing needs at least 2.5 in of height"):
        build_parts(params, derive(params))
    ply = Params(total_rise_in=3.0, layout="switchback", decking="3/4_ext_ply")
    with pytest.raises(ParamValidationError, match="at least 2.3 in"):
        build_parts(ply, derive(ply))
    ok = Params(total_rise_in=5, layout="switchback")  # landing at 2.5 in: 1.5 in frame
    assert_invariants(build_parts(ok, derive(ok)))


def test_three_run_switchback_has_two_landings():
    params, derived, parts = make(total_rise_in=60, layout="switchback")
    assert derived.run_count == 2 and len(derived.landings) == 1
    groups = {p.group for p in parts}
    assert {f"landing_{i + 1}" for i in range(len(derived.landings))} <= groups
    assert len(named(parts, "Ledger")) == 1 and named(parts, "Ledger")[0].group == f"run_{derived.run_count}"
    assert_invariants(parts)
