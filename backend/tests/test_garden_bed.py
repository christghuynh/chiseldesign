"""GEO-19: raised garden bed template, rules and end-to-end plan."""

import itertools
import math
import random

import pytest

from app import templates
from app.cutlist import label_parts, part_length
from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.models import Part, Plan
from app.plan import build_plan
from app.rules import check_design, sources
from app.rules.constants import (
    BED_MAX_HEIGHT_IN,
    BED_MAX_WIDTH_BOTH_SIDES_IN,
    BED_MAX_WIDTH_ONE_SIDE_IN,
    BED_MIN_HEIGHT_IN,
    BED_PATH_CLEARANCE_IN,
)
from app.templates.garden_bed import Params, build_skeleton, derive, generate_parts
from app.templates.geometry import signed_area
from app.util.units import format_ft_in


def P(**kw) -> Params:
    return Params(**kw)


def box(part: Part) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """World (x, y, z) ranges of an unrotated part."""
    (px, py, pz), xs, ys = part.transform.pos, [p[0] for p in part.profile], [p[1] for p in part.profile]
    return ((px + min(xs), px + max(xs)), (py + min(ys), py + max(ys)), (pz, pz + part.thickness))


def names(parts: list[Part]) -> list[str]:
    return [p.name for p in parts]


# --- registry and params ------------------------------------------------------------------------


def test_registry_finds_garden_bed_with_schema_and_defaults():
    module = templates.registry()["garden_bed"]
    assert module.KEY == "garden_bed"
    info = next(i for i in templates.template_infos() if i.key == "garden_bed")
    props = info.params_schema["properties"]
    assert (props["length_in"]["minimum"], props["length_in"]["maximum"]) == (24, 144)
    assert (props["width_in"]["minimum"], props["width_in"]["maximum"]) == (12, 48)
    assert (props["height_in"]["minimum"], props["height_in"]["maximum"]) == (12, 48)
    assert props["access"]["enum"] == ["one_side", "both_sides"]
    assert props["board"]["enum"] == ["2x10_PT", "2x8_PT"]
    assert props["cap_rail"]["type"] == "boolean"
    assert props["length_in"]["unit"] == "in"
    assert info.params_schema.get("required", []) == []
    assert info.defaults == {"length_in": 72, "width_in": 24, "height_in": 30, "access": "one_side", "board": "2x10_PT", "cap_rail": True}


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"length_in": 23}, "length_in"),
        ({"length_in": 145}, "length_in"),
        ({"width_in": 11}, "width_in"),
        ({"width_in": 49}, "width_in"),
        ({"height_in": 11}, "height_in"),
        ({"height_in": 49}, "height_in"),
        ({"access": "roof"}, "access"),
        ({"board": "2x12_PT"}, "board"),
        ({"cap_rail": "maybe"}, "cap_rail"),
        ({"depth": 3}, "Unknown parameter 'depth'"),
    ],
)
def test_validate_params_rejects_bad_values_readably(values, message):
    with pytest.raises(ParamValidationError, match=message):
        templates.validate_params("garden_bed", values)


def test_validate_params_accepts_the_bounds():
    for values in ({"length_in": 24, "width_in": 12, "height_in": 12}, {"length_in": 144, "width_in": 48, "height_in": 48}):
        assert templates.validate_params("garden_bed", values).length_in == values["length_in"]


# --- derive --------------------------------------------------------------------------------------


def test_default_derive():
    d = derive(P())
    assert d.course_count == 4 and d.course_height_in == 28.5 and d.post_height_in == 28.5
    assert d.ripped_width_in == pytest.approx(0.75) and d.course_widths_in == (9.25, 9.25, 9.25, 0.75)
    assert (d.outer_length_in, d.outer_width_in) == (72, 24)
    assert (d.inner_length_in, d.inner_width_in) == (69, 21)
    assert d.long_board_length_in == 65 and d.end_board_length_in == 17


def test_exact_multiple_has_no_rip():
    d = derive(P(height_in=3 * 9.25 + 1.5))
    assert d.course_count == 3 and d.ripped_width_in is None and d.ripped_course_count == 0


