"""GEO-6: handrail posts and rails."""

import math

import pytest

from app.data import lumber_spec
from app.rules.constants import HANDRAIL_HEIGHT_IN
from tests.test_ramp_support import assert_invariants, bbox, make, named, world_points

H = HANDRAIL_HEIGHT_IN.value
LONGEST_RAIL = lumber_spec("2x4_PT").max_stock_length_in  # rails are 2x4: the longest board sold


def handrail_parts(parts):
    return [p for p in parts if p.group == "handrail"]


@pytest.mark.parametrize("overrides", [{"handrails": "no"}, {"handrails": "auto", "total_rise_in": 6}, {"handrails": "auto", "total_rise_in": 3}, {"handrails": "no", "total_rise_in": 40}])
def test_no_handrail_parts_when_not_included(overrides):
    _, derived, parts = make(**overrides)
    assert not derived.handrails_included
    assert not handrail_parts(parts)


@pytest.mark.parametrize("overrides", [{"handrails": "auto", "total_rise_in": 7}, {"handrails": "yes", "total_rise_in": 3}, {"handrails": "yes", "total_rise_in": 2}])
def test_handrail_parts_when_included(overrides):
    _, derived, parts = make(**overrides)
    assert derived.handrails_included
    assert named(parts, "Handrail post") and named(parts, "Handrail")
    assert all(p.group == "handrail" for p in named(parts, "Handrail post") + named(parts, "Handrail"))
    assert_invariants(parts)


def test_post_and_rail_counts_for_a_known_case():
    params, derived, parts = make(total_rise_in=12)  # 144 in run, 144.5 in sloped: 4 posts per side
    assert len(named(parts, "Handrail post")) == 8
    assert all(p.material == "4x4_PT" and p.thickness == 3.5 for p in named(parts, "Handrail post"))
    rails = named(parts, "Handrail")
    assert len(rails) == 2 and all(r.material == "2x4_PT" and r.thickness == 1.5 and r.cut_notes == ["Square cut both ends"] for r in rails)


@pytest.mark.parametrize("overrides", [{"total_rise_in": 12}, {"total_rise_in": 31, "layout": "straight"}, {"total_rise_in": 30, "layout": "straight"}, {"total_rise_in": 20, "layout": "switchback"}, {"total_rise_in": 8, "slope_ratio": 16}])
def test_posts_are_at_most_72_inches_apart_along_the_slope(overrides):
    params, derived, parts = make(**overrides)
    cos = math.cos(derived.slope_angle_rad)
    for run in derived.runs:
        w = derived.clear_width_in
        for lo, hi in ((run.z_center - w / 2 - 3.5, run.z_center - w / 2), (run.z_center + w / 2, run.z_center + w / 2 + 3.5)):
            posts = [
                p
                for p in named(parts, "Handrail post")
                if bbox([p])[0][2] == pytest.approx(lo, abs=1e-3)
                and bbox([p])[1][2] == pytest.approx(hi, abs=1e-3)
                and min(run.x_start, run.x_end) - 1e-3 <= bbox([p])[0][0]
                and bbox([p])[1][0] <= max(run.x_start, run.x_end) + 1e-3
            ]
            assert len(posts) == math.ceil(run.sloped_in / 72) + 1
            xs = sorted((bbox([p])[0][0] + bbox([p])[1][0]) / 2 for p in posts)
            assert all((b - a) / cos <= 72 + 1e-6 for a, b in zip(xs, xs[1:], strict=False))
            assert xs[0] == pytest.approx(min(run.x_start, run.x_end) + 1.75, abs=1e-3) and xs[-1] == pytest.approx(max(run.x_start, run.x_end) - 1.75, abs=1e-3)


def test_posts_reach_from_the_stringer_bottom_to_the_handrail_height():
    params, derived, parts = make(total_rise_in=12)
    cos = math.cos(derived.slope_angle_rad)
    for p in named(parts, "Handrail post"):
        (x0, y0, _), (x1, y1, _) = bbox([p])
        xc = (x0 + x1) / 2
        assert y1 == pytest.approx(xc / 12 + H / cos, abs=2e-3)
        assert y0 >= -1e-3
        assert y1 - y0 <= 120


def test_posts_on_the_ground_stand_on_it():
    _, _, parts = make(total_rise_in=12)
    first = min(named(parts, "Handrail post"), key=lambda p: bbox([p])[0][0])
    assert bbox([first])[0][1] == pytest.approx(0, abs=1e-3)  # the stringer is level-cut there, so the post stops at grade


