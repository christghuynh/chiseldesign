"""GEO-20: step platform template: params, derive, parts, rules, skeleton and the plan built from it."""

import math
import random

import pytest

from app import templates
from app.cutlist import label_parts, part_length
from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.models import Part, Plan, RuleCheck
from app.plan import build_plan
from app.rules import check_design, sources
from app.rules.constants import PERMIT_NOTICE_SOURCE, STEP_MAX_RISER_IN, STEP_MIN_TREAD_IN
from app.rules import step_platform as rules
from app.templates import step_platform as sp
from app.util.units import format_ft_in

KEY = "step_platform"


def params(**values) -> sp.Params:
    values.setdefault("total_rise_in", 21)
    return sp.Params(**values)


def parts_of(**values) -> list[Part]:
    return sp.generate_parts(params(**values))


def by_name(parts: list[Part], name: str) -> list[Part]:
    return [p for p in parts if p.name == name]


def world_y_range(part: Part) -> tuple[float, float]:
    ys = [y for _, y in part.profile]
    return part.transform.pos[1] + min(ys), part.transform.pos[1] + max(ys)


def area(profile) -> float:
    n = len(profile)
    return sum(profile[i][0] * profile[(i + 1) % n][1] - profile[(i + 1) % n][0] * profile[i][1] for i in range(n)) / 2


# --- registry, schema, validation -------------------------------------------------------------


def test_registry_finds_the_template_with_all_interface_members():
    module = templates.registry()[KEY]
    assert module.KEY == KEY
    for attr in ("NAME", "DESCRIPTION", "Params", "derive", "generate_parts", "build_skeleton"):
        assert hasattr(module, attr)


def test_schema_and_defaults():
    info = next(i for i in templates.template_infos() if i.key == KEY)
    props = info.params_schema["properties"]
    assert info.params_schema["required"] == ["total_rise_in"]
    assert info.defaults == {"width_in": 36, "tread_depth_in": 11, "max_riser_in": 7, "step_count": None}
    assert (props["total_rise_in"]["minimum"], props["total_rise_in"]["maximum"]) == (1, 60)
    assert (props["width_in"]["minimum"], props["width_in"]["maximum"]) == (24, 72)
    assert (props["tread_depth_in"]["minimum"], props["tread_depth_in"]["maximum"]) == (8, 16)
    assert (props["max_riser_in"]["minimum"], props["max_riser_in"]["maximum"]) == (4, 9)
    for name in props:
        assert props[name]["description"]
        if name != "step_count":
            assert props[name]["unit"] == "in"
    assert "inferred" in sp.Params.__doc__


@pytest.mark.parametrize(
    "values, message",
    [
        ({}, "total_rise_in is required"),
        ({"total_rise_in": 0.5}, "total_rise_in"),
        ({"total_rise_in": 61}, "total_rise_in"),
        ({"total_rise_in": 20, "width_in": 23}, "width_in"),
        ({"total_rise_in": 20, "width_in": 73}, "width_in"),
        ({"total_rise_in": 20, "tread_depth_in": 7}, "tread_depth_in"),
        ({"total_rise_in": 20, "tread_depth_in": 17}, "tread_depth_in"),
        ({"total_rise_in": 20, "max_riser_in": 3.9}, "max_riser_in"),
        ({"total_rise_in": 20, "max_riser_in": 9.1}, "max_riser_in"),
        ({"total_rise_in": 20, "stair_style": "spiral"}, "Unknown parameter 'stair_style'"),
        ({"total_rise_in": "tall"}, "total_rise_in"),
    ],
)
def test_validate_params_errors_are_readable(values, message):
    with pytest.raises(ParamValidationError, match=message):
        templates.validate_params(KEY, values)


@pytest.mark.parametrize("values", [{"total_rise_in": 1}, {"total_rise_in": 60, "width_in": 72, "tread_depth_in": 8, "max_riser_in": 9}, {"total_rise_in": 20, "width_in": 24, "tread_depth_in": 16, "max_riser_in": 4}])
def test_bounds_are_inclusive(values):
    assert templates.validate_params(KEY, values).total_rise_in == values["total_rise_in"]


