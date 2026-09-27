"""Lane A (parse) tests for ai/parse.py — the parse pipeline in fake mode.

No test here touches the network: FAKE_AI=1 and a blocked real client (mirrors test_ai_client.py).
Gemini readings are queued with client.fake_responses("parse", ...).
"""

from __future__ import annotations

import pytest

from app.ai import client
from app.ai.client import AIUnavailable, fake_responses
from app.ai.parse import (
    ParseError,
    build_prompt,
    parse_image,
    parse_measurements,
)
from app.ai.parse import _templates as templates


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch):
    monkeypatch.setenv("FAKE_AI", "1")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    def _refuse(*_a, **_k):
        raise AssertionError("a parse test tried to create a real Gemini client")

    monkeypatch.setattr(client, "_client_for", _refuse)


def _reading(**over):
    base = {
        "template": "ramp",
        "template_confidence": 0.9,
        "params": [{"name": "total_rise_in", "value": 21, "unit": "in", "source": "read"}],
        "questions": [],
        "notes": "A three-step porch.",
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------------------------
# A1 — prompt


def test_prompt_lists_every_template_and_its_params():
    prompt = build_prompt(templates())
    assert "ramp" in prompt
    assert "total_rise_in" in prompt
    assert "clear_width_in" in prompt
    # Bounds and required-ness make it into the catalog so the model respects them.
    assert "range 1..60" in prompt
    assert "required" in prompt
    # The template placeholder is fully substituted.
    assert "{templates}" not in prompt


def test_prompt_rebuilds_from_the_registry(monkeypatch):
    from app.models import TemplateInfo

    extra = TemplateInfo(
        key="grab_bar",
        name="Grab bar",
        description="A wall-mounted grab bar.",
        params_schema={
            "type": "object",
            "required": ["length_in"],
            "properties": {"length_in": {"type": "number", "minimum": 12, "maximum": 48}},
        },
        defaults={},
    )
    monkeypatch.setattr("app.ai.parse._templates", lambda: [*templates(), extra])
    from app.ai.parse import _templates as t2

    prompt = build_prompt(t2())
    assert "grab_bar" in prompt and "length_in" in prompt


# ---------------------------------------------------------------------------------------------
# A2 — normalization, defaults, overrides, assumed


def test_metric_values_are_normalized_to_inches():
    reading = _reading(
        params=[
            {"name": "total_rise_in", "value": 53.34, "unit": "cm", "source": "read"},
            {"name": "available_length_in", "value": 3, "unit": "m", "source": "inferred"},
        ]
    )
    with fake_responses("parse", reading):
        out = parse_image(b"jpegbytes")
    assert out.spec.params["total_rise_in"].value == pytest.approx(21.0)
    assert out.spec.params["available_length_in"].value == pytest.approx(118.1102, abs=1e-3)


def test_feet_and_ft_in_strings_normalize():
    reading = _reading(
        params=[
            {"name": "total_rise_in", "value": 1.5, "unit": "ft", "source": "read"},
            {"name": "available_length_in", "value": "20'", "unit": None, "source": "read"},
        ]
    )
    with fake_responses("parse", reading):
        out = parse_image(b"x")
    assert out.spec.params["total_rise_in"].value == pytest.approx(18.0)
    assert out.spec.params["available_length_in"].value == pytest.approx(240.0)


def test_user_measurement_overrides_the_models_value():
    reading = _reading(
        params=[{"name": "total_rise_in", "value": 30, "unit": "in", "source": "read"}]
    )
    with fake_responses("parse", reading):
        out = parse_image(b"x", measurements={"total_rise": 21})
    p = out.spec.params["total_rise_in"]
    assert p.value == pytest.approx(21.0)
    assert p.source == "user"
    assert p.confidence is None
    assert "total_rise_in" not in out.spec.assumed  # user values are not assumptions


def test_missing_params_filled_with_defaults_and_listed_in_assumed():
    reading = _reading(params=[{"name": "total_rise_in", "value": 21, "unit": "in", "source": "read"}])
    with fake_responses("parse", reading):
        out = parse_image(b"x")
    # A default-filled param exists with source default and is in assumed.
    assert out.spec.params["clear_width_in"].value == 36
    assert out.spec.params["clear_width_in"].source == "default"
    assert "clear_width_in" in out.spec.assumed
    # The read value is not assumed.
    assert "total_rise_in" not in out.spec.assumed
    # A null default (available_length_in) is left unset: ParamValue cannot hold None.
    assert "available_length_in" not in out.spec.params


def test_inferred_values_are_assumed():
    reading = _reading(
        params=[
            {"name": "total_rise_in", "value": 21, "unit": "in", "source": "read"},
            {"name": "clear_width_in", "value": 36, "unit": "in", "source": "inferred", "confidence": 0.4},
        ]
    )
    with fake_responses("parse", reading):
        out = parse_image(b"x")
    assert "clear_width_in" in out.spec.assumed
    assert out.spec.params["clear_width_in"].source == "inferred"


def test_required_param_with_no_reading_and_no_default_is_not_invented():
    # total_rise_in is required and has no default. If the model doesn't read it, leave it out
    # and add a question, do not invent a number.
    reading = _reading(params=[{"name": "clear_width_in", "value": 40, "unit": "in", "source": "read"}])
    with fake_responses("parse", reading):
        out = parse_image(b"x")
    assert "total_rise_in" not in out.spec.params
    assert any("rise" in q.lower() for q in out.questions)


def test_out_of_bounds_reading_is_dropped():
    # clear_width_in max is 60; a 200 reading is invalid and must not land in the spec.
    reading = _reading(
        params=[
            {"name": "total_rise_in", "value": 21, "unit": "in", "source": "read"},
            {"name": "clear_width_in", "value": 200, "unit": "in", "source": "read"},
        ]
    )
    with fake_responses("parse", reading):
        out = parse_image(b"x")
    # Falls back to the default, marked assumed.
    assert out.spec.params["clear_width_in"].value == 36
    assert out.spec.params["clear_width_in"].source == "default"


def test_enum_and_boolean_params_pass_through():
    reading = _reading(
        params=[
            {"name": "total_rise_in", "value": 21, "unit": "in", "source": "read"},
            {"name": "layout", "value": "switchback", "unit": None, "source": "inferred"},
            {"name": "edge_curb", "value": False, "unit": None, "source": "read"},
        ]
    )
    with fake_responses("parse", reading):
        out = parse_image(b"x")
    assert out.spec.params["layout"].value == "switchback"
    assert out.spec.params["edge_curb"].value is False


def test_contractor_quote_goes_to_meta():
    with fake_responses("parse", _reading()):
        out = parse_image(b"x", measurements={"contractor_quote": 4200})
    assert out.spec.meta["contractor_quote_cad"] == pytest.approx(4200.0)


def test_note_is_appended_to_the_prompt(monkeypatch):
    captured = {}

    def _spy(prompt, schema, images=None, *, call="json", system=None):
        captured["prompt"] = prompt
        return _reading()

    monkeypatch.setattr(client, "generate_json", _spy)
    parse_image(b"x", note="the yard is only 10 feet")
    assert "the yard is only 10 feet" in captured["prompt"]


# ---------------------------------------------------------------------------------------------
# unknown object


def test_unknown_object_returns_null_spec_with_a_reason():
    reading = _reading(template=None, params=[], notes="This is a photo of a cat, not a ramp.")
    with fake_responses("parse", reading):
        out = parse_image(b"x")
    assert out.spec is None
    assert "cat" in out.raw_notes.lower()


def test_unknown_template_key_is_treated_as_no_match():
    reading = _reading(template="spaceship", params=[])
    with fake_responses("parse", reading):
        out = parse_image(b"x")
    assert out.spec is None


# ---------------------------------------------------------------------------------------------
# A3 — failure handling at the module level


def test_invalid_output_is_retried_once_then_raises_parse_error():
    # Two invalid outputs in a row: the module retries once, then gives up with ParseError.
    bad = {"template": "ramp"}  # missing required fields -> AIInvalidOutput
    with fake_responses("parse", bad, bad):
        with pytest.raises(ParseError):
            parse_image(b"x")


def test_invalid_then_valid_recovers():
    bad = {"template": "ramp"}
    good = _reading()
    with fake_responses("parse", bad, good):
        out = parse_image(b"x")
    assert out.spec is not None and out.spec.template == "ramp"


def test_ai_unavailable_propagates():
    with fake_responses("parse", AIUnavailable("down")):
        with pytest.raises(AIUnavailable):
            parse_image(b"x")


# ---------------------------------------------------------------------------------------------
# measurements parsing


def test_parse_measurements_maps_aliases_and_quote():
    overrides, quote = parse_measurements(
        {"total_rise": 21, "desired_width": 42, "unknown_key": 5, "contractor_quote": 3000}
    )
    assert overrides == {"total_rise_in": 21.0, "clear_width_in": 42.0}
    assert quote == pytest.approx(3000.0)


def test_parse_measurements_accepts_length_strings():
    overrides, _ = parse_measurements({"available_length": "12'"})
    assert overrides["available_length_in"] == pytest.approx(144.0)


def test_parse_measurements_ignores_empty_values():
    overrides, quote = parse_measurements({"total_rise": "", "contractor_quote": None})
    assert overrides == {}
    assert quote is None


def test_typed_width_goes_to_the_templates_own_width_param():
    # The form sends the ramp's name (clear_width_in); a garden bed calls it width_in.
    reading = _reading(template="garden_bed", params=[{"name": "length_in", "value": 6, "unit": "ft", "source": "read"}])
    with fake_responses("parse", reading):
        out = parse_image(b"x", measurements={"clear_width_in": 30, "total_rise_in": 21})
    assert out.spec.template == "garden_bed"
    assert out.spec.params["width_in"].value == pytest.approx(30.0) and out.spec.params["width_in"].source == "user"
    assert out.spec.params["length_in"].value == pytest.approx(72.0)
    assert out.spec.params["height_in"].value == 29.25 and out.spec.params["height_in"].source == "default"
    assert "clear_width_in" not in out.spec.params and "total_rise_in" not in out.spec.params