def test_no_cap_rail_is_taller_stack():
    with_cap, without = derive(P()), derive(P(cap_rail=False))
    assert without.course_height_in == 30 and without.post_height_in == 30
    assert without.course_count == 4 and without.ripped_width_in == pytest.approx(2.25)
    assert without.course_height_in > with_cap.course_height_in
    assert derive(P(cap_rail=False, height_in=27.75)).course_count == 3


def test_board_choice_changes_course_count():
    assert derive(P(board="2x8_PT")).course_count == 4  # ceil(28.5 / 7.25)
    assert derive(P(board="2x8_PT", height_in=48)).course_count == 7


def test_derive_is_frozen():
    with pytest.raises(AttributeError):
        derive(P()).course_count = 9  # type: ignore[misc]


def test_a_board_longer_than_its_stock_is_a_readable_error():
    too_long = Params.model_construct(length_in=300.0, width_in=24.0, height_in=30.0, access="one_side", board="2x10_PT", cap_rail=True)
    with pytest.raises(ParamValidationError, match="longest 2x10_PT sold is 12' 0\""):
        derive(too_long)


# --- parts ---------------------------------------------------------------------------------------


def test_default_part_counts_names_and_groups():
    parts = generate_parts(P())
    counts = {(p.name, p.group): 0 for p in parts}
    for p in parts:
        counts[(p.name, p.group)] += 1
    assert counts == {
        ("Side course (long)", "sides"): 8,
        ("Side course (end)", "sides"): 8,
        ("Corner post", "posts"): 4,
        ("Cap rail", "cap"): 4,
    }
    assert len(parts) == 24
    assert {p.material for p in parts if p.name == "Corner post"} == {"4x4_PT"}
    assert {p.material for p in parts if p.name == "Cap rail"} == {"2x6_PT"}
    assert {p.material for p in parts if p.group == "sides"} == {"2x10_PT"}


def test_ripped_course_is_one_course_with_a_note():
    parts = generate_parts(P())
    ripped = [p for p in parts if p.cut_notes]
    assert len(ripped) == 4 and {p.name for p in ripped} == {"Side course (long)", "Side course (end)"}
    assert all(p.cut_notes == ["Rip to 3/4 in wide"] for p in ripped)
    assert {round(box(p)[1][1], 3) for p in ripped} == {28.5}
    assert max(box(p)[1][1] for p in parts if p.group == "sides") == 28.5


def test_a_height_that_is_not_a_multiple_produces_one_ripped_course():
    d = derive(P(height_in=24, cap_rail=False))
    assert d.course_widths_in == (9.25, 9.25, 5.5) and d.ripped_width_in == 5.5
    parts = generate_parts(P(height_in=24, cap_rail=False))
    assert {p.cut_notes[0] for p in parts if p.cut_notes} == {"Rip to 5-1/2 in wide"}
    assert sum(1 for p in parts if p.cut_notes) == 4


def test_no_cap_rail_has_no_cap_parts_and_taller_courses():
    capped, bare = generate_parts(P()), generate_parts(P(cap_rail=False))
    assert not [p for p in bare if p.group == "cap" or p.name == "Cap rail"]
    assert len(bare) == len(capped) - 4
    top = lambda parts: max(box(p)[1][1] for p in parts)  # noqa: E731
    assert top(bare) == 30 and top(capped) == 30
    assert max(box(p)[1][1] for p in bare if p.group == "sides") > max(box(p)[1][1] for p in capped if p.group == "sides")


@pytest.mark.parametrize("kwargs", [{}, {"length_in": 144, "width_in": 48, "height_in": 48}, {"length_in": 24, "width_in": 12, "height_in": 12}, {"cap_rail": False, "board": "2x8_PT"}])
def test_outer_footprint_is_exactly_length_by_width(kwargs):
    p = P(**kwargs)
    boxes = [box(part) for part in generate_parts(p)]
    assert min(b[0][0] for b in boxes) == pytest.approx(-p.length_in / 2)
    assert max(b[0][1] for b in boxes) == pytest.approx(p.length_in / 2)
    assert min(b[2][0] for b in boxes) == pytest.approx(-p.width_in / 2)
    assert max(b[2][1] for b in boxes) == pytest.approx(p.width_in / 2)
    assert min(b[1][0] for b in boxes) == 0
    assert max(b[1][1] for b in boxes) == pytest.approx(p.height_in)