# --- derive -------------------------------------------------------------------------------------


def test_known_case_rise_21_is_three_risers_of_seven():
    d = sp.derive(params(total_rise_in=21))
    assert d.riser_count == 3 and d.tread_count == 2
    assert d.riser_height_in == pytest.approx(7)
    assert d.run_in == pytest.approx(22)
    assert d.tread_boards_per_tread == 2 and d.tread_span_in == pytest.approx(11.125)
    assert d.riser_material == "2x8_PT" and d.riser_rip_width_in == pytest.approx(7)
    assert d.stringer_diagonal_in == pytest.approx(math.hypot(22, 21))
    assert 0 < d.stringer_length_in <= lumber_spec("2x10_PT").max_stock_length_in


@pytest.mark.parametrize("rise, max_riser, count", [(7, 7, 1), (7.01, 7, 2), (14, 7, 2), (14.01, 7, 3), (60, 7, 9), (60, 9, 7), (1, 4, 1), (36, 4, 9)])
def test_riser_count_is_the_ceiling(rise, max_riser, count):
    d = sp.derive(params(total_rise_in=rise, max_riser_in=max_riser))
    assert d.riser_count == count
    assert d.tread_count == count - 1
    assert d.riser_height_in == pytest.approx(rise / count)
    assert d.riser_height_in <= max_riser + 1e-9


@pytest.mark.parametrize("depth, boards", [(8, 2), (11, 2), (11.25, 2), (11.3, 3), (16, 3)])
def test_tread_board_count_follows_the_depth(depth, boards):
    assert sp.derive(params(tread_depth_in=depth)).tread_boards_per_tread == boards


def test_a_tall_riser_uses_the_wider_board_and_a_full_width_riser_is_not_ripped():
    tall = sp.derive(params(total_rise_in=16, max_riser_in=9))  # 2 risers of 8
    assert tall.riser_material == "2x10_PT" and tall.riser_rip_width_in == pytest.approx(8)
    full = sp.derive(params(total_rise_in=14.5, max_riser_in=9))  # one riser of 7.25 = the width of a 2x8
    assert full.riser_count == 2 and full.riser_material == "2x8_PT" and full.riser_rip_width_in is None


def test_a_rise_that_needs_a_stringer_longer_than_the_stock_is_rejected():
    with pytest.raises(ParamValidationError, match=r"stringers would need a board .* longest 2x10_PT sold is 12' 0\""):
        sp.derive(params(total_rise_in=60, tread_depth_in=16))
    with pytest.raises(ParamValidationError):
        sp.generate_parts(params(total_rise_in=60, tread_depth_in=16))
    assert sp.derive(params(total_rise_in=60, tread_depth_in=11)).stringer_length_in <= 144


def test_a_single_riser_has_no_stringers_or_treads():
    parts = parts_of(total_rise_in=5)
    assert [p.name for p in parts] == ["Riser"]
    d = sp.derive(params(total_rise_in=5))
    assert not d.has_stringers and not d.has_treads and d.stringer_length_in == 0


# --- parts --------------------------------------------------------------------------------------


@pytest.mark.parametrize("rise, n", [(21, 3), (14.5, 3), (40, 6), (60, 9)])
def test_part_counts_names_groups_and_materials(rise, n):
    parts = parts_of(total_rise_in=rise)
    d = sp.derive(params(total_rise_in=rise))
    stringers, treads, risers = by_name(parts, "Stringer"), by_name(parts, "Tread board"), by_name(parts, "Riser")
    assert len(parts) == len(stringers) + len(treads) + len(risers)
    assert (len(stringers), len(treads), len(risers)) == (2, (n - 1) * d.tread_boards_per_tread, n)
    assert {p.group for p in stringers} == {"frame"}
    assert {p.group for p in treads} == {"treads"}
    assert {p.group for p in risers} == {"risers"}
    assert {p.material for p in stringers} == {"2x10_PT"}
    assert {p.material for p in treads} == {"5/4x6_PT_deck"}
    assert {p.material for p in risers} == {"2x8_PT"}
    assert all(p.transform.rot == (0.0, 0.0, 0.0) for p in parts)


