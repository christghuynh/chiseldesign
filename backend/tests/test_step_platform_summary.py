"""The step platform's at-a-glance numbers (meta["summary"]), its parameter-panel schema hints, and the
optional step count (GEO-20)."""

import pytest

from app import engine
from app.cutlist import label_parts
from app.engine_errors import ParamValidationError
from app.models import ParamValue
from app.plan import build_plan
from app.rules import check_design
from app.templates import params_schema
from app.templates import step_platform as sp


def _generate(**params):
    params.setdefault("top_platform", False)  # the steps up to a porch; the platform's summary is tested in test_step_platform_top.py
    spec, _ = engine.generate("step_platform", {k: ParamValue(value=v, source="user") for k, v in params.items()})
    return spec


def _summary(**params):
    return {fact["label"]: fact for fact in _generate(**params).meta["summary"]}


def _riser_rule(**params):
    return next(c for c in _generate(**params).rule_checks if c.id == "STEP-001")


def test_schema_groups_and_labels():
    props = params_schema(sp.Params)["properties"]
    key = [name for name, prop in props.items() if prop.get("group") == "key"]
    advanced = [name for name, prop in props.items() if prop.get("group") == "advanced"]
    assert key == ["total_rise_in", "width_in", "step_count", "top_platform"]
    assert advanced == ["tread_depth_in", "max_riser_in", "platform_depth_in"]
    assert "rise" in props["total_rise_in"]["title"].lower()
    assert props["step_count"]["title"] == "Number of steps"
    assert "leave empty for the fewest steps" in props["step_count"]["description"].lower()
    assert props["step_count"]["type"] == ["integer", "null"]
    assert props["step_count"]["empty_label"] == "Automatic"
    for prop in props.values():
        assert "(in)" not in prop["title"] and "inferred" not in prop["description"]


def test_21_in_rise_is_three_steps_of_seven():
    s = _summary(total_rise_in=21)
    assert s["Steps"]["value"] == "3 steps"
    assert s["Each step"]["value"] == '7" high, 11" deep'
    assert s["Space needed"]["value"] == "1' 10\" long × 3' 0\" wide"  # 2 treads of 11
    assert s["Total rise"]["value"] == "1' 9\""
    assert s["Stringer length"]["detail"] == "longest board sold is 12' 0\""
    assert _riser_rule(total_rise_in=21).status == "pass"


def test_two_forced_steps_at_21_in_are_too_tall_and_the_fix_restores_three():
    s = _summary(total_rise_in=21, step_count=2)
    assert s["Steps"]["value"] == "2 steps" and s["Steps"]["detail"] == "the number you chose"
    assert s["Each step"]["value"] == '10-1/2" high, 11" deep'
    assert s["Space needed"]["value"] == "11\" long × 3' 0\" wide"
    check = _riser_rule(total_rise_in=21, step_count=2)
    assert check.status == "fail" and check.fix is not None
    assert check.fix.params_patch == {"step_count": 3}
    assert _riser_rule(total_rise_in=21, **check.fix.params_patch).status == "pass"


def test_a_forced_count_over_the_own_maximum_fails_even_under_the_guideline():
    # 4 steps of 6-1/4 are within the 7 in guideline but over the 6 in chosen as the tallest step.
    check = _riser_rule(total_rise_in=25, max_riser_in=6, step_count=4)
    assert check.status == "fail" and "tallest step allowed is 6\"" in check.detail
    assert check.fix.params_patch == {"step_count": 5}


def test_extra_steps_make_them_lower():
    s = _summary(total_rise_in=21, step_count=4, width_in=48)
    assert s["Each step"]["value"] == '5-1/4" high, 11" deep'
    assert s["Space needed"]["value"] == "2' 9\" long × 4' 0\" wide"
    assert _riser_rule(total_rise_in=21, step_count=4).status == "pass"


def test_a_single_step_has_no_space_or_stringer_line():
    s = _summary(total_rise_in=5)
    assert s["Steps"]["value"] == "1 step"
    assert s["Each step"]["value"] == '5" high'
    assert "Space needed" not in s and "Stringer length" not in s


@pytest.mark.parametrize("rise, count, strips", [(21, 2, 2), (21, 1, 3), (40, 4, 2)])
def test_a_riser_taller_than_any_board_is_stacked_strips_and_still_builds(rise, count, strips):
    p = sp.Params(total_rise_in=rise, step_count=count)
    d = sp.derive(p)
    assert d.riser_count == count and d.riser_boards_per_riser == strips
    assert d.riser_material == "2x10_PT" and d.riser_rip_width_in == pytest.approx(rise / count / strips)
    parts = label_parts(sp.generate_parts(p))
    risers = [q for q in parts if q.name == "Riser"]
    assert len(risers) == count * strips
    assert max(q.transform.pos[1] + max(y for _, y in q.profile) for q in risers) == pytest.approx(rise)
    build_plan(parts)
    assert [c.id for c in check_design(sp.KEY, p, d, parts)] == ["STEP-001", "STEP-002", "STEP-003", "STEP-004"]


def test_a_forced_count_the_stringer_cannot_be_cut_from_names_the_count_that_works():
    # 2 steps of 15 in leave 0.38 in of wood under the notches; 3 steps of 10 leave enough.
    with pytest.raises(ParamValidationError, match=r'^2 steps of 15" are too tall to cut from a 2x10 stringer\. Use at least 3 steps, or leave Number of steps empty\.$'):
        sp.derive(sp.Params(total_rise_in=30, step_count=2))
    sp.derive(sp.Params(total_rise_in=30, step_count=3))


def test_leaving_the_count_empty_behaves_as_before():
    assert sp.derive(sp.Params(total_rise_in=37.3)) == sp.derive(sp.Params(total_rise_in=37.3, step_count=None))
    assert sp.derive(sp.Params(total_rise_in=37.3)).riser_count == 6
