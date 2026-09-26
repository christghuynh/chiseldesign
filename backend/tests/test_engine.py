"""The engine entry point (a stub returning fixtures for now). The signatures are a contract."""

import inspect

import pytest

from app import engine
from app.models import ParamValue, Plan, SkeletonStep, Spec, TemplateInfo


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


def test_list_templates_returns_the_ramp_with_schema_and_defaults():
    templates = engine.list_templates()
    ramp = next(t for t in templates if t.key == "ramp")
    assert isinstance(ramp, TemplateInfo)
    assert "total_rise_in" in ramp.params_schema["properties"]
    assert ramp.defaults["clear_width_in"] == 36
    templates.clear()
    assert engine.list_templates()  # each call returns its own copy


def test_generate_returns_a_spec_and_a_plan():
    spec, plan = engine.generate("ramp", {})
    assert isinstance(spec, Spec) and isinstance(plan, Plan)
    assert spec.template == "ramp" and spec.parts and plan.cut_list


def test_generate_stub_picks_the_layout_fixture():
    straight, _ = engine.generate("ramp", {"layout": ParamValue(value="straight", source="user")})
    switchback, _ = engine.generate("ramp", {"layout": ParamValue(value="switchback", source="user")})
    assert straight.params["layout"].value == "straight"
    assert switchback.params["layout"].value == "switchback"


def test_generate_returns_independent_copies():
    a, _ = engine.generate("ramp", {})
    a.parts.clear()
    b, _ = engine.generate("ramp", {})
    assert b.parts


def test_unknown_template_raises_template_error():
    with pytest.raises(engine.TemplateError, match="nope"):
        engine.generate("nope", {})


def test_get_skeleton_returns_the_outline():
    spec, _ = engine.generate("ramp", {})
    steps = engine.get_skeleton(spec)
    assert steps and all(isinstance(s, SkeletonStep) for s in steps)
    assert steps[0].action_key == "prepare_site" and steps[-1].action_key == "final_check"


def test_error_types_are_distinct():
    assert not issubclass(engine.ParamValidationError, engine.TemplateError)
    assert not issubclass(engine.TemplateError, engine.ParamValidationError)
