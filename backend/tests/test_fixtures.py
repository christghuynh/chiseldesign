"""F-3: the hand-built fixtures obey the contracts and are internally consistent.

These are rough placeholder data (replaced by real /generate output in GEO-16). The checks
here are the ones GEO-15 will also want for generated plans, so they double as a starting point.
"""

import json
from pathlib import Path

import pytest

from app.models import BuildStep, GenerateResponse, InstructionsResponse, SkeletonStep, TemplateInfo
from app.util.units import format_ft_in

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SPEC_FILES = ["ramp_straight.json", "ramp_switchback.json"]


def load(name: str) -> GenerateResponse:
    return GenerateResponse.model_validate_json((FIXTURES / "specs" / name).read_text("utf-8"))


@pytest.fixture(params=SPEC_FILES)
def fixture(request) -> GenerateResponse:
    return load(request.param)


def test_fixture_files_are_valid_contracts(fixture):
    assert fixture.spec.template == "ramp"
    assert fixture.spec.schema_version == "1.0"
    assert fixture.spec.parts and fixture.spec.rule_checks and fixture.plan.cut_list


def test_assumed_lists_exactly_the_inferred_and_default_params(fixture):
    expected = [k for k, v in fixture.spec.params.items() if v.source in ("inferred", "default")]
    assert fixture.spec.assumed == expected


def test_confidence_only_on_read_or_inferred_params(fixture):
    for name, value in fixture.spec.params.items():
        if value.confidence is not None:
            assert value.source in ("read", "inferred"), name
            assert 0 <= value.confidence <= 1


def test_part_ids_are_unique_and_match_their_label(fixture):
    ids = [p.id for p in fixture.spec.parts]
    assert len(ids) == len(set(ids))
    for p in fixture.spec.parts:
        assert p.id.startswith(f"{p.label}-")


def test_profiles_are_ccw_polygons(fixture):
    for p in fixture.spec.parts:
        pts = p.profile
        assert len(pts) >= 3 and len(set(pts)) == len(pts), p.id
        twice_area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
        assert twice_area > 0, f"{p.id} is not counter-clockwise"
        assert p.thickness > 0


def test_nothing_sits_below_grade(fixture):
    """Y-up, origin on the ground: no part may dip below y = 0 (only y rotation and translation are used)."""
    for p in fixture.spec.parts:
        low = min(y for _, y in p.profile) + p.transform.pos[1]
        assert low >= -1e-3, f"{p.id} goes below grade ({low})"


def test_cut_list_covers_every_part_once(fixture):
    part_ids = {p.id for p in fixture.spec.parts}
    listed = [pid for row in fixture.plan.cut_list for pid in row.part_ids]
    assert sorted(listed) == sorted(part_ids)
    for row in fixture.plan.cut_list:
        assert row.qty == len(row.part_ids)
        assert row.length_display == format_ft_in(row.length_in)
    labels = [row.label for row in fixture.plan.cut_list]
    assert len(labels) == len(set(labels))
    by_id = {p.id: p for p in fixture.spec.parts}
    for row in fixture.plan.cut_list:
        assert {by_id[pid].label for pid in row.part_ids} == {row.label}


def test_layouts_place_every_part_without_overlap_or_overflow(fixture):
    placed = [piece.part_id for layout in fixture.plan.layouts for piece in layout.pieces]
    assert sorted(placed) == sorted(p.id for p in fixture.spec.parts)
    length_of = {pid: row.length_in for row in fixture.plan.cut_list for pid in row.part_ids}
    for layout in fixture.plan.layouts:
        assert layout.kind == "board"
        pieces = sorted(layout.pieces, key=lambda q: q.x)
        assert pieces[0].x >= 0
        for a, b in zip(pieces, pieces[1:], strict=False):
            assert b.x >= a.x + a.w - 1e-6, f"{layout.stock_id}: {a.part_id} overlaps {b.part_id}"
        assert pieces[-1].x + pieces[-1].w <= layout.length_in + 1e-6, layout.stock_id
        for q in pieces:
            assert q.w == pytest.approx(length_of[q.part_id], abs=1e-3)
        assert layout.utilization == pytest.approx(sum(q.w for q in pieces) / layout.length_in, abs=1e-3)
    ids = [layout.stock_id for layout in fixture.plan.layouts]
    assert len(ids) == len(set(ids))


