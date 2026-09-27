"""GEO-21: the workbench template (registry, parts, skeleton, and the whole pipeline to a plan)."""

import math
import random
from collections import Counter

import pytest

from app import templates
from app.cutlist import label_parts, sheet_piece_dims
from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.models import Part, Plan
from app.plan import build_plan
from app.templates import workbench
from app.templates.geometry import signed_area
from app.templates.workbench import Params

EPS = 1e-6


def make(**overrides) -> Params:
    return templates.validate_params("workbench", overrides)  # type: ignore[return-value]


def parts_of(**overrides) -> list[Part]:
    return workbench.generate_parts(make(**overrides))


def bounds(part: Part) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """World (x, y, z) ranges; parts are never rotated, so this is exact."""
    assert part.transform.rot == (0.0, 0.0, 0.0)
    px, py, pz = part.transform.pos
    xs = [p[0] for p in part.profile]
    ys = [p[1] for p in part.profile]
    return ((px + min(xs), px + max(xs)), (py + min(ys), py + max(ys)), (pz, pz + part.thickness))


def names(parts: list[Part]) -> Counter:
    return Counter(p.name for p in parts)


# ----------------------------------------------------------------------------- registry and params


def test_registry_finds_the_workbench_with_schema_and_defaults():
    assert "workbench" in templates.registry()
    info = next(i for i in templates.template_infos() if i.key == "workbench")
    assert info.name == "Workbench"
    assert info.defaults == {"width_in": 48, "depth_in": 24, "height_in": 34, "lower_shelf": True, "shelf_height_in": 10.0}
    props = info.params_schema["properties"]
    assert (props["width_in"]["minimum"], props["width_in"]["maximum"]) == (24, 96)
    assert (props["depth_in"]["minimum"], props["depth_in"]["maximum"]) == (12, 48)
    assert (props["height_in"]["minimum"], props["height_in"]["maximum"]) == (24, 48)
    assert props["lower_shelf"]["type"] == "boolean"
    assert props["width_in"]["unit"] == "in"
    assert not info.params_schema.get("required")


def test_the_module_exposes_the_template_interface():
    for attr in ("KEY", "NAME", "DESCRIPTION", "Params", "derive", "generate_parts", "build_skeleton"):
        assert hasattr(workbench, attr)


@pytest.mark.parametrize(
    "values",
    [{"width_in": 23.9}, {"width_in": 96.1}, {"depth_in": 11}, {"depth_in": 49}, {"height_in": 23}, {"height_in": 49}],
)
def test_out_of_bounds_values_are_rejected_readably(values):
    (name,) = values
    with pytest.raises(ParamValidationError, match=name):
        templates.validate_params("workbench", values)


def test_unknown_and_mistyped_params_are_rejected_readably():
    with pytest.raises(ParamValidationError, match="Unknown parameter 'colour'"):
        templates.validate_params("workbench", {"colour": "red"})
    with pytest.raises(ParamValidationError, match="lower_shelf"):
        templates.validate_params("workbench", {"lower_shelf": "maybe"})


def test_bounds_are_inclusive():
    for values in ({"width_in": 24, "depth_in": 12, "height_in": 24}, {"width_in": 96, "depth_in": 48, "height_in": 48}):
        parts = parts_of(**values)
        assert parts
    assert make().model_dump() == {"width_in": 48, "depth_in": 24, "height_in": 34, "lower_shelf": True, "shelf_height_in": 10.0}


# ----------------------------------------------------------------------------- parts


def test_default_bench_with_shelf_has_twelve_parts_in_the_expected_materials():
    parts = parts_of()
    assert names(parts) == {"Leg": 4, "Apron (long)": 2, "Apron (short)": 2, "Top": 1, "Shelf support": 2, "Lower shelf": 1}
    assert len(parts) == 12
    materials = {p.name: p.material for p in parts}
    assert materials == {
        "Leg": "4x4_PT", "Apron (long)": "2x4_PT", "Apron (short)": "2x4_PT", "Top": "3/4_ext_ply",
        "Shelf support": "2x4_PT", "Lower shelf": "3/4_ext_ply",
    }
    groups = Counter(p.group for p in parts)
    assert groups == {"legs": 4, "aprons": 4, "top": 1, "shelf": 3}