@pytest.mark.parametrize("kwargs", [{}, {"cap_rail": False}, {"length_in": 24, "width_in": 12, "height_in": 12}, {"board": "2x8_PT", "height_in": 41}])
def test_profiles_are_ccw_finite_and_nothing_is_below_grade(kwargs):
    for part in generate_parts(P(**kwargs)):
        assert signed_area(part.profile) > 1e-6, part.name
        assert all(math.isfinite(v) for point in part.profile for v in point)
        assert math.isfinite(part.thickness) and part.thickness > 0
        assert part.transform.rot == (0.0, 0.0, 0.0)
        assert box(part)[1][0] >= 0


@pytest.mark.parametrize("kwargs", [{}, {"cap_rail": False}, {"length_in": 24, "width_in": 12, "height_in": 12}, {"length_in": 144, "width_in": 48, "height_in": 48}])
def test_no_two_parts_overlap(kwargs):
    parts = generate_parts(P(**kwargs))
    for a, b in itertools.combinations(parts, 2):
        overlap = [min(x[1], y[1]) - max(x[0], y[0]) for x, y in zip(box(a), box(b), strict=True)]
        assert min(overlap) <= 1e-6, (a.name, b.name, overlap)


def test_posts_are_full_height():
    for kwargs in ({}, {"cap_rail": False}, {"height_in": 47}):
        p = P(**kwargs)
        d = derive(p)
        posts = [part for part in generate_parts(p) if part.name == "Corner post"]
        assert len(posts) == 4
        for post in posts:
            (x0, x1), (y0, y1), (z0, z1) = box(post)
            assert (y0, y1) == (0, pytest.approx(d.post_height_in))
            assert x1 - x0 == pytest.approx(3.5) and z1 - z0 == pytest.approx(3.5)
        courses = [part for part in generate_parts(p) if part.group == "sides"]
        assert max(box(c)[1][1] for c in courses) == pytest.approx(d.post_height_in)
        # the four posts sit in the four distinct corners
        assert len({(round(box(q)[0][0]), round(box(q)[2][0])) for q in posts}) == 4


@pytest.mark.parametrize("kwargs", [{}, {"length_in": 144, "width_in": 48, "height_in": 48}, {"board": "2x8_PT", "length_in": 144}, {"length_in": 24, "width_in": 12, "height_in": 12}])
def test_every_board_fits_its_stock(kwargs):
    for part in generate_parts(P(**kwargs)):
        assert part_length(part) <= lumber_spec(part.material).max_stock_length_in


def test_long_sides_are_single_boards_at_the_maximum_length():
    parts = generate_parts(P(length_in=144))
    longs = [p for p in parts if p.name == "Side course (long)"]
    assert max(part_length(p) for p in longs) == 137


def test_narrow_bed_short_boards_carry_their_true_length_in_a_note():
    parts = generate_parts(P(width_in=12, height_in=12))
    ends = [p for p in parts if p.name == "Side course (end)" and p.profile[2][1] == 9.25]  # full-width boards: 5 in long, 9.25 in wide
    assert ends and all(any(n.startswith("Cut to ") for n in p.cut_notes) for p in ends)
    caps = [p for p in parts if p.name == "Cap rail" and p.thickness < 5.5]
    assert caps and all("Cut to 1 in long" in p.cut_notes for p in caps)


def test_generate_parts_is_deterministic():
    a = [p.model_dump() for p in generate_parts(P())]
    b = [p.model_dump() for p in generate_parts(P())]
    assert a == b
    assert [p.model_dump() for p in generate_parts(P(access="both_sides"))] == a  # access is rules-only


# --- skeleton ------------------------------------------------------------------------------------