def test_rails_follow_the_slope():
    params, derived, parts = make(total_rise_in=31, layout="straight")
    for r in named(parts, "Handrail"):
        pts = r.profile
        edges = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        a, b = max(edges, key=lambda e: math.dist(*e))
        assert math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180 == pytest.approx(derived.slope_angle_deg, abs=0.05)
        assert math.dist(*max(edges, key=lambda e: math.dist(*e))) <= LONGEST_RAIL + 1e-6


def test_rails_stay_within_the_height_range_above_the_surface():
    for overrides in ({"total_rise_in": 12}, {"total_rise_in": 20, "layout": "switchback"}, {"total_rise_in": 31, "layout": "straight"}):
        params, derived, parts = make(**overrides)
        cos = math.cos(derived.slope_angle_rad)
        for r in named(parts, "Handrail"):
            for x, y, z in world_points(r):
                run = next(
                    rn
                    for rn in derived.runs
                    if abs(z - rn.z_center) < derived.clear_width_in / 2 + 6 and min(rn.x_start, rn.x_end) - 1e-3 <= x <= max(rn.x_start, rn.x_end) + 1e-3
                )
                surface = run.y_start + (x - run.x_start) * run.direction / params.slope_ratio
                assert H - 3.5 - 2e-2 <= (y - surface) * cos <= H + 2e-2


def test_long_rails_are_split_at_posts_into_buyable_pieces():
    params, derived, parts = make(total_rise_in=30, layout="straight")
    per_run = [r for r in named(parts, "Handrail") if bbox([r])[0][0] < derived.runs[0].run_in]
    assert derived.runs[0].sloped_in > LONGEST_RAIL  # longer than the longest board sold, so each rail is spliced
    pieces = math.ceil(derived.runs[0].sloped_in / LONGEST_RAIL)
    assert len(per_run) == 2 * pieces and all(r.cut_notes == ["Splice: butt joint centered on a post"] for r in per_run)
    left = sorted((r for r in per_run if bbox([r])[0][2] < 0), key=lambda r: bbox([r])[0][0])
    assert len(left) == pieces
    for r in left:
        edges = [math.dist(r.profile[i], r.profile[(i + 1) % 4]) for i in range(4)]
        assert max(edges) <= LONGEST_RAIL + 1e-6
    # the pieces butt against each other at posts: adjacent pieces meet in x (within the parallelogram lean)
    post_xs = sorted({round((bbox([p])[0][0] + bbox([p])[1][0]) / 2, 2) for p in named(parts, "Handrail post") if bbox([p])[1][0] <= derived.runs[0].run_in + 1e-3})
    for a, b in zip(left, left[1:], strict=False):
        joint = (bbox([a])[1][0] + bbox([b])[0][0]) / 2
        assert min(abs(joint - x) for x in post_xs) < 4


@pytest.mark.parametrize("overrides", [{"total_rise_in": 12}, {"total_rise_in": 31, "layout": "straight"}, {"total_rise_in": 20, "layout": "switchback"}, {"total_rise_in": 40, "layout": "switchback", "clear_width_in": 60}])
def test_handrails_never_overlap_the_deck_area_in_plan(overrides):
    params, derived, parts = make(**overrides)
    w = derived.clear_width_in
    for p in handrail_parts(parts):
        (_, _, z0), (_, _, z1) = bbox([p])
        for run in derived.runs:
            assert z1 <= run.z_center - w / 2 + 1e-3 or z0 >= run.z_center + w / 2 - 1e-3, f"{p.name} enters the deck of run {run.index + 1}"
    # on both sides of each run, outside the stringers
    for p in named(parts, "Handrail post"):
        (_, _, z0), (_, _, z1) = bbox([p])
        assert z1 - z0 == pytest.approx(3.5)
    rails = named(parts, "Handrail")
    posts = named(parts, "Handrail post")
    for r in rails:
        (_, _, rz0), (_, _, rz1) = bbox([r])
        assert rz1 - rz0 == pytest.approx(1.5)
        assert any(bbox([p])[0][2] == pytest.approx(rz1, abs=1e-3) or bbox([p])[1][2] == pytest.approx(rz0, abs=1e-3) for p in posts)


def test_switchback_handrails_do_not_touch_each_other():
    _, derived, parts = make(total_rise_in=20, layout="switchback")
    run1 = [p for p in handrail_parts(parts) if bbox([p])[1][2] <= 24]
    run2 = [p for p in handrail_parts(parts) if bbox([p])[0][2] >= 24]
    assert run1 and run2
    assert max(bbox([p])[1][2] for p in run1) < min(bbox([p])[0][2] for p in run2)


def test_no_handrails_on_landings():
    _, _, parts = make(total_rise_in=31, layout="straight")
    assert all(p.group == "handrail" for p in parts if p.name in ("Handrail post", "Handrail"))
    assert not [p for p in parts if p.group == "landing_1" and p.name.startswith("Handrail")]