def test_bench_without_shelf_has_only_legs_aprons_and_top():
    parts = parts_of(lower_shelf=False)
    assert names(parts) == {"Leg": 4, "Apron (long)": 2, "Apron (short)": 2, "Top": 1}
    assert {p.group for p in parts} == {"legs", "aprons", "top"}


def test_top_surface_is_exactly_the_height_and_legs_reach_the_floor():
    for height in (24, 30, 34, 36.5, 48):
        parts = parts_of(height_in=height)
        top = next(p for p in parts if p.name == "Top")
        assert bounds(top)[1][1] == pytest.approx(height, abs=EPS)
        assert max(bounds(p)[1][1] for p in parts) == pytest.approx(height, abs=EPS)
        legs = [p for p in parts if p.name == "Leg"]
        assert all(bounds(leg)[1][0] == 0.0 for leg in legs)
        # legs are the full height minus the top thickness and carry the top
        assert all(bounds(leg)[1][1] == pytest.approx(height - 0.703, abs=EPS) for leg in legs)
        assert bounds(top)[1][0] == pytest.approx(bounds(legs[0])[1][1], abs=EPS)


def test_aprons_sit_under_the_top_between_the_legs():
    parts = parts_of()
    legs = [bounds(p) for p in parts if p.name == "Leg"]
    for apron in (p for p in parts if p.name.startswith("Apron")):
        (x0, x1), (y0, y1), (z0, z1) = bounds(apron)
        assert y1 == pytest.approx(34 - 0.703, abs=EPS) and y1 - y0 == pytest.approx(3.5)
        for (lx0, lx1), _, (lz0, lz1) in legs:  # butted against, never inside, a leg
            overlap = min(x1, lx1) - max(x0, lx0) > EPS and min(z1, lz1) - max(z0, lz0) > EPS
            assert not overlap


def test_shelf_rests_on_its_supports_about_ten_inches_up():
    parts = parts_of()
    shelf = next(p for p in parts if p.name == "Lower shelf")
    assert bounds(shelf)[1][1] == pytest.approx(10.0, abs=EPS)
    for support in (p for p in parts if p.name == "Shelf support"):
        assert bounds(support)[1][1] == pytest.approx(bounds(shelf)[1][0], abs=EPS)  # touches, not overlaps
        (sx0, sx1), _, (sz0, sz1) = bounds(support)
        (hx0, hx1), _, (hz0, hz1) = bounds(shelf)
        assert hx0 <= sx0 + EPS and sx1 <= hx1 + EPS and hz0 <= sz0 + EPS and sz1 <= hz1 + EPS  # fully under the shelf


def test_no_parts_overlap_the_legs_or_each_other_in_a_volume():
    parts = parts_of()
    boxes = [(p.name, bounds(p)) for p in parts]
    for i, (na, a) in enumerate(boxes):
        for nb, b in boxes[i + 1 :]:
            inter = [min(a[k][1], b[k][1]) - max(a[k][0], b[k][0]) for k in range(3)]
            assert not all(v > EPS for v in inter), f"{na} intersects {nb}"


def test_profiles_are_counter_clockwise_finite_and_not_degenerate():
    for shelf in (True, False):
        for part in parts_of(lower_shelf=shelf, width_in=24, depth_in=12, height_in=24):
            assert len(part.profile) >= 3
            assert all(math.isfinite(v) for pt in part.profile for v in pt)
            assert signed_area(part.profile) > 0
            assert part.thickness > 0 and math.isfinite(part.thickness)
            assert all(math.isfinite(v) for v in part.transform.pos)


@pytest.mark.parametrize("shelf", [True, False])
def test_nothing_is_below_grade_and_everything_is_inside_the_footprint(shelf):
    for w, d, h in [(24, 12, 24), (48, 24, 34), (96, 48, 48), (60.5, 17.25, 29.75)]:
        for part in parts_of(width_in=w, depth_in=d, height_in=h, lower_shelf=shelf):
            (x0, x1), (y0, y1), (z0, z1) = bounds(part)
            assert y0 >= 0.0 and y1 <= h + EPS
            assert -w / 2 - EPS <= x0 and x1 <= w / 2 + EPS
            assert -d / 2 - EPS <= z0 and z1 <= d / 2 + EPS
            assert part.transform.rot == (0.0, 0.0, 0.0)