def test_skeleton_default_steps_and_labels():
    parts = label_parts(generate_parts(P()))
    steps = build_skeleton(P(), parts)
    assert [(s.phase, s.action_key) for s in steps] == [("cut", "cut_boards"), ("assemble", "assemble_courses"), ("install", "attach_cap_rail"), ("check", "level_and_fill")]
    assert next(s for s in steps if s.action_key == "assemble_courses").title == "Assemble the courses on the posts"
    assert next(s for s in steps if s.action_key == "level_and_fill").title == "Level the bed and fill it"
    by_name = {}
    for part in parts:
        by_name.setdefault(part.name, set()).add(part.label)
    known = {p.label for p in parts}
    for step in steps:
        assert step.part_labels == sorted(set(step.part_labels)) and set(step.part_labels) <= known
    assert steps[0].part_labels == sorted(known)
    assert steps[1].part_labels == sorted(by_name["Side course (long)"] | by_name["Side course (end)"] | by_name["Corner post"])
    assert steps[2].part_labels == sorted(by_name["Cap rail"])


def test_skeleton_without_cap_rail_has_no_cap_step():
    p = P(cap_rail=False)
    steps = build_skeleton(p, label_parts(generate_parts(p)))
    assert [s.action_key for s in steps] == ["cut_boards", "assemble_courses", "level_and_fill"]


def test_skeleton_without_parts_has_no_steps():
    assert build_skeleton(P(), []) == []


# --- rules ---------------------------------------------------------------------------------------


def run_rules(**kw):
    p = P(**kw)
    d = derive(p)
    return {c.id: c for c in check_design("garden_bed", p, d, generate_parts(p))}


def test_rules_default_bed():
    checks = run_rules()
    assert list(checks) == ["BED-001", "BED-002", "BED-003"]
    assert checks["BED-001"].status == "pass" and checks["BED-001"].fix is None
    assert checks["BED-002"].status == "pass" and checks["BED-002"].fix is None
    assert checks["BED-003"].status == "info"
    assert format_ft_in(BED_PATH_CLEARANCE_IN.value) in checks["BED-003"].detail
    assert checks["BED-001"].title == "Height in accessible range"
    assert checks["BED-002"].title == "Reach: width within limit"
    assert checks["BED-003"].title == "Path clearance around the bed"


def test_rule_sources_exist_and_come_from_the_constants():
    checks = run_rules()
    assert checks["BED-001"].source_ref == BED_MIN_HEIGHT_IN.source_key == BED_MAX_HEIGHT_IN.source_key
    assert checks["BED-002"].source_ref == BED_MAX_WIDTH_ONE_SIDE_IN.source_key
    assert checks["BED-003"].source_ref == BED_PATH_CLEARANCE_IN.source_key
    assert all(c.source_ref in sources() for c in checks.values())


@pytest.mark.parametrize(
    ("height", "status", "patch"),
    [
        (12, "warn", 15),
        (14.9, "warn", 15),
        (15, "pass", None),
        (30, "pass", None),
        (34, "pass", None),
        (34.1, "warn", 34),
        (48, "warn", 34),
    ],
)
def test_height_rule_thresholds_and_fix(height, status, patch):
    check = run_rules(height_in=height)["BED-001"]
    assert check.status == status
    if patch is None:
        assert check.fix is None
        return
    assert check.fix is not None and check.fix.params_patch == {"height_in": patch}
    assert run_rules(height_in=patch)["BED-001"].status == "pass"
    assert format_ft_in(height) in check.detail


@pytest.mark.parametrize(
    ("access", "width", "status", "limit"),
    [
        ("one_side", 12, "pass", None),
        ("one_side", 24, "pass", None),
        ("one_side", 24.5, "warn", 24),
        ("one_side", 48, "warn", 24),
        ("both_sides", 24.5, "pass", None),
        ("both_sides", 48, "pass", None),
    ],
)
def test_reach_rule_thresholds_and_fix(access, width, status, limit):
    check = run_rules(access=access, width_in=width)["BED-002"]
    assert check.status == status
    if limit is None:
        assert check.fix is None
        return
    assert check.fix is not None and check.fix.params_patch == {"width_in": limit}
    assert run_rules(access=access, width_in=limit)["BED-002"].status == "pass"