def test_every_profile_is_ccw_non_degenerate_and_finite():
    for values in ({"total_rise_in": 21}, {"total_rise_in": 60}, {"total_rise_in": 13, "tread_depth_in": 9, "max_riser_in": 9}, {"total_rise_in": 3}):
        for part in parts_of(**values):
            assert len(part.profile) >= 3
            assert all(math.isfinite(c) for pt in part.profile for c in pt)
            assert all(math.isfinite(c) for c in part.transform.pos)
            assert math.isfinite(part.thickness) and part.thickness > 0
            assert area(part.profile) > 1e-3, f"{part.name} is clockwise or degenerate"


@pytest.mark.parametrize("values", [{"total_rise_in": 21}, {"total_rise_in": 60}, {"total_rise_in": 12, "tread_depth_in": 8}, {"total_rise_in": 2}])
def test_nothing_is_below_the_ground(values):
    parts = parts_of(**values)
    assert min(world_y_range(p)[0] for p in parts) == pytest.approx(0, abs=1e-9)
    assert all(world_y_range(p)[0] >= 0 for p in parts)


@pytest.mark.parametrize("rise, max_riser", [(21, 7), (14.5, 7), (37.3, 7), (60, 7), (60, 9), (5, 7)])
def test_the_top_of_the_last_riser_and_tread_is_the_total_rise(rise, max_riser):
    parts = parts_of(total_rise_in=rise, max_riser_in=max_riser)
    assert max(world_y_range(p)[1] for p in by_name(parts, "Riser")) == pytest.approx(rise, abs=1 / 16)
    treads = by_name(parts, "Tread board")
    if treads:
        d = sp.derive(params(total_rise_in=rise, max_riser_in=max_riser))
        assert max(world_y_range(p)[1] for p in treads) == pytest.approx(rise - d.riser_height_in, abs=1 / 16)
    assert max(world_y_range(p)[1] for p in parts) == pytest.approx(rise, abs=1 / 16)


def test_risers_and_treads_step_up_and_along_by_the_riser_height_and_tread_depth():
    parts = parts_of(total_rise_in=21, tread_depth_in=12)
    risers = sorted(by_name(parts, "Riser"), key=lambda p: p.transform.pos[0])
    assert [p.transform.pos[0] for p in risers] == [0, 12, 24]  # first riser's front face is the origin
    assert [world_y_range(p) for p in risers] == [pytest.approx((0, 7)), pytest.approx((7, 14)), pytest.approx((14, 21))]
    for p in risers:
        assert p.profile == [(0, 0), (1.5, 0), (1.5, pytest.approx(7)), (0, pytest.approx(7))]
    tops = sorted({round(world_y_range(p)[1], 3) for p in by_name(parts, "Tread board")})
    assert tops == [7, 14]


def test_everything_spans_the_width_and_the_stringers_are_flush_with_the_edges():
    width = 48
    parts = parts_of(total_rise_in=21, width_in=width)
    for p in by_name(parts, "Riser") + by_name(parts, "Tread board"):
        assert p.transform.pos[2] == pytest.approx(-width / 2)
        assert p.thickness == pytest.approx(width)
    stringers = by_name(parts, "Stringer")
    assert sorted((p.transform.pos[2], p.transform.pos[2] + p.thickness) for p in stringers) == [(-24, -22.5), (22.5, 24)]


def test_riser_rip_notes():
    ripped = by_name(parts_of(total_rise_in=21), "Riser")
    assert {tuple(p.cut_notes) for p in ripped} == {("Rip to 7 in wide",)}
    odd = by_name(parts_of(total_rise_in=20), "Riser")  # 3 risers of 6-2/3 in -> nearest sixteenth
    assert {tuple(p.cut_notes) for p in odd} == {("Rip to 6-11/16 in wide",)}
    assert by_name(parts_of(total_rise_in=14.5, max_riser_in=9), "Riser")[0].cut_notes == []  # 7.25 = a full 2x8


