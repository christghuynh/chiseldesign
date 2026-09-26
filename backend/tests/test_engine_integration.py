"""GEO-15: cross-module checks that no single module's tests cover.

Templates -> cut list -> nesting -> rules -> pricing, all through `engine.generate`. Sweeps use a fixed
seed so failures are reproducible.
"""

import json
import math
import random

import pytest
from fastapi.testclient import TestClient

from app import engine, templates
from app.cutlist import part_extents
from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.main import app
from app.models import GenerateResponse, ParamValue

client = TestClient(app)

REQUIRED = {"ramp": {"total_rise_in": 15}, "step_platform": {"total_rise_in": 14}, "garden_bed": {}, "workbench": {}}


def user(value):
    return ParamValue(value=value, source="user")


def build(template, values=None, meta=None):
    params = {**REQUIRED[template], **(values or {})}
    return engine.generate(template, {k: user(v) for k, v in params.items()}, meta)


def dump(spec_and_plan) -> str:
    return json.dumps([m.model_dump(mode="json") for m in spec_and_plan], sort_keys=False)


def random_ramp_values(rng: random.Random) -> dict:
    return {
        "total_rise_in": round(rng.uniform(1, 60), 1),
        "clear_width_in": rng.choice([30, 36, 42, 48, 60]),
        "layout": rng.choice(["auto", "straight", "switchback"]),
        "framing": rng.choice(["2x6_PT", "2x8_PT"]),
        "decking": rng.choice(["5/4x6_PT_deck", "5/4x6_PT_deck", "3/4_ext_ply"]),
        "handrails": rng.choice(["auto", "yes", "no"]),
        "edge_curb": rng.choice([True, False]),
        "stringer_spacing_in": rng.choice([12, 16, 24]),
        "slope_ratio": rng.choice([10, 12, 14, 16]),
        **({"available_length_in": rng.choice([120, 144, 200, 300])} if rng.random() < 0.5 else {}),
    }


def ramp_sweep(n=60):
    rng = random.Random(2026)
    cases = []
    while len(cases) < n:
        values = random_ramp_values(rng)
        try:
            build("ramp", values)
        except ParamValidationError:
            continue  # the documented too-small-switchback case
        cases.append(values)
    return cases


SWEEP = ramp_sweep()
ALL_DESIGNS = [("ramp", v) for v in SWEEP[:20]] + [(t, {}) for t in REQUIRED]


def _world_min_y(part) -> float:
    return min(y for _, y in part.profile) + part.transform.pos[1]


@pytest.mark.parametrize(("template", "values"), ALL_DESIGNS)
def test_every_design_is_deterministic_byte_for_byte(template, values):
    assert dump(build(template, values)) == dump(build(template, values))


@pytest.mark.parametrize(("template", "values"), ALL_DESIGNS)
def test_every_design_is_a_valid_well_formed_model(template, values):
    spec, plan = build(template, values)
    # JSON round trip keeps everything
    assert GenerateResponse.model_validate_json(GenerateResponse(spec=spec, plan=plan).model_dump_json()) == GenerateResponse(spec=spec, plan=plan)
    ids = [p.id for p in spec.parts]
    assert len(ids) == len(set(ids)) and spec.parts
    for p in spec.parts:
        assert p.group, p.id
        assert p.transform.rot in ((0, 0, 0), (0, math.pi, 0)), (p.id, p.transform.rot)  # only Y flips are used
        assert _world_min_y(p) >= -1e-3, f"{p.id} goes below grade"
        assert len(p.profile) >= 3 and all(math.isfinite(v) for pt in p.profile for v in pt)
        area = sum(p.profile[i][0] * p.profile[(i + 1) % len(p.profile)][1] - p.profile[(i + 1) % len(p.profile)][0] * p.profile[i][1] for i in range(len(p.profile))) / 2
        assert area > 0, f"{p.id} is not counter-clockwise"
        assert lumber_spec(p.material)  # a known material
    for c in spec.rule_checks:
        assert c.status in ("pass", "warn", "fail", "info") and c.detail and c.source_ref


@pytest.mark.parametrize(("template", "values"), ALL_DESIGNS)
def test_cut_list_matches_the_parts_and_nesting_places_every_buyable_piece(template, values):
    spec, plan = build(template, values)
    by_id = {p.id: p for p in spec.parts}
    assert sorted(i for row in plan.cut_list for i in row.part_ids) == sorted(by_id)
    for row in plan.cut_list:
        assert row.qty == len(row.part_ids)
        assert {by_id[i].label for i in row.part_ids} == {row.label}
    unbuyable = {i for row in plan.cut_list if any("cannot be bought as one piece" in n for n in row.cut_notes) for i in row.part_ids}
    placed = [piece.part_id for lay in plan.layouts for piece in lay.pieces]
    assert sorted(placed) == sorted(set(by_id) - unbuyable)
    for lay in plan.layouts:
        pieces = sorted(lay.pieces, key=lambda q: (q.x, q.y))
        for q in pieces:
            assert q.x >= -1e-6 and q.x + q.w <= lay.length_in + 1e-6
            assert q.y >= -1e-6 and q.y + q.h <= lay.width_in + 1e-6
        if lay.kind == "board":
            for a, b in zip(pieces, pieces[1:], strict=False):
                assert b.x >= a.x + a.w - 1e-6
        assert 0 <= lay.utilization <= 1 + 1e-9


