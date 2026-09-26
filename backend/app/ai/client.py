"""AI-1: the one place that talks to Gemini.

Two entry points:
- `generate_json(prompt, response_schema, images=None)` -> dict, via structured output. Used by
  /parse (AI-3) and /instructions (AI-6).
- `call_with_tools(messages, tools)` -> `ToolCall | Text`, via function calling. Used by /edit (AI-5).

Behavior shared by both:
- Model from `GEMINI_MODEL` (default `DEFAULT_MODEL`), key from `GEMINI_API_KEY`. Both are read at
  call time, so tests and `.env` changes take effect without a restart.
- 20 s timeout per attempt and one retry on transient failures (timeouts, connection errors,
  HTTP 429 and 5xx). Anything else fails fast.
- One log line per attempt on the `app.ai` logger: call type, model, attempt, latency, outcome.
  Prompts, images, responses and keys are never logged.
- Failures raise `AIUnavailable` (no usable answer: timeout, network, quota, missing key, rejected
  request) or `AIInvalidOutput` (Gemini answered, but not in the requested shape). The client
  does not retry invalid output; callers that want that (AI-4) retry themselves. Every route
  must turn both into its non-AI fallback.

`FAKE_AI=1` never touches the network: responses come from `ai/fakes/<call>.json`, keyed by the
`call` argument, and go through the same validation as real ones. Tests queue their own responses
with `fake_responses()`.

The AI never computes dimensions, quantities or prices. Callers only use it to read, interpret
and word things; numbers come from the engine.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import httpx
import jsonschema
from pydantic import BaseModel, ValidationError

import app.config  # noqa: F401  (loads the repo-root .env into os.environ)

log = logging.getLogger("app.ai")

DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_S = 20.0
RETRY_DELAY_S = 0.5
FAKES_DIR = Path(__file__).parent / "fakes"

# HTTP statuses worth one more try: rate limited, or the server had a bad moment.
_TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
# The SDK raises httpx errors, or httpx2 errors when httpx2 is installed. httpx2 is only a dev
# dependency (the FastAPI test client), so it is optional here: the production image has no dev deps.
_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (httpx.TransportError, TimeoutError)
try:
    import httpx2
except ImportError:  # pragma: no cover - production image
    pass
else:
    _TRANSPORT_ERRORS += (httpx2.TransportError,)


class AIError(Exception):
    """Base class: the AI could not produce a usable answer. Callers fall back to a non-AI path."""


class AIUnavailable(AIError):
    """No answer: timeout, network failure, quota, missing API key, or the request was rejected."""


class AIInvalidOutput(AIError):
    """Gemini answered, but the answer is not valid JSON, does not match the schema, or names an unknown tool."""


@dataclass(frozen=True)
class Image:
    data: bytes
    mime_type: str = "image/jpeg"


@dataclass(frozen=True)
class Message:
    role: Literal["user", "model"]
    text: str


@dataclass(frozen=True)
class Tool:
    """A function Gemini may call. `parameters` is a JSON Schema object for the arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Text:
    text: str


Schema = type[BaseModel] | dict[str, Any]


def fake_mode() -> bool:
    return os.environ.get("FAKE_AI", "").strip().lower() in {"1", "true", "yes"}


def model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


# ---------------------------------------------------------------------------------------------
# Public API


def generate_json(
    prompt: str,
    response_schema: Schema,
    images: Sequence[Image | bytes] | None = None,
    *,
    call: str = "json",
    system: str | None = None,
) -> dict[str, Any]:
    """Ask for JSON matching `response_schema` (a Pydantic model class or a JSON Schema dict).

    Returns the decoded object, validated against the schema (for a Pydantic model, its JSON dump).
    `call` names the call type for logs and for the fake-mode fixture (`fakes/<call>.json`).
    Raises AIUnavailable or AIInvalidOutput.
    """
    if fake_mode():
        raw = _take_fake(call)
        return _decode_json(raw if isinstance(raw, str) else json.dumps(raw), response_schema)

    from google.genai import types

    schema_kw: dict[str, Any]
    if isinstance(response_schema, dict):
        schema_kw = {"response_json_schema": response_schema}
    else:
        schema_kw = {"response_schema": response_schema}
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        **schema_kw,
    )
    contents: list[Any] = [_image_part(img) for img in images or []]
    contents.append(prompt)
    response = _send(call, contents, config)
    return _decode_json(response.text or "", response_schema)


def call_with_tools(
    messages: Sequence[Message],
    tools: Sequence[Tool],
    *,
    call: str = "tools",
    system: str | None = None,
    force_tool: bool = False,
) -> ToolCall | Text:
    """One function-calling turn. Returns the first tool call, or the text reply if there is none.

    Tool arguments are validated against the tool's `parameters` schema. `force_tool=True` makes
    Gemini call one of the tools instead of replying in text. Functions are never executed here;
    the caller acts on the returned `ToolCall`. Raises AIUnavailable or AIInvalidOutput.
    """
    if not tools:
        raise ValueError("call_with_tools needs at least one tool")
    if fake_mode():
        return _decode_fake_turn(_take_fake(call), tools)

    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=t.name, description=t.description, parameters_json_schema=t.parameters
                    )
                    for t in tools
                ]
            )
        ],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY" if force_tool else "AUTO")
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = [types.Content(role=m.role, parts=[types.Part.from_text(text=m.text)]) for m in messages]
    response = _send(call, contents, config)

    calls = response.function_calls or []
    if calls:
        return _check_tool_call(calls[0].name or "", dict(calls[0].args or {}), tools)
    text = (response.text or "").strip()
    if not text:
        raise AIInvalidOutput("Gemini returned neither a tool call nor text")
    return Text(text)


