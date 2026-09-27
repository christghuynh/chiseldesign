"""The ramp's at-a-glance numbers (meta["summary"]) and its parameter-panel schema hints."""

from app import engine
from app.models import ParamValue
from app.templates import params_schema
from app.templates.ramp import Params


def _summary(**params):
    spec, _ = engine.generate("ramp", {k: ParamValue(value=v, source="user") for k, v in params.items()})
    return {fact["label"]: fact for fact in spec.meta["summary"]}


def test_demo_straight_ramp_explains_why_it_does_not_fit():
    s = _summary(total_rise_in=21, available_length_in=192, layout="straight")
    assert s["Layout"]["value"] == "Straight, 1 run"
    assert s["Ramp length"]["value"] == "21' 0\""
    assert s["Space needed"]["detail"] == "5' 0\" more than the 16' 0\" available"
    assert s["Run"]["value"] == "rises 21\" over 21' 0\""
    assert s["Longest stringer"]["detail"].endswith("too long for one board")


def test_demo_switchback_lists_each_run_and_the_turn_landing():
    s = _summary(total_rise_in=21, available_length_in=192)
    assert s["Layout"]["value"] == "Switchback, 2 runs"
    assert s["Space needed"]["detail"] == "fits the 16' 0\" available"
    assert s["Run 1"]["value"] == s["Run 2"]["value"] == "rises 10-1/2\" over 10' 6\""
    assert s["Landings"]["value"] == "1 turn landing, 5' 0\" long"
    assert s["Handrails"]["value"] == "Both sides"


def test_low_ramp_needs_no_handrails_or_landings():
    s = _summary(total_rise_in=5)
    assert s["Landings"]["value"] == "None"
    assert s["Handrails"]["value"] == "None" and "not needed" in s["Handrails"]["detail"]
    assert s["Space needed"]["detail"] == "no space limit given"


def test_schema_marks_key_dimensions_and_labels_choices():
    props = params_schema(Params)["properties"]
    key = [name for name, prop in props.items() if prop.get("group") == "key"]
    assert key == ["total_rise_in", "clear_width_in", "available_length_in"]
    assert all(prop.get("group") in ("key", "advanced") for prop in props.values())
    for prop in props.values():
        if "enum" in prop:
            assert set(prop["enum_labels"]) == set(prop["enum"])