def test_top_is_full_width_by_depth_and_derive_reports_the_layout():
    top = next(p for p in parts_of(width_in=60, depth_in=30) if p.name == "Top")
    (x0, x1), _, (z0, z1) = bounds(top)
    assert (x0, x1, z0, z1) == (-30.0, 30.0, -15.0, 15.0)
    d = workbench.derive(make(width_in=60, depth_in=30))
    assert d.leg_height_in == pytest.approx(34 - 0.703)
    assert d.footprint_x == (-30, 30) and d.footprint_z == (-15, 15)
    assert d.long_apron_length_in == pytest.approx(60 - 1.5 - 7)
    assert d.short_apron_length_in == pytest.approx(30 - 1.5 - 7)


def test_plywood_pieces_are_width_by_depth_and_fit_a_sheet():
    parts = parts_of(width_in=96, depth_in=48)
    for part in parts:
        if part.material == "3/4_ext_ply":
            big, small = sheet_piece_dims(part)
            assert big <= 96 and small <= 48
    top = next(p for p in parts if p.name == "Top")
    assert sheet_piece_dims(top) == (96, 48)
    shelf = next(p for p in parts_of() if p.name == "Lower shelf")
    assert sheet_piece_dims(shelf) == pytest.approx((48 - 1.5 - 7, 24 - 1.5))


def test_a_bench_wider_than_a_sheet_is_rejected_clearly():
    with pytest.raises(ParamValidationError, match="width_in"):
        templates.validate_params("workbench", {"width_in": 100})
    # bypassing the bounds (as a future wider bound would) still fails clearly
    wide = Params.model_construct(width_in=100.0, depth_in=24.0, height_in=34.0, lower_shelf=True)
    with pytest.raises(ParamValidationError, match=r"Top is 100 x 24 in, larger than a 48 x 96 in sheet"):
        workbench.generate_parts(wide)
    deep = Params.model_construct(width_in=48.0, depth_in=100.0, height_in=34.0, lower_shelf=False)
    with pytest.raises(ParamValidationError, match="cannot be built from stock lumber"):
        workbench.generate_parts(deep)


def test_a_board_longer_than_its_stock_is_rejected_clearly():
    longest = lumber_spec("2x4_PT").max_stock_length_in
    wide = Params.model_construct(width_in=longest + 60, depth_in=48.0, height_in=34.0, lower_shelf=False)
    needed = f"{longest + 60 - 8.5:g}"  # the apron is the width less the leg posts and end clearance
    with pytest.raises(ParamValidationError, match=rf"Apron \(long\) needs a {needed} in board but 2x4_PT is sold up to {longest:g} in"):
        workbench.generate_parts(wide)


def test_generation_is_deterministic():
    a, b = parts_of(width_in=71.5, depth_in=20), parts_of(width_in=71.5, depth_in=20)
    assert [p.model_dump() for p in a] == [p.model_dump() for p in b]
    assert [p.id for p in a] == [f"T-{i}" for i in range(1, len(a) + 1)]


# ----------------------------------------------------------------------------- skeleton


def test_skeleton_with_shelf_lists_every_step_with_real_labels():
    params = make()
    parts = label_parts(workbench.generate_parts(params))
    steps = workbench.build_skeleton(params, parts)
    assert [s.action_key for s in steps] == ["cut_boards", "cut_plywood", "assemble_frame", "attach_shelf", "attach_top", "final_check"]
    assert [s.phase for s in steps] == ["cut", "cut", "assemble", "assemble", "install", "check"]
    known = {p.label for p in parts}
    by_key = {s.action_key: s for s in steps}
    for step in steps:
        assert step.part_labels == sorted(set(step.part_labels))
        assert set(step.part_labels) <= known
    label = {p.name: p.label for p in parts}
    assert by_key["cut_plywood"].part_labels == sorted({label["Top"], label["Lower shelf"]})
    assert by_key["assemble_frame"].part_labels == sorted({label["Leg"], label["Apron (long)"], label["Apron (short)"]})
    assert by_key["attach_shelf"].part_labels == sorted({label["Shelf support"], label["Lower shelf"]})
    assert by_key["attach_top"].part_labels == [label["Top"]]
    assert by_key["cut_boards"].part_labels == sorted({label[n] for n in ("Leg", "Apron (long)", "Apron (short)", "Shelf support")})
    assert by_key["final_check"].part_labels == []
    assert by_key["final_check"].title == "Check the bench is level and does not rock"