# ---------------------------------------------------------------------------------------------
# Transport: timeout, one retry, latency logging


@lru_cache(maxsize=4)
def _client_for(api_key: str) -> Any:
    from google import genai
    from google.genai import types

    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(TIMEOUT_S * 1000)))


def _generate_content(model: str, contents: Any, config: Any) -> Any:
    """The only line that reaches the network. Tests replace this function."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise AIUnavailable("GEMINI_API_KEY is not set")
    return _client_for(api_key).models.generate_content(model=model, contents=contents, config=config)


def _send(call: str, contents: Any, config: Any) -> Any:
    from google.genai import errors

    model = model_name()
    for attempt in (1, 2):
        start = time.perf_counter()
        try:
            response = _generate_content(model, contents, config)
        except _TRANSPORT_ERRORS as exc:
            reason, transient = f"{type(exc).__name__}", True
        except errors.APIError as exc:
            reason, transient = f"HTTP {exc.code}", exc.code in _TRANSIENT_STATUS
        else:
            _log(call, model, attempt, start, "ok")
            return response

        _log(call, model, attempt, start, reason)
        if not transient:
            raise AIUnavailable(f"Gemini rejected the {call} request ({reason})")
        if attempt == 1:
            time.sleep(RETRY_DELAY_S)
    raise AIUnavailable(f"Gemini did not answer the {call} request ({reason}, after one retry)")


def _log(call: str, model: str, attempt: int, start: float, outcome: str) -> None:
    ms = (time.perf_counter() - start) * 1000
    level = logging.INFO if outcome == "ok" else logging.WARNING
    log.log(level, "gemini call=%s model=%s attempt=%d latency_ms=%.0f outcome=%s", call, model, attempt, ms, outcome)


def _image_part(img: Image | bytes) -> Any:
    from google.genai import types

    if isinstance(img, bytes):
        img = Image(img)
    return types.Part.from_bytes(data=img.data, mime_type=img.mime_type)


# ---------------------------------------------------------------------------------------------
# Output validation (shared by real and fake responses)


def _decode_json(text: str, schema: Schema) -> dict[str, Any]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIInvalidOutput(f"Gemini returned invalid JSON ({exc.msg} at char {exc.pos})") from exc
    if not isinstance(obj, dict):
        raise AIInvalidOutput(f"Gemini returned a JSON {type(obj).__name__}, expected an object")

    if isinstance(schema, dict):
        try:
            jsonschema.validate(obj, schema)
        except jsonschema.ValidationError as exc:
            where = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            raise AIInvalidOutput(f"Gemini output does not match the schema at {where}: {exc.message}") from exc
        return obj
    try:
        return schema.model_validate(obj).model_dump(mode="json")
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "(root)"
        raise AIInvalidOutput(f"Gemini output does not match the schema at {where}: {first['msg']}") from exc


def _check_tool_call(name: str, args: dict[str, Any], tools: Sequence[Tool]) -> ToolCall:
    tool = next((t for t in tools if t.name == name), None)
    if tool is None:
        raise AIInvalidOutput(f"Gemini called an unknown tool {name!r}")
    try:
        jsonschema.validate(args, tool.parameters)
    except jsonschema.ValidationError as exc:
        raise AIInvalidOutput(f"Bad arguments for tool {name!r}: {exc.message}") from exc
    return ToolCall(name, args)


# ---------------------------------------------------------------------------------------------
# Fake mode

_fake_queue: dict[str, list[Any]] = {}


@contextmanager
def fake_responses(call: str, *responses: Any) -> Iterator[None]:
    """Queue canned responses for `call` while the block runs (fake mode only).

    Each response is used once, in order, except the last, which repeats. A response is:
    - for `generate_json`: a dict (the JSON object) or a str (raw text, e.g. to test bad JSON);
    - for `call_with_tools`: `{"tool_call": {"name": ..., "args": {...}}}` or `{"text": "..."}`;
    - or an exception instance, which is raised instead.
    """
    if not responses:
        raise ValueError("fake_responses needs at least one response")
    previous = _fake_queue.get(call)
    _fake_queue[call] = list(responses)
    try:
        yield
    finally:
        if previous is None:
            _fake_queue.pop(call, None)
        else:
            _fake_queue[call] = previous


def _take_fake(call: str) -> Any:
    start = time.perf_counter()
    queue = _fake_queue.get(call)
    if queue:
        response = queue.pop(0) if len(queue) > 1 else queue[0]
    else:
        path = FAKES_DIR / f"{call}.json"
        if not path.is_file():
            _log(call, "fake", 1, start, "no fake")
            raise AIUnavailable(f"FAKE_AI is on and there is no canned response for {call!r} ({path.name})")
        response = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(response, BaseException):
        _log(call, "fake", 1, start, type(response).__name__)
        raise response
    _log(call, "fake", 1, start, "ok")
    return response


def _decode_fake_turn(raw: Any, tools: Sequence[Tool]) -> ToolCall | Text:
    if isinstance(raw, dict) and isinstance(raw.get("tool_call"), dict):
        tc = raw["tool_call"]
        return _check_tool_call(str(tc.get("name", "")), dict(tc.get("args") or {}), tools)
    if isinstance(raw, dict) and isinstance(raw.get("text"), str) and raw["text"].strip():
        return Text(raw["text"].strip())
    raise AIInvalidOutput("Fake response is neither {'tool_call': ...} nor {'text': ...}")
