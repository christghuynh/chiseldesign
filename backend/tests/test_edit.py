"""AI-5 tests for /edit. FAKE_AI mode; engine.generate is monkeypatched to echo params.

The real engine.generate is a stub that only reads `layout`, so a width patch would not show up in
the returned spec. To assert on the patch we replace it with a fake that echoes the params it was
given back into the spec.
"""

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import engine
from app.ai import edit as edit_mod
from app.ai.client import AIInvalidOutput, AIUnavailable, Text, ToolCall, fake_responses
from app.main import app
from app.models import GenerateResponse, ParamValue, Plan, Spec

client = TestClient(app)

_STRAIGHT = json.loads((Path(__file__).resolve().parents[2] / "fixtures/specs/ramp_straight.json").read_text())


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch):
    monkeypatch.setenv("FAKE_AI", "1")


@pytest.fixture
def echo_engine(monkeypatch):
    """Replace engine.generate with a fake that echoes the given params into the spec."""
    base = GenerateResponse.model_validate(_STRAIGHT)
    calls: list[dict] = []

    def _fake_generate(template, params, meta=None):
        calls.append({"template": template, "params": dict(params), "meta": meta})
        spec = base.spec.model_copy(deep=True)
        spec.template = template
        spec.params = dict(params)
        spec.meta = dict(meta or {})
        return spec, base.plan.model_copy(deep=True)

    # Patch on the app.engine module so calls through `engine.generate` see the fake.
    monkeypatch.setattr(engine, "generate", _fake_generate)
    return calls


def _spec_dict(**param_overrides):
    spec = copy.deepcopy(_STRAIGHT["spec"])
    for name, value in param_overrides.items():
        spec["params"][name] = {"value": value, "source": "user"}
    return spec


def _post(spec_dict, utterance):
    return client.post("/api/edit", json={"spec": spec_dict, "utterance": utterance})


# ---------------------------------------------------------------------------------------------
# set_params


def test_widen_request_applies_a_width_patch(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "set_params", "args": {"patch": {"clear_width_in": 42}}}}):
        r = _post(_spec_dict(clear_width_in=36), "make it six inches wider")
    assert r.status_code == 200
    body = r.json()
    assert body["patch"] == {"clear_width_in": 42.0}
    assert body["spec"]["params"]["clear_width_in"]["value"] == 42.0
    assert body["spec"]["params"]["clear_width_in"]["source"] == "user"
    assert body["needs_clarification"] is False
    assert "forty-two inches" in body["message"]


def test_out_of_bounds_number_is_clamped_and_the_message_says_so(echo_engine):
    # clear_width_in max is 60.
    with fake_responses("edit", {"tool_call": {"name": "set_params", "args": {"patch": {"clear_width_in": 999}}}}):
        r = _post(_spec_dict(), "make it super wide")
    body = r.json()
    assert body["patch"] == {"clear_width_in": 60.0}
    assert body["spec"]["params"]["clear_width_in"]["value"] == 60.0
    assert "maximum" in body["message"].lower()
    assert body["needs_clarification"] is False


def test_below_minimum_is_clamped_up(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "set_params", "args": {"patch": {"clear_width_in": 5}}}}):
        r = _post(_spec_dict(), "make it tiny")
    body = r.json()
    assert body["patch"] == {"clear_width_in": 30.0}
    assert "minimum" in body["message"].lower()


def test_unknown_param_name_becomes_a_clarification(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "set_params", "args": {"patch": {"color": "red"}}}}):
        r = _post(_spec_dict(), "paint it red")
    body = r.json()
    assert body["needs_clarification"] is True
    assert body["patch"] == {}


def test_invalid_enum_value_becomes_a_clarification(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "set_params", "args": {"patch": {"layout": "spiral"}}}}):
        r = _post(_spec_dict(), "make it spiral")
    body = r.json()
    assert body["needs_clarification"] is True
    assert body["patch"] == {}


def test_enum_change_is_applied(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "set_params", "args": {"patch": {"framing": "2x8_PT"}}}}):
        r = _post(_spec_dict(), "use bigger framing")
    body = r.json()
    assert body["patch"] == {"framing": "2x8_PT"}
    assert body["spec"]["params"]["framing"]["value"] == "2x8_PT"
    assert body["needs_clarification"] is False


def test_boolean_change_is_applied(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "set_params", "args": {"patch": {"edge_curb": False}}}}):
        r = _post(_spec_dict(), "remove the curb")
    body = r.json()
    assert body["patch"] == {"edge_curb": False}
    assert body["spec"]["params"]["edge_curb"]["value"] is False


# ---------------------------------------------------------------------------------------------
# apply_fix


