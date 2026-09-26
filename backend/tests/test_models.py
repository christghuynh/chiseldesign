"""F-2: the contract models and the generated JSON Schema."""

import pytest
from pydantic import ValidationError

from app import models
from app.models import ParamValue, ParseResponse, Part, Plan, SkeletonStep, Spec, Transform
from app.models.schema import SCHEMA_PATH, build_schema, contract_models, render_schema


def test_every_exported_model_is_a_contract():
    for model in contract_models():
        assert issubclass(model, models.Contract)


def test_param_value_sources_are_restricted():
    assert ParamValue(value=36, source="user").confidence is None
    with pytest.raises(ValidationError):
        ParamValue(value=36, source="guess")


def test_param_value_keeps_numbers_and_bools_distinct():
    assert type(ParamValue(value=36, source="default").value) is int
    assert type(ParamValue(value=0.125, source="default").value) is float
    assert ParamValue(value=True, source="default").value is True


def test_spec_defaults_and_schema_version():
    spec = Spec(template="ramp", params={}, assumed=[])
    assert spec.schema_version == "1.0" and spec.parts == [] and spec.rule_checks == [] and spec.meta == {}
    with pytest.raises(ValidationError):
        Spec(template="ramp", params={}, assumed=[], schema_version="2.0")


def test_defaults_are_not_shared_between_instances():
    a = Spec(template="ramp", params={}, assumed=[])
    b = Spec(template="ramp", params={}, assumed=[])
    a.parts.append(Part(id="A-1", label="A", name="x", material="m", profile=[(0, 0), (1, 0), (1, 1)], thickness=1,
                        transform=Transform(pos=(0, 0, 0), rot=(0, 0, 0))))
    assert b.parts == []


def test_transform_requires_three_numbers():
    with pytest.raises(ValidationError):
        Transform(pos=(0, 0), rot=(0, 0, 0))


def test_json_schema_marks_defaulted_fields_required():
    """So the generated TS types don't make fields the server always returns optional."""
    schema = build_schema()
    assert "parts" in schema["$defs"]["Spec"]["required"]
    assert "cut_notes" in schema["$defs"]["Part"]["required"]


def test_json_schema_keeps_a_field_literally_named_title():
    """The title-stripping pass must not remove RuleCheck.title (a property, not a keyword)."""
    assert "title" in build_schema()["$defs"]["RuleCheck"]["properties"]


def test_committed_json_schema_is_up_to_date():
    """Fails when a model changed but `make types` wasn't run."""
    committed = SCHEMA_PATH.read_text("utf-8").replace("\r\n", "\n")  # checkouts on Windows may add CRLF
    assert committed == render_schema(), "shared/schema is stale: run `make types`"


def test_plan_placeholder_price_flag_defaults_to_false_and_is_required_in_the_schema():
    plan = Plan(cut_list=[], layouts=[], shopping=[], subtotal=0, tax=0, total=0, contractor_quote=None, savings=None)
    assert plan.has_placeholder_prices is False
    assert "has_placeholder_prices" in build_schema()["$defs"]["Plan"]["required"]


def test_skeleton_step_fields():
    step = SkeletonStep(phase="cut", title="Cut all stringers", part_labels=["A"], action_key="cut_stringers")
    assert step.model_dump() == {"phase": "cut", "title": "Cut all stringers", "part_labels": ["A"], "action_key": "cut_stringers"}


def test_parse_response_allows_no_spec_for_an_unsupported_image():
    res = ParseResponse(spec=None, template_confidence=None, questions=[], raw_notes="Not a ramp, bed or platform.")
    assert res.spec is None
    assert {"type": "null"} in build_schema()["$defs"]["ParseResponse"]["properties"]["spec"]["anyOf"]