def test_stringer_sawtooth_vertices_for_a_small_case():
    # rise 12, tread 8 -> 2 risers of 6 (a 6-8-10 triangle). Hand check, x measured from the riser's back face:
    #   notch depth = 6*8/10 = 4.8, throat = 9.25 - 4.8 = 4.45 square to the slope = 4.45 * 10/8 = 5.5625 vertical.
    #   lower edge: y = 0.75 x - 1 - 5.5625 (1 = tread thickness) -> meets the ground at x = 8.75 and is 2.0625 high at
    #   the plumb cut x = 8 + 3.5 = 11.5. The top ledge is at 2*6 - 1 = 11, the tooth tip at (8, 11), the notch corner
    #   at (8, 5) and the first floor at 6 - 1 = 5.
    parts = parts_of(total_rise_in=12, tread_depth_in=8)
    expected = [(0, 0), (8.75, 0), (11.5, 2.0625), (11.5, 11), (8, 11), (8, 5), (0, 5)]
    stringers = by_name(parts, "Stringer")
    assert len(stringers) == 2
    for p in stringers:
        assert len(p.profile) == len(expected)
        for got, want in zip(p.profile, expected, strict=True):
            assert got == pytest.approx(want, abs=1e-3)
        assert p.transform.pos[:2] == (1.5, 0)
        assert p.thickness == 1.5
        assert part_length(p) == pytest.approx(11.5)
    assert sp.derive(params(total_rise_in=12, tread_depth_in=8)).stringer_throat_in == pytest.approx(4.45)


def test_stringer_has_a_level_bottom_and_a_plumb_top_cut_for_the_default_case():
    (a, _b) = by_name(parts_of(total_rise_in=21), "Stringer")
    ys = [y for _, y in a.profile]
    xs = [x for x, _ in a.profile]
    assert min(ys) == 0
    assert sum(1 for _, y in a.profile if y == 0) == 2  # a level edge on the ground
    assert sum(1 for x, _ in a.profile if x == max(xs)) == 2  # a plumb edge at the top end
    assert 0 < sp.derive(params(total_rise_in=21)).stringer_length_in <= 144
    # notch floors sit at tread-underside height (k*h - 1) and the top ledge at 3*7 - 1 = 20
    heights = {y for _, y in a.profile}
    assert {6, 13, 20} <= heights


def test_stringer_length_matches_the_cut_list():
    for rise in (21, 40, 60):
        d = sp.derive(params(total_rise_in=rise))
        stringer = by_name(parts_of(total_rise_in=rise), "Stringer")[0]
        assert part_length(stringer) == pytest.approx(d.stringer_length_in)


def test_every_board_fits_the_longest_stock():
    for values in ({"total_rise_in": 60}, {"total_rise_in": 60, "width_in": 72, "tread_depth_in": 8, "max_riser_in": 9}):
        for part in parts_of(**values):
            assert part_length(part) <= lumber_spec(part.material).max_stock_length_in + 1e-9


def test_determinism():
    first = [p.model_dump() for p in parts_of(total_rise_in=37.3, tread_depth_in=12.5, width_in=41)]
    second = [p.model_dump() for p in parts_of(total_rise_in=37.3, tread_depth_in=12.5, width_in=41)]
    assert first == second
    p = params(total_rise_in=37.3)
    assert sp.derive(p) == sp.derive(p)


# --- rules --------------------------------------------------------------------------------------


def run_rules(**values) -> dict[str, RuleCheck]:
    p = params(**values)
    return {c.id: c for c in check_design(KEY, p, sp.derive(p), sp.generate_parts(p))}


def apply(check: RuleCheck, **values) -> sp.Params:
    return params(**{**values, **check.fix.params_patch})


