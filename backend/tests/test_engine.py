"""The engine entry point. The signatures are a contract; the behavior is the real pipeline."""

import inspect
import json
import time

import pytest

from app import engine
from app.models import ParamValue, Plan, SkeletonStep, Spec, TemplateInfo


def user(value):
    return ParamValue(value=value, source="user")


def generate(rise=15, **extra):
    return engine.generate("ramp", {"total_rise_in": user(rise), **{k: user(v) for k, v in extra.items()}})


def test_generate_signature_is_the_agreed_contract():
    sig = inspect.signature(engine.generate)
    assert list(sig.parameters) == ["template", "params", "meta"]
    assert sig.parameters["meta"].default is None
    assert sig.parameters["template"].annotation is str
    assert sig.parameters["params"].annotation == dict[str, ParamValue]
    assert sig.return_annotation == tuple[Spec, Plan]


def test_get_skeleton_signature_is_the_agreed_contract():
    sig = inspect.signature(engine.get_skeleton)
    assert list(sig.parameters) == ["spec"]
    assert sig.parameters["spec"].annotation is Spec
    assert sig.return_annotation == list[SkeletonStep]


def test_list_templates_signature_is_the_agreed_contract():
    sig = inspect.signature(engine.list_templates)
    assert list(sig.parameters) == []
    assert sig.return_annotation == list[TemplateInfo]


def test_list_templates_returns_every_registered_template_with_schema_and_defaults():
    templates = {t.key: t for t in engine.list_templates()}
    assert "ramp" in templates
    ramp = templates["ramp"]
    assert isinstance(ramp, TemplateInfo)
    assert "total_rise_in" in ramp.params_schema["properties"]
    assert ramp.defaults["clear_width_in"] == 36


def test_generate_returns_a_spec_and_a_plan():
    spec, plan = generate()
    assert isinstance(spec, Spec) and isinstance(plan, Plan)
    assert spec.template == "ramp" and spec.parts and plan.cut_list and plan.layouts and plan.shopping


def test_generate_spec_params_echo_the_caller_and_fill_defaults_in_template_order():
    spec, _ = engine.generate("ramp", {"total_rise_in": ParamValue(value=15, source="inferred", confidence=0.7), "layout": user("straight")})
    assert list(spec.params)[:2] == ["total_rise_in", "clear_width_in"]  # the template's own order
    assert spec.params["total_rise_in"] == ParamValue(value=15, source="inferred", confidence=0.7)
    assert spec.params["layout"].source == "user" and spec.params["clear_width_in"].source == "default"
    assert spec.assumed == [n for n, v in spec.params.items() if v.source in ("inferred", "default")]
    assert "available_length_in" not in spec.params  # null (no limit) cannot be a ParamValue, so it is left out


def test_generate_keeps_meta_and_uses_the_contractor_quote():
    spec, plan = engine.generate("ramp", {"total_rise_in": user(12)}, {"contractor_quote_cad": 4000.0, "notes": "x"})
    assert {k: v for k, v in spec.meta.items() if k != "summary"} == {"contractor_quote_cad": 4000.0, "notes": "x"}
    assert plan.contractor_quote == 4000.0 and plan.savings == pytest.approx(4000 - plan.total, abs=0.005)
    assert generate(12)[1].savings is None


def test_generate_does_not_modify_the_callers_inputs():
    params = {"total_rise_in": user(12)}
    meta = {"notes": "x"}
    engine.generate("ramp", params, meta)
    assert params == {"total_rise_in": user(12)} and meta == {"notes": "x"}


def test_generate_is_deterministic_byte_for_byte():
    a = generate(21, layout="switchback")
    b = generate(21, layout="switchback")
    assert json.dumps([m.model_dump(mode="json") for m in a]) == json.dumps([m.model_dump(mode="json") for m in b])


def test_generate_labels_parts_consistently_with_the_cut_list():
    spec, plan = generate(15, layout="switchback")
    by_id = {p.id: p for p in spec.parts}
    assert len(by_id) == len(spec.parts)
    for row in plan.cut_list:
        assert {by_id[i].label for i in row.part_ids} == {row.label}
    assert sum(row.qty for row in plan.cut_list) == len(spec.parts)