def test_apply_fix_uses_the_rules_patch(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "apply_fix", "args": {"rule_id": "RAMP-007"}}}):
        r = _post(_spec_dict(), "yes, fix the slope")
    body = r.json()
    # RAMP-007 fix in the fixture patches layout -> switchback.
    assert body["patch"] == {"layout": "switchback"}
    assert body["spec"]["params"]["layout"]["value"] == "switchback"
    assert body["needs_clarification"] is False


def test_apply_fix_with_an_unknown_rule_id_clarifies(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "apply_fix", "args": {"rule_id": "RAMP-999"}}}):
        r = _post(_spec_dict(), "fix it")
    body = r.json()
    assert body["needs_clarification"] is True
    assert body["patch"] == {}


# ---------------------------------------------------------------------------------------------
# clarification / text


def test_ask_clarification_sets_the_flag_and_leaves_the_spec_unchanged(echo_engine):
    with fake_responses("edit", {"tool_call": {"name": "ask_clarification", "args": {"question": "How much wider?"}}}):
        r = _post(_spec_dict(clear_width_in=36), "wider")
    body = r.json()
    assert body["needs_clarification"] is True
    assert body["patch"] == {}
    assert body["message"] == "How much wider?"
    assert body["spec"]["params"]["clear_width_in"]["value"] == 36.0


def test_plain_text_reply_is_treated_as_a_clarification(echo_engine):
    with fake_responses("edit", {"text": "I can only change the ramp."}):
        r = _post(_spec_dict(), "tell me a joke")
    body = r.json()
    assert body["needs_clarification"] is True
    assert body["patch"] == {}
    assert body["message"].endswith((".", "?"))


# ---------------------------------------------------------------------------------------------
# AI failure -> 503 AI_UNAVAILABLE


@pytest.mark.parametrize("exc", [AIUnavailable("down"), AIInvalidOutput("garbage")])
def test_ai_failure_returns_503_ai_unavailable(echo_engine, exc):
    with fake_responses("edit", exc):
        r = _post(_spec_dict(), "make it wider")
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "AI_UNAVAILABLE"
    assert "slider" in body["error"]["message"].lower()


# ---------------------------------------------------------------------------------------------
# history from spec.meta['edit_turns']


def test_prior_turns_from_meta_are_passed_to_the_model(monkeypatch, echo_engine):
    captured = {}

    def _capture(messages, tools, **kwargs):
        captured["messages"] = messages
        return ToolCall("set_params", {"patch": {"clear_width_in": 42}})

    monkeypatch.setattr(edit_mod, "call_with_tools", _capture)
    spec = _spec_dict()
    spec["meta"]["edit_turns"] = [
        {"role": "user", "text": "make it wider"},
        {"role": "model", "text": "How much wider?"},
    ]
    r = _post(spec, "six inches")
    assert r.status_code == 200
    prompt_text = captured["messages"][0].text
    assert "make it wider" in prompt_text
    assert "How much wider?" in prompt_text


def test_force_tool_is_used(monkeypatch, echo_engine):
    captured = {}

    def _capture(messages, tools, **kwargs):
        captured.update(kwargs)
        return ToolCall("set_params", {"patch": {"clear_width_in": 42}})

    monkeypatch.setattr(edit_mod, "call_with_tools", _capture)
    _post(_spec_dict(), "wider")
    assert captured.get("force_tool") is True


def test_the_conversation_is_not_stored_in_the_returned_spec(monkeypatch, echo_engine):
    monkeypatch.setattr(edit_mod, "call_with_tools", lambda *a, **k: ToolCall("set_params", {"patch": {"clear_width_in": 42}}))
    spec = _spec_dict()
    spec["meta"]["contractor_quote_cad"] = 4000
    spec["meta"]["edit_turns"] = [{"role": "user", "text": "change the width"}, {"role": "model", "text": "What width?"}]
    body = _post(spec, "42 inches").json()
    assert "edit_turns" not in body["spec"]["meta"]
    assert body["spec"]["meta"]["contractor_quote_cad"] == 4000


def test_only_the_last_five_exchanges_reach_the_model(monkeypatch, echo_engine):
    captured = {}

    def _capture(messages, tools, **kwargs):
        captured["prompt"] = messages[0].text
        return ToolCall("ask_clarification", {"question": "Which part?"})

    monkeypatch.setattr(edit_mod, "call_with_tools", _capture)
    spec = _spec_dict()
    spec["meta"]["edit_turns"] = [
        {"role": "user" if i % 2 == 0 else "model", "text": f"turn-{i:02d}"} for i in range(14)
    ]
    _post(spec, "hmm")
    assert "turn-03" not in captured["prompt"]
    assert "turn-04" in captured["prompt"] and "turn-13" in captured["prompt"]
