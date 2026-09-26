"""GEO-2: template registry, params JSON Schema and validation."""

import json
from pathlib import Path

import pytest

from app import templates
from app.engine_errors import ParamValidationError, TemplateError
from app.models import TemplateInfo
from app.templates.ramp import Params

FIXTURE_TEMPLATES = json.loads((Path(__file__).resolve().parents[2] / "fixtures" / "templates.json").read_text("utf-8"))


def test_registry_finds_the_ramp_and_only_real_templates():
    reg = templates.registry()
    assert "ramp" in reg
    for key, module in reg.items():
        assert module.KEY == key
        for attr in ("NAME", "DESCRIPTION", "Params", "derive", "generate_parts", "build_skeleton"):
            assert hasattr(module, attr), f"{key} lacks {attr}"


def test_unknown_template_is_a_template_error():
    with pytest.raises(TemplateError, match="nope"):
        templates.get_template("nope")


def test_template_infos_are_valid_and_carry_a_schema_and_defaults():
    infos = templates.template_infos()
    ramp = next(i for i in infos if i.key == "ramp")
    assert isinstance(ramp, TemplateInfo)
    props = ramp.params_schema["properties"]
    assert ramp.params_schema["required"] == ["total_rise_in"]
    assert props["total_rise_in"]["minimum"] == 1 and props["total_rise_in"]["maximum"] == 60
    assert props["clear_width_in"]["minimum"] == 30 and props["clear_width_in"]["maximum"] == 60
    assert props["layout"]["enum"] == ["auto", "straight", "switchback"]
    assert props["framing"]["enum"] == ["2x6_PT", "2x8_PT"]
    assert props["edge_curb"]["type"] == "boolean"
    assert props["total_rise_in"]["unit"] == "in"


def test_defaults_match_the_agreed_ramp_defaults():
    ramp = next(i for i in templates.template_infos() if i.key == "ramp")
    assert ramp.defaults == {
        "clear_width_in": 36, "available_length_in": None, "layout": "auto", "slope_ratio": 12,
        "landing_length_in": 60, "framing": "2x6_PT", "stringer_spacing_in": 16,
        "decking": "5/4x6_PT_deck", "deck_gap_in": 0.125, "handrails": "auto", "edge_curb": True,
    }
    assert "total_rise_in" not in ramp.defaults  # required, no default


def test_nullable_fields_are_flattened_like_the_frontend_fixture():
    props = templates.params_schema(Params)["properties"]
    assert props["available_length_in"]["type"] == ["number", "null"]
    assert "anyOf" not in props["available_length_in"]
    assert props["available_length_in"]["minimum"] == 12


def test_schema_has_the_same_fields_and_defaults_as_the_frontend_fixture():
    """fixtures/templates.json is what the frontend develops against; the real schema must not drift from it."""
    fixture = FIXTURE_TEMPLATES[0]["params_schema"]["properties"]
    real = templates.params_schema(Params)["properties"]
    assert set(real) == set(fixture)
    for name, spec in fixture.items():
        assert real[name].get("default") == spec.get("default"), name
        assert real[name].get("enum") == spec.get("enum"), name
        assert real[name]["type"] == spec["type"], name


def test_validate_fills_defaults():
    params = templates.validate_params("ramp", {"total_rise_in": 21})
    assert params.total_rise_in == 21 and params.clear_width_in == 36 and params.layout == "auto"


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({}, "total_rise_in is required"),
        ({"total_rise_in": 0.5}, "total_rise_in"),
        ({"total_rise_in": 61}, "total_rise_in"),
        ({"total_rise_in": 21, "clear_width_in": 29}, "clear_width_in"),
        ({"total_rise_in": 21, "layout": "spiral"}, "layout"),
        ({"total_rise_in": 21, "wobble": 1}, "Unknown parameter 'wobble'"),
        ({"total_rise_in": "tall"}, "total_rise_in"),
    ],
)
def test_validate_rejects_bad_values_with_a_readable_message(values, message):
    with pytest.raises(ParamValidationError, match=message):
        templates.validate_params("ramp", values)


def test_validate_reports_every_problem_at_once():
    with pytest.raises(ParamValidationError) as info:
        templates.validate_params("ramp", {"clear_width_in": 10, "layout": "spiral"})
    text = str(info.value)
    assert "total_rise_in is required" in text and "clear_width_in" in text and "layout" in text


def test_validate_unknown_template():
    with pytest.raises(TemplateError):
        templates.validate_params("nope", {})