def test_reach_limits_come_from_the_constants():
    assert BED_MAX_WIDTH_ONE_SIDE_IN.value < BED_MAX_WIDTH_BOTH_SIDES_IN.value
    assert run_rules(width_in=BED_MAX_WIDTH_ONE_SIDE_IN.value + 1)["BED-002"].status == "warn"
    assert run_rules(access="both_sides", width_in=BED_MAX_WIDTH_BOTH_SIDES_IN.value)["BED-002"].status == "pass"


def test_every_offered_fix_resolves_its_check_for_the_whole_grid():
    offered = 0
    for height, width, access in itertools.product((12, 20, 24, 36, 40, 48), (12, 24, 30, 48), ("one_side", "both_sides")):
        for check in run_rules(height_in=height, width_in=width, access=access).values():
            if check.fix is None:
                continue
            offered += 1
            assert check.status == "warn"
            patched = {"height_in": height, "width_in": width, "access": access, **check.fix.params_patch}
            assert run_rules(**patched)[check.id].status == "pass", (check.id, patched)
    assert offered > 10


def test_a_fix_whose_result_is_not_valid_params_is_not_offered(monkeypatch):
    from app.rules import garden_bed as rules

    monkeypatch.setattr(rules, "BED_MAX_HEIGHT_IN", type(BED_MAX_HEIGHT_IN)(60.0, "x", "in", "test"))
    monkeypatch.setattr(rules, "BED_MIN_HEIGHT_IN", type(BED_MIN_HEIGHT_IN)(60.0, "x", "in", "test"))
    p = P(height_in=30)
    check = rules.check(p, derive(p), [])[0]
    assert check.status == "warn" and check.fix is None  # 60 is above the 48 in height bound


# --- end to end ----------------------------------------------------------------------------------


def assert_valid_plan(p: Params) -> Plan:
    labelled = label_parts(generate_parts(p))
    plan = build_plan(labelled, {"contractor_quote_cad": 500.0})
    assert isinstance(plan, Plan)
    placed = sorted(piece.part_id for layout in plan.layouts for piece in layout.pieces)
    assert placed == sorted(part.id for part in labelled), "every part must be placed on a board"
    assert sum(row.qty for row in plan.cut_list) == len(labelled)
    assert {row.label for row in plan.cut_list} == {part.label for part in labelled}
    assert plan.subtotal == pytest.approx(sum(item.subtotal for item in plan.shopping), abs=0.01)
    assert plan.total == pytest.approx(plan.subtotal + plan.tax, abs=0.01)
    assert plan.contractor_quote == 500.0 and plan.savings == pytest.approx(500.0 - plan.total, abs=0.01)
    assert plan.total > 0 and all(item.qty > 0 for item in plan.shopping)
    assert not any("Longer than" in note for row in plan.cut_list for note in row.cut_notes)
    for layout in plan.layouts:
        assert 0 < layout.utilization <= 1 + 1e-9
    return plan


def test_end_to_end_default_bed():
    plan = assert_valid_plan(P())
    assert {row.material for row in plan.cut_list} == {"2x10_PT", "4x4_PT", "2x6_PT"}
    assert any("Rip to 3/4 in wide" in row.cut_notes for row in plan.cut_list)


def test_end_to_end_randomized_sweep():
    rng = random.Random(20260926)
    for _ in range(60):
        p = P(
            length_in=round(rng.uniform(24, 144), 2),
            width_in=round(rng.uniform(12, 48), 2),
            height_in=round(rng.uniform(12, 48), 2),
            access=rng.choice(["one_side", "both_sides"]),
            board=rng.choice(["2x10_PT", "2x8_PT"]),
            cap_rail=rng.random() < 0.5,
        )
        assert_valid_plan(p)
        parts = generate_parts(p)
        assert [x.model_dump() for x in parts] == [x.model_dump() for x in generate_parts(p)]
        assert all(box(x)[1][0] >= 0 for x in parts)

