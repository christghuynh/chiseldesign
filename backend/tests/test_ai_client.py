"""AI-1: Gemini client wrapper. No test here reaches the network.

Fake-mode tests go through `fake_responses` / `ai/fakes/`. Real-path tests replace
`client._generate_content` (the only function that would touch the network) with a scripted stub.
"""

import logging
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors
from pydantic import BaseModel

from app.ai import client
from app.ai.client import (
    AIInvalidOutput,
    AIUnavailable,
    Image,
    Message,
    Text,
    Tool,
    ToolCall,
    call_with_tools,
    fake_responses,
    generate_json,
)

SCHEMA = {
    "type": "object",
    "properties": {"template": {"type": ["string", "null"]}, "confidence": {"type": "number"}},
    "required": ["template", "confidence"],
}


class Reading(BaseModel):
    template: str | None
    confidence: float


SET_PARAMS = Tool(
    name="set_params",
    description="Change parameters",
    parameters={
        "type": "object",
        "properties": {"patch": {"type": "object"}},
        "required": ["patch"],
    },
)
ASK = Tool(
    name="ask_clarification",
    description="Ask the user a question",
    parameters={"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
)
TOOLS = [SET_PARAMS, ASK]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Belt and braces: even a test that forgets to stub the transport cannot reach Gemini."""

    def _refuse(*_a, **_k):
        raise AssertionError("a test tried to create a real Gemini client")

    monkeypatch.setattr(client, "_client_for", _refuse)
    monkeypatch.setattr(client, "RETRY_DELAY_S", 0)
    monkeypatch.setenv("FAKE_AI", "1")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)


@pytest.fixture
def real_mode(monkeypatch):
    """Real code path with a scripted transport. Returns the list of recorded calls."""
    monkeypatch.setenv("FAKE_AI", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    calls: list[dict] = []
    script: list = []

    def _stub(model, contents, config):
        calls.append({"model": model, "contents": contents, "config": config})
        outcome = script.pop(0) if len(script) > 1 else script[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(client, "_generate_content", _stub)
    return SimpleNamespace(calls=calls, script=script)


def _response(text=None, function_calls=None):
    return SimpleNamespace(text=text, function_calls=function_calls)


def _api_error(cls, code):
    return cls(code, {"error": {"code": code, "message": "scripted", "status": "SCRIPTED"}})


# ---------------------------------------------------------------------------------------------
# generate_json, fake mode


def test_fake_json_returns_a_schema_valid_dict():
    with fake_responses("parse", {"template": "ramp", "confidence": 0.9}):
        out = generate_json("read this", SCHEMA, call="parse")
    assert out == {"template": "ramp", "confidence": 0.9}


def test_fake_json_with_a_pydantic_schema_returns_its_dump():
    with fake_responses("parse", {"template": "ramp", "confidence": 1}):
        out = generate_json("read this", Reading, call="parse")
    assert out == {"template": "ramp", "confidence": 1.0}
    assert isinstance(out, dict)


def test_shipped_parse_fake_is_used_when_nothing_is_queued():
    schema = {
        "type": "object",
        "required": ["template", "template_confidence", "params", "questions", "notes"],
    }
    out = generate_json("read this", schema, call="parse")
    assert out["template"] == "ramp"
    assert out["params"]["total_rise_in"]["value"] == 21


def test_fake_output_that_breaks_the_schema_is_invalid_output():
    with fake_responses("parse", {"template": "ramp"}):
        with pytest.raises(AIInvalidOutput, match="schema"):
            generate_json("read this", SCHEMA, call="parse")
    with fake_responses("parse", {"template": 3, "confidence": 0.5}):
        with pytest.raises(AIInvalidOutput, match="template"):
            generate_json("read this", Reading, call="parse")


@pytest.mark.parametrize("raw", ["{not json", "[1, 2]", ""])
def test_non_object_json_is_invalid_output(raw):
    with fake_responses("parse", raw):
        with pytest.raises(AIInvalidOutput):
            generate_json("read this", SCHEMA, call="parse")


def test_missing_fake_is_unavailable_so_callers_fall_back():
    with pytest.raises(AIUnavailable, match="no canned response"):
        generate_json("x", SCHEMA, call="no_such_call_type")


def test_fake_queue_is_consumed_in_order_and_the_last_repeats():
    first, second = {"template": "a", "confidence": 0}, {"template": "b", "confidence": 1}
    with fake_responses("q", first, second):
        assert generate_json("x", SCHEMA, call="q")["template"] == "a"
        assert generate_json("x", SCHEMA, call="q")["template"] == "b"
        assert generate_json("x", SCHEMA, call="q")["template"] == "b"


def test_fake_can_raise_to_simulate_an_outage():
    with fake_responses("parse", AIUnavailable("down")):
        with pytest.raises(AIUnavailable, match="down"):
            generate_json("x", SCHEMA, call="parse")


def test_fake_queue_is_restored_after_the_block():
    with fake_responses("parse", {"template": "outer", "confidence": 0}):
        with fake_responses("parse", {"template": "inner", "confidence": 0}):
            assert generate_json("x", SCHEMA, call="parse")["template"] == "inner"
        assert generate_json("x", SCHEMA, call="parse")["template"] == "outer"
    assert generate_json("x", {"type": "object"}, call="parse")["template"] == "ramp"  # shipped fake


# ---------------------------------------------------------------------------------------------
# call_with_tools, fake mode


def test_fake_tool_call_is_returned_with_its_args():
    out = call_with_tools([Message("user", "make it 6 inches wider")], TOOLS, call="edit")
    assert out == ToolCall("set_params", {"patch": {"clear_width_in": 42}})


def test_fake_text_reply():
    with fake_responses("edit", {"text": "  Sure.  "}):
        assert call_with_tools([Message("user", "hi")], TOOLS, call="edit") == Text("Sure.")


def test_unknown_tool_is_invalid_output():
    with fake_responses("edit", {"tool_call": {"name": "delete_everything", "args": {}}}):
        with pytest.raises(AIInvalidOutput, match="unknown tool"):
            call_with_tools([Message("user", "x")], TOOLS, call="edit")


def test_tool_args_are_checked_against_the_tool_schema():
    with fake_responses("edit", {"tool_call": {"name": "ask_clarification", "args": {}}}):
        with pytest.raises(AIInvalidOutput, match="Bad arguments"):
            call_with_tools([Message("user", "x")], TOOLS, call="edit")


def test_call_with_tools_needs_tools():
    with pytest.raises(ValueError):
        call_with_tools([Message("user", "x")], [], call="edit")


# ---------------------------------------------------------------------------------------------
# Real path: retry, timeout, errors, request shape (transport stubbed)


def test_timeout_on_both_attempts_raises_a_clean_ai_unavailable(real_mode, caplog):
    real_mode.script.append(httpx.ReadTimeout("scripted timeout"))
    with caplog.at_level(logging.INFO, logger="app.ai"):
        with pytest.raises(AIUnavailable, match="after one retry") as info:
            generate_json("x", SCHEMA, call="parse")
    assert len(real_mode.calls) == 2  # one try + one retry, then give up
    assert "ReadTimeout" in str(info.value)
    lines = [r.getMessage() for r in caplog.records]
    assert len(lines) == 2 and all("latency_ms=" in line and "call=parse" in line for line in lines)


def test_one_transient_failure_is_retried(real_mode):
    real_mode.script.extend([httpx.ConnectError("scripted"), _response(text='{"template": "ramp", "confidence": 0.8}')])
    assert generate_json("x", SCHEMA, call="parse") == {"template": "ramp", "confidence": 0.8}
    assert len(real_mode.calls) == 2


@pytest.mark.parametrize("code", [429, 503])
def test_rate_limit_and_server_errors_are_retried(real_mode, code):
    cls = errors.ClientError if code < 500 else errors.ServerError
    real_mode.script.extend([_api_error(cls, code), _response(text='{"template": null, "confidence": 0}')])
    assert generate_json("x", SCHEMA, call="parse")["template"] is None
    assert len(real_mode.calls) == 2


def test_a_rejected_request_fails_fast(real_mode):
    real_mode.script.append(_api_error(errors.ClientError, 400))
    with pytest.raises(AIUnavailable, match="HTTP 400"):
        generate_json("x", SCHEMA, call="parse")
    assert len(real_mode.calls) == 1


def test_invalid_json_from_gemini_is_not_retried_by_the_client(real_mode):
    real_mode.script.append(_response(text="Sorry, I can't read that."))
    with pytest.raises(AIInvalidOutput):
        generate_json("x", SCHEMA, call="parse")
    assert len(real_mode.calls) == 1


def test_missing_api_key_is_unavailable(monkeypatch):
    monkeypatch.setenv("FAKE_AI", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(AIUnavailable, match="GEMINI_API_KEY"):
        generate_json("x", SCHEMA, call="parse")


def test_json_request_uses_structured_output_the_model_from_env_and_images(real_mode, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    real_mode.script.append(_response(text='{"template": "ramp", "confidence": 1}'))
    generate_json("read this", SCHEMA, images=[b"\xff\xd8jpeg", Image(b"png", "image/png")], call="parse", system="sys")
    sent = real_mode.calls[0]
    assert sent["model"] == "gemini-test-model"
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].response_json_schema == SCHEMA
    assert sent["config"].system_instruction == "sys"
    *images, prompt = sent["contents"]
    assert prompt == "read this"
    assert [p.inline_data.mime_type for p in images] == ["image/jpeg", "image/png"]


def test_pydantic_schema_is_sent_as_response_schema(real_mode):
    real_mode.script.append(_response(text='{"template": "ramp", "confidence": 1}'))
    generate_json("x", Reading, call="parse")
    assert real_mode.calls[0]["config"].response_schema is Reading


def test_default_model_when_env_is_unset(real_mode):
    real_mode.script.append(_response(text='{"template": "ramp", "confidence": 1}'))
    generate_json("x", SCHEMA, call="parse")
    assert real_mode.calls[0]["model"] == client.DEFAULT_MODEL


def test_real_tool_call_is_decoded_and_validated(real_mode):
    fc = SimpleNamespace(name="set_params", args={"patch": {"clear_width_in": 42}})
    real_mode.script.append(_response(function_calls=[fc]))
    history = [Message("user", "make it wider"), Message("model", "How much wider?"), Message("user", "6 inches")]
    out = call_with_tools(history, TOOLS, call="edit", force_tool=True)
    assert out == ToolCall("set_params", {"patch": {"clear_width_in": 42}})

    config = real_mode.calls[0]["config"]
    assert [d.name for d in config.tools[0].function_declarations] == ["set_params", "ask_clarification"]
    assert config.tool_config.function_calling_config.mode == "ANY"
    assert config.automatic_function_calling.disable is True
    assert [c.role for c in real_mode.calls[0]["contents"]] == ["user", "model", "user"]


def test_real_text_reply_and_empty_reply(real_mode):
    real_mode.script.append(_response(text="Widened to 42 inches."))
    assert call_with_tools([Message("user", "x")], TOOLS, call="edit") == Text("Widened to 42 inches.")
    real_mode.script[:] = [_response(text=None, function_calls=None)]
    with pytest.raises(AIInvalidOutput, match="neither"):
        call_with_tools([Message("user", "x")], TOOLS, call="edit")