def test_rules_are_found_and_ordered_and_use_the_constants():
    checks = run_rules(total_rise_in=21)
    assert list(checks) == ["STEP-001", "STEP-002", "STEP-003"]
    assert checks["STEP-001"].title == "Riser height within maximum"
    assert checks["STEP-002"].title == "Tread deep enough"
    assert checks["STEP-003"].title == "Permit and local code notice"
    assert checks["STEP-001"].source_ref == STEP_MAX_RISER_IN.source_key
    assert checks["STEP-002"].source_ref == STEP_MIN_TREAD_IN.source_key
    assert checks["STEP-003"].source_ref == PERMIT_NOTICE_SOURCE.source_key
    for c in checks.values():
        assert c.source_ref in sources()


def test_riser_rule_at_its_threshold():
    at = run_rules(total_rise_in=21)["STEP-001"]  # exactly the limit
    assert at.status == "pass" and at.fix is None
    assert format_ft_in(7) in at.detail
    just_over = run_rules(total_rise_in=21.03, max_riser_in=9)["STEP-001"]  # 3 risers of 7.01
    assert just_over.status == "fail"
    assert format_ft_in(7.01) in just_over.detail and format_ft_in(STEP_MAX_RISER_IN.value) in just_over.detail
    just_under = run_rules(total_rise_in=20.97, max_riser_in=9)["STEP-001"]
    assert just_under.status == "pass"


def test_riser_fix_resolves_the_check():
    values = {"total_rise_in": 27, "max_riser_in": 9}  # 3 risers of 9
    failing = run_rules(**values)["STEP-001"]
    assert failing.status == "fail" and failing.fix is not None
    assert failing.fix.params_patch == {"max_riser_in": STEP_MAX_RISER_IN.value}
    fixed = apply(failing, **values)
    assert {c.id: c for c in check_design(KEY, fixed, sp.derive(fixed), sp.generate_parts(fixed))}["STEP-001"].status == "pass"


def test_riser_fix_is_only_offered_when_it_works():
    # 7 risers of 8.6 in with 16 in treads; the fix would need 9 risers, whose stringer is too long to buy.
    values = {"total_rise_in": 60, "tread_depth_in": 16, "max_riser_in": 9}
    p = params(**values)
    derived = sp.derive(p)
    assert derived.riser_height_in > STEP_MAX_RISER_IN.value
    check = rules.check(p, derived, [])[0]
    assert check.status == "fail" and check.fix is None


def test_tread_rule_at_its_threshold():
    at = run_rules(tread_depth_in=11)["STEP-002"]
    assert at.status == "pass" and at.fix is None
    below = run_rules(tread_depth_in=10.99)["STEP-002"]
    assert below.status == "fail"
    assert format_ft_in(10.99) in below.detail and format_ft_in(11) in below.detail
    assert run_rules(tread_depth_in=16)["STEP-002"].status == "pass"


def test_tread_fix_resolves_the_check():
    values = {"tread_depth_in": 9}
    failing = run_rules(**values)["STEP-002"]
    assert failing.status == "fail" and failing.fix.params_patch == {"tread_depth_in": STEP_MIN_TREAD_IN.value}
    fixed = apply(failing, **values)
    assert {c.id: c for c in check_design(KEY, fixed, sp.derive(fixed), sp.generate_parts(fixed))}["STEP-002"].status == "pass"


def test_permit_notice_is_always_info():
    for values in ({"total_rise_in": 21}, {"total_rise_in": 30, "tread_depth_in": 8, "max_riser_in": 9}):
        c = run_rules(**values)["STEP-003"]
        assert c.status == "info" and c.fix is None
        assert c.detail == "Guidelines, not code compliance. Check local permit requirements."


# --- skeleton -----------------------------------------------------------------------------------


def skeleton(**values):
    p = params(**values)
    parts = label_parts(sp.generate_parts(p))
    return sp.build_skeleton(p, parts), parts