@pytest.mark.parametrize(("template", "values"), ALL_DESIGNS)
def test_totals_and_placeholder_flag_are_consistent(template, values):
    _, plan = build(template, values, {"contractor_quote_cad": 4000.0})
    assert plan.subtotal == pytest.approx(sum(i.subtotal for i in plan.shopping), abs=0.005)
    assert plan.tax == pytest.approx(round(plan.subtotal * 0.13, 2), abs=0.005)
    assert plan.total == pytest.approx(plan.subtotal + plan.tax, abs=0.005)
    assert plan.savings == pytest.approx(4000 - plan.total, abs=0.005)
    # The estimate flag is on exactly while some item in the list still has a placeholder price (NC-4).
    assert plan.has_placeholder_prices is any("placeholder price" in i.description for i in plan.shopping)
    assert all(i.qty > 0 for i in plan.shopping)


@pytest.mark.parametrize(("template", "values"), ALL_DESIGNS)
def test_boards_never_need_more_material_than_the_lumber_and_unmodified_ones_match_it_exactly(template, values):
    """Each board part's two smaller extents fit inside the lumber's actual thickness x width, and equal them unless
    the cut notes say the board is ripped, bevelled, cut to a wedge at grade, cut down or spliced."""
    spec, _ = build(template, values)
    for p in spec.parts:
        material = lumber_spec(p.material)
        if material.kind != "board":
            continue
        smaller = sorted(part_extents(p))[:2]
        actual = sorted([material.thickness_in, material.width_in])
        assert smaller[0] <= actual[0] + 0.05 and smaller[1] <= actual[1] + 0.05, (p.id, p.name, smaller, "needs more than one board")
        is_a_short_block = max(part_extents(p)) <= actual[1] + 0.05  # no longer than the board is wide: no length axis
        if not is_a_short_block and not any(word in note for note in p.cut_notes for word in ("Rip", "Bevel", "Cut to", "Splice", "level cut")):
            assert smaller == pytest.approx(actual, abs=0.05), (p.id, p.name, smaller, p.cut_notes)


def test_every_rule_fix_resolves_its_check_end_to_end():
    """Apply each offered fix to the params, regenerate, and the same check must pass (300 designs' worth of checks)."""
    resolved = 0
    for values in SWEEP:
        spec, _ = build("ramp", values)
        for check in spec.rule_checks:
            if check.fix is None:
                continue
            assert check.status in ("warn", "fail")
            patched = {**values, **check.fix.params_patch}
            fixed, _ = build("ramp", patched)
            assert next(c for c in fixed.rule_checks if c.id == check.id).status == "pass", (values, check.id, check.fix.params_patch)
            resolved += 1
    assert resolved > 10, "the sweep should exercise several fixes"


def test_the_demo_demonstration_flow_straight_fails_then_the_fix_gives_a_switchback():
    values = {"total_rise_in": 15, "available_length_in": 160, "layout": "straight"}
    spec, plan = build("ramp", values, {"contractor_quote_cad": 4000.0})
    fail = next(c for c in spec.rule_checks if c.id == "RAMP-007")
    assert fail.status == "fail" and fail.fix.params_patch == {"layout": "switchback"}
    fixed, fixed_plan = build("ramp", {**values, **fail.fix.params_patch}, {"contractor_quote_cad": 4000.0})
    assert next(c for c in fixed.rule_checks if c.id == "RAMP-007").status == "pass"
    assert len(fixed.parts) > len(spec.parts)  # the switchback adds a run and a landing
    assert plan.savings is not None and fixed_plan.savings is not None


def test_generate_stays_fast_for_the_biggest_designs():
    import time

    start = time.perf_counter()
    for values in ({"total_rise_in": 60, "clear_width_in": 60, "layout": "straight"}, {"total_rise_in": 60, "clear_width_in": 60, "layout": "switchback"}):
        build("ramp", values)
    per_call = (time.perf_counter() - start) / 2
    print(f"largest ramps: {per_call * 1000:.0f} ms per generate")
    assert per_call < 0.5


@pytest.mark.parametrize("template", list(REQUIRED))
def test_generate_route_works_for_every_template(template):
    params = {k: {"value": v, "source": "user"} for k, v in REQUIRED[template].items()}
    r = client.post("/api/generate", json={"template": template, "params": params})
    assert r.status_code == 200, r.text
    assert GenerateResponse.model_validate(r.json()).spec.parts


def test_registry_and_engine_agree_on_the_template_list():
    assert {t.key for t in engine.list_templates()} == set(templates.registry()) == set(REQUIRED)
    for info in engine.list_templates():
        module = templates.get_template(info.key)
        assert info.name == module.NAME and info.params_schema["properties"]


def test_the_skeleton_is_consistent_with_each_designs_own_parts():
    for template in REQUIRED:
        spec, _ = build(template)
        steps = engine.get_skeleton(spec)
        labels = {p.label for p in spec.parts}
        assert steps and len({s.action_key for s in steps}) == len(steps)
        assert all(set(s.part_labels) <= labels for s in steps), template