def test_shopping_totals_add_up(fixture):
    plan = fixture.plan
    for item in plan.shopping:
        assert item.subtotal == pytest.approx(item.qty * item.unit_price, abs=0.005)
    assert plan.subtotal == pytest.approx(sum(i.subtotal for i in plan.shopping), abs=0.005)
    assert plan.tax == pytest.approx(round(plan.subtotal * 0.13, 2), abs=0.005)
    assert plan.total == pytest.approx(plan.subtotal + plan.tax, abs=0.005)
    assert plan.contractor_quote == fixture.spec.meta["contractor_quote_cad"]
    assert plan.savings == pytest.approx(plan.contractor_quote - plan.total, abs=0.005)


def test_lumber_boards_bought_match_layouts(fixture):
    bought = {i.key: i.qty for i in fixture.plan.shopping if i.unit == "each" and i.key[0] in "245"}
    from collections import Counter

    needed = Counter(f"{layout.material}_{int(layout.length_in)}" for layout in fixture.plan.layouts)
    assert bought == dict(needed)


def test_rule_checks_have_ids_and_fixes_only_on_failures(fixture):
    ids = [c.id for c in fixture.spec.rule_checks]
    assert ids == [f"RAMP-00{i}" for i in range(1, 10)]
    for c in fixture.spec.rule_checks:
        if c.fix is not None:
            assert c.status in ("fail", "warn")


def test_straight_fails_site_fit_with_a_switchback_fix_and_switchback_passes():
    straight, switchback = load("ramp_straight.json"), load("ramp_switchback.json")
    fail = next(c for c in straight.spec.rule_checks if c.id == "RAMP-007")
    assert fail.status == "fail" and fail.fix is not None
    assert fail.fix.params_patch == {"layout": "switchback"}
    assert next(c for c in switchback.spec.rule_checks if c.id == "RAMP-007").status == "pass"
    assert switchback.spec.params["layout"].value == "switchback"
    assert straight.spec.params["layout"].value == "straight"


def test_instructions_fixture_references_real_labels():
    steps = InstructionsResponse.model_validate_json((FIXTURES / "instructions" / "ramp_switchback.json").read_text("utf-8")).steps
    labels = {row.label for row in load("ramp_switchback.json").plan.cut_list}
    assert [s.n for s in steps] == list(range(1, len(steps) + 1))
    for step in steps:
        assert isinstance(step, BuildStep)
        assert set(step.part_labels) <= labels
        assert {c.label for c in step.cut_callouts} <= labels


def test_templates_fixture_is_valid_and_defaults_match_schema():
    infos = [TemplateInfo.model_validate(t) for t in json.loads((FIXTURES / "templates.json").read_text("utf-8"))]
    ramp = next(t for t in infos if t.key == "ramp")
    props = ramp.params_schema["properties"]
    for name, default in ramp.defaults.items():
        assert props[name]["default"] == default
    assert ramp.params_schema["required"] == ["total_rise_in"]


def test_fixture_prices_are_flagged_as_placeholders(fixture):
    assert fixture.plan.has_placeholder_prices is True
    assert all("placeholder price" in i.description for i in fixture.plan.shopping)


def test_skeleton_fixture_follows_the_build_order_and_references_real_labels():
    steps = [SkeletonStep.model_validate(s) for s in json.loads((FIXTURES / "skeletons" / "ramp_straight.json").read_text("utf-8"))]
    labels = {row.label for row in load("ramp_straight.json").plan.cut_list}
    keys = [s.action_key for s in steps]
    assert keys == [
        "prepare_site", "cut_stringers", "cut_ledger", "attach_ledger", "set_stringers",
        "check_slope", "install_decking", "install_curbs", "install_handrails", "final_check",
    ]
    assert len(set(keys)) == len(keys)
    for step in steps:
        assert set(step.part_labels) <= labels, step.action_key
    assert next(s for s in steps if s.action_key == "cut_stringers").part_labels  # not empty