def test_skeleton_for_the_default_case():
    steps, parts = skeleton(total_rise_in=21)
    assert [s.action_key for s in steps] == ["cut_stringers", "cut_treads_and_risers", "set_stringers", "install_risers", "install_treads", "final_check"]
    assert [s.phase for s in steps] == ["cut", "cut", "assemble", "install", "install", "check"]
    assert steps[-1].title == "Check every step is level and solid"
    label = {name: sorted({p.label for p in parts if p.name == name}) for name in ("Stringer", "Tread board", "Riser")}
    assert steps[0].part_labels == label["Stringer"] == steps[2].part_labels
    assert steps[3].part_labels == label["Riser"]
    assert steps[4].part_labels == label["Tread board"]
    assert steps[1].part_labels == sorted(label["Tread board"] + label["Riser"])
    assert steps[5].part_labels == steps[1].part_labels
    known = {p.label for p in parts}
    assert all(set(s.part_labels) <= known for s in steps)
    assert all(s.part_labels == sorted(set(s.part_labels)) for s in steps)


def test_skeleton_steps_are_conditional():
    steps, _ = skeleton(total_rise_in=5)  # a single riser: no stringers, no treads
    assert [s.action_key for s in steps] == ["cut_treads_and_risers", "install_risers", "final_check"]
    steps, _ = skeleton(total_rise_in=12)
    assert "install_treads" in [s.action_key for s in steps]


def test_skeleton_is_deterministic():
    assert skeleton(total_rise_in=33)[0] == skeleton(total_rise_in=33)[0]


# --- end to end: parts -> cut list -> plan ------------------------------------------------------


def check_plan(plan: Plan, labelled: list[Part]) -> None:
    assert sorted(pid for row in plan.cut_list for pid in row.part_ids) == sorted(p.id for p in labelled)
    for row in plan.cut_list:
        assert row.qty == len(row.part_ids)
        assert row.length_display == format_ft_in(row.length_in)
    placed = sorted(q.part_id for layout in plan.layouts for q in layout.pieces)
    assert placed == sorted(p.id for p in labelled)  # every piece placed; nothing was oversize
    assert all(not any("Longer than" in n for n in row.cut_notes) for row in plan.cut_list)
    assert all(0 < layout.utilization <= 1 + 1e-9 for layout in plan.layouts)
    assert plan.subtotal == pytest.approx(round(sum(i.subtotal for i in plan.shopping), 2))
    assert plan.total == pytest.approx(round(plan.subtotal + plan.tax, 2))
    assert plan.total > 0
    assert Plan.model_validate(plan.model_dump()) == plan


def test_default_design_builds_a_plan():
    labelled = label_parts(sp.generate_parts(params(total_rise_in=21)))
    plan = build_plan(labelled)
    check_plan(plan, labelled)
    assert [(r.name, r.qty) for r in plan.cut_list] == [("Stringer", 2), ("Riser", 3), ("Tread board", 4)]
    assert {r.material for r in plan.cut_list} == {"2x10_PT", "2x8_PT", "5/4x6_PT_deck"}


def test_randomized_sweep_of_valid_params_builds_valid_plans():
    rng = random.Random(20260926)
    built = rejected = 0
    for _ in range(80):
        values = {
            "total_rise_in": round(rng.uniform(1, 60), 2),
            "width_in": round(rng.uniform(24, 72), 1),
            "tread_depth_in": round(rng.uniform(8, 16), 2),
            "max_riser_in": round(rng.uniform(4, 9), 2),
        }
        p = templates.validate_params(KEY, values)
        try:
            parts = sp.generate_parts(p)
        except ParamValidationError as exc:  # only the documented too-long-stringer rejection
            assert "stringers would need a board" in str(exc)
            rejected += 1
            continue
        labelled = label_parts(parts)
        check_plan(build_plan(labelled), labelled)
        derived = sp.derive(p)
        assert len(by_name(parts, "Riser")) == derived.riser_count
        assert derived.riser_height_in <= p.max_riser_in + 1e-9
        assert max(world_y_range(q)[1] for q in parts) == pytest.approx(p.total_rise_in, abs=1 / 16)
        assert min(world_y_range(q)[0] for q in parts) >= -1e-9
        assert all(area(q.profile) > 0 for q in parts)
        steps = sp.build_skeleton(p, labelled)
        assert steps[-1].action_key == "final_check"
        checks = check_design(KEY, p, derived, labelled)
        assert [c.id for c in checks] == ["STEP-001", "STEP-002", "STEP-003"]
        built += 1
    assert built >= 40 and built + rejected == 80