def test_skeleton_without_shelf_drops_the_shelf_step_and_labels():
    params = make(lower_shelf=False)
    parts = label_parts(workbench.generate_parts(params))
    steps = workbench.build_skeleton(params, parts)
    assert [s.action_key for s in steps] == ["cut_boards", "cut_plywood", "assemble_frame", "attach_top", "final_check"]
    label = {p.name: p.label for p in parts}
    assert next(s for s in steps if s.action_key == "cut_plywood").part_labels == [label["Top"]]


def test_a_square_bench_still_labels_long_and_short_aprons_separately():
    parts = label_parts(parts_of(width_in=40, depth_in=40))  # same length, different name
    assert len({p.label for p in parts if p.name.startswith("Apron")}) == 2


def test_skeleton_is_deterministic():
    params = make()
    parts = label_parts(workbench.generate_parts(params))
    assert workbench.build_skeleton(params, parts) == workbench.build_skeleton(params, parts)


# ----------------------------------------------------------------------------- end to end


def check_plan(parts: list[Part], plan: Plan, shelf: bool) -> None:
    assert isinstance(plan, Plan)
    Plan.model_validate(plan.model_dump())
    # every part id is on exactly one cut list row and exactly one layout piece
    row_ids = [pid for row in plan.cut_list for pid in row.part_ids]
    assert sorted(row_ids) == sorted(p.id for p in parts)
    placed = [piece.part_id for layout in plan.layouts for piece in layout.pieces]
    assert sorted(placed) == sorted(p.id for p in parts)
    assert all(not row.cut_notes for row in plan.cut_list)  # nothing flagged as unbuyable
    assert sum(row.qty for row in plan.cut_list) == len(parts)
    # plywood is nested on sheets, boards on boards
    sheet_ids = {p.id for p in parts if p.material == "3/4_ext_ply"}
    on_sheets = {piece.part_id for layout in plan.layouts if layout.kind == "sheet" for piece in layout.pieces}
    assert on_sheets == sheet_ids and len(sheet_ids) == (2 if shelf else 1)
    for layout in plan.layouts:
        assert 0 < layout.utilization <= 1
    # totals are consistent
    assert plan.shopping
    assert plan.subtotal == pytest.approx(sum(item.subtotal for item in plan.shopping), abs=0.011)
    assert plan.total == pytest.approx(plan.subtotal + plan.tax, abs=0.011)
    assert plan.total > 0


def run_pipeline(**overrides) -> tuple[list[Part], Plan]:
    params = make(**overrides)
    labelled = label_parts(workbench.generate_parts(params))
    return labelled, build_plan(labelled)


@pytest.mark.parametrize("shelf", [True, False])
def test_default_bench_builds_a_valid_plan(shelf):
    parts, plan = run_pipeline(lower_shelf=shelf)
    check_plan(parts, plan, shelf)
    assert {layout.kind for layout in plan.layouts} == {"board", "sheet"}
    assert {row.material for row in plan.cut_list} == {"4x4_PT", "2x4_PT", "3/4_ext_ply"}


def test_the_largest_bench_builds_a_valid_plan():
    parts, plan = run_pipeline(width_in=96, depth_in=48, height_in=48)
    check_plan(parts, plan, True)


def test_randomized_valid_params_always_build_a_valid_plan():
    rng = random.Random(21)
    for _ in range(40):
        overrides = {
            "width_in": round(rng.uniform(24, 96), 2),
            "depth_in": round(rng.uniform(12, 48), 2),
            "height_in": round(rng.uniform(24, 48), 2),
            "lower_shelf": rng.random() < 0.5,
        }
        parts, plan = run_pipeline(**overrides)
        check_plan(parts, plan, overrides["lower_shelf"])
        top = next(p for p in parts if p.name == "Top")
        assert bounds(top)[1][1] == pytest.approx(overrides["height_in"], abs=EPS)