def test_generate_the_demo_case_reports_that_it_does_not_fit_and_offers_no_fix():
    """21 in rise in a 144 in yard: a two-run switchback needs 186 in, so no layout fits."""
    spec, plan = generate(21, available_length_in=144)
    check = next(c for c in spec.rule_checks if c.id == "RAMP-007")
    assert check.status == "fail" and check.fix is None and "12' 0\"" in check.detail
    assert spec.params["layout"].value == "auto"


def test_generate_a_straight_21_in_ramp_is_flagged_not_crashed():
    """The stringers are longer than any board sold: the design still builds, the rule flags it."""
    spec, plan = generate(21, layout="straight")
    check = next(c for c in spec.rule_checks if c.id == "RAMP-009")
    assert check.status == "fail" and check.fix is not None and check.fix.params_patch == {"layout": "switchback"}
    stringers = next(r for r in plan.cut_list if r.name == "Stringer")
    assert any("cannot be bought as one piece" in n for n in stringers.cut_notes)
    assert stringers.part_ids and not any(p.part_id in stringers.part_ids for lay in plan.layouts for p in lay.pieces)


def test_generate_applying_a_rule_fix_resolves_that_check():
    spec, _ = generate(15, layout="straight", available_length_in=160)
    fix = next(c for c in spec.rule_checks if c.id == "RAMP-007").fix
    assert fix is not None
    params = {**{n: v for n, v in spec.params.items()}, **{k: user(v) for k, v in fix.params_patch.items()}}
    fixed, _ = engine.generate("ramp", params)
    assert next(c for c in fixed.rule_checks if c.id == "RAMP-007").status == "pass"


def test_unknown_template_raises_template_error():
    with pytest.raises(engine.TemplateError, match="nope"):
        engine.generate("nope", {})


@pytest.mark.parametrize(
    ("params", "message"),
    [({}, "total_rise_in is required"), ({"total_rise_in": user(0)}, "total_rise_in"), ({"total_rise_in": user(12), "bogus": user(1)}, "Unknown parameter 'bogus'")],
)
def test_bad_params_raise_param_validation_error(params, message):
    with pytest.raises(engine.ParamValidationError, match=message):
        engine.generate("ramp", params)


def test_a_too_small_switchback_is_a_param_error_not_a_crash():
    with pytest.raises(engine.ParamValidationError, match="too small"):
        generate(3, layout="switchback")


def test_generate_is_fast():
    start = time.perf_counter()
    for rise in (12, 21, 45):
        generate(rise)
    per_call = (time.perf_counter() - start) / 3
    print(f"generate: {per_call * 1000:.1f} ms per call")
    assert per_call < 0.5


@pytest.mark.parametrize(("template", "params"), [("garden_bed", {}), ("workbench", {})])
def test_other_templates_generate_through_the_same_engine(template, params):
    spec, plan = engine.generate(template, {k: user(v) for k, v in params.items()})
    assert spec.template == template and spec.parts and plan.cut_list


def test_get_skeleton_follows_the_specs_own_parts():
    spec, _ = generate(15, layout="straight")
    steps = engine.get_skeleton(spec)
    keys = [s.action_key for s in steps]
    assert keys[0] == "prepare_site" and keys[-1] == "final_check" and "cut_stringers" in keys
    labels = {p.label for p in spec.parts}
    assert all(set(s.part_labels) <= labels for s in steps)
    switchback_keys = [s.action_key for s in engine.get_skeleton(generate(15, layout="switchback")[0])]
    assert "build_landings" in switchback_keys and "build_landings" not in keys


def test_error_types_are_distinct():
    assert not issubclass(engine.ParamValidationError, engine.TemplateError)
    assert not issubclass(engine.TemplateError, engine.ParamValidationError)


def test_summary_is_recomputed_on_every_call():
    # The ramp's key numbers land in meta["summary"]; a stale one posted back in meta never survives.
    spec, _ = engine.generate("ramp", {"total_rise_in": user(21), "available_length_in": user(192)}, {"summary": [{"label": "stale", "value": "x"}]})
    labels = [fact["label"] for fact in spec.meta["summary"]]
    assert "stale" not in labels
    assert labels[:4] == ["Layout", "Slope", "Ramp length", "Space needed"]
    assert all(isinstance(fact["value"], str) and fact["value"] for fact in spec.meta["summary"])


def test_templates_without_a_summary_drop_a_stale_one():
    spec, _ = engine.generate("workbench", {}, {"summary": [{"label": "stale", "value": "x"}]})
    assert "summary" not in spec.meta
