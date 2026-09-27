"""AI-5: turn a spoken or typed edit request into a parameter change, a rule fix, or a question.

Flow (see `handle_edit`):
1. Build the `set_params`/`apply_fix`/`ask_clarification` tools from the posted spec's template
   schema and its current rule checks.
2. Ask Gemini for exactly one tool call (`force_tool=True`).
3. Turn that tool call into a validated params patch:
   - `set_params` — reject unknown names and out-of-range enums; clamp numbers to the schema
     bounds (and note the clamp in the spoken message); patched values get source "user".
   - `apply_fix(rule_id)` — use the matching rule check's `fix.params_patch`; unknown id becomes a
     clarification.
   - `ask_clarification` / a plain text reply — no change; `needs_clarification` is true.
4. Regenerate through the engine (always via `app.engine.generate`, so tests can monkeypatch it)
   and build the one-sentence spoken message in code from the actual patched values.

Gemini never computes numbers here; it only picks the tool and the target value, which we validate.
On any AI failure the route raises AI_UNAVAILABLE (503) so the frontend falls back to its sliders
and typed box.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app import engine
from app.ai import numwords
from app.ai.client import AIError, Message, Text, Tool, ToolCall, call_with_tools
from app.models import EditResponse, ParamValue, Spec

_PROMPT_PATH = Path(__file__).parent / "prompts" / "edit.md"
_MAX_HISTORY = 10  # messages: the last 5 user/model exchanges


class EditError(Exception):
    """The AI could not be used; the caller turns this into AI_UNAVAILABLE (503)."""


# ---------------------------------------------------------------------------------------------
# Tool schemas built from the template


def _template_schema(template_key: str) -> dict[str, Any]:
    for tpl in engine.list_templates():
        if tpl.key == template_key:
            return tpl.params_schema
    # Unknown template: no properties, so every name is rejected and we clarify.
    return {"type": "object", "properties": {}}


def _tools_for(schema: dict[str, Any], rule_ids: list[str]) -> list[Tool]:
    # The patch schema is intentionally permissive: we validate names, enums and bounds in code
    # (clamping numbers) so that an out-of-range value reaches the handler instead of being
    # rejected as an invalid tool call. The property names/units guide the model via the prompt.
    set_params = Tool(
        name="set_params",
        description="Change one or more template parameters to new absolute values.",
        parameters={
            "type": "object",
            "properties": {
                "patch": {
                    "type": "object",
                    "description": "Parameter name to new value. Only the parameters being changed.",
                    "additionalProperties": True,
                }
            },
            "required": ["patch"],
        },
    )
    fix = Tool(
        name="apply_fix",
        description=(
            "Accept the suggested fix for a flagged rule check, by its id. "
            + ("Fixable rule ids: " + ", ".join(rule_ids) + "." if rule_ids else "There are no fixable rule checks.")
        ),
        parameters={
            "type": "object",
            "properties": {"rule_id": {"type": "string"}},
            "required": ["rule_id"],
        },
    )
    ask = Tool(
        name="ask_clarification",
        description="Ask one short question when the request cannot be mapped to a change or a fix.",
        parameters={
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    )
    return [set_params, fix, ask]


# ---------------------------------------------------------------------------------------------
# Prompt / context


def _param_lines(schema: dict[str, Any], params: dict[str, ParamValue]) -> str:
    props = schema.get("properties", {})
    lines = []
    for name, prop in props.items():
        bits = []
        if "enum" in prop:
            bits.append("one of " + ", ".join(str(v) for v in prop["enum"]))
        else:
            lo, hi = prop.get("minimum"), prop.get("maximum")
            if lo is not None or hi is not None:
                bits.append(f"range {lo if lo is not None else '-'}..{hi if hi is not None else '-'}")
        current = params.get(name)
        cur = current.value if current is not None else prop.get("default")
        desc = prop.get("description", "")
        meta = "; ".join(b for b in bits if b)
        lines.append(f"- {name}: {desc} ({meta}) current={cur!r}")
    return "\n".join(lines)


def _rule_lines(spec: Spec) -> str:
    if not spec.rule_checks:
        return "(none)"
    out = []
    for rc in spec.rule_checks:
        fixable = "fixable" if rc.fix is not None else "no fix"
        out.append(f"- {rc.id} [{rc.status}] {rc.title} ({fixable})")
    return "\n".join(out)


def _history(spec: Spec) -> list[Message]:
    """Prior turns from spec.meta['edit_turns'] (last few), if the frontend sent any.

    EditRequest has no history field yet (see QUESTIONS.md); until it does, callers may stash
    {role, text} turns in spec.meta. Anything malformed is ignored.
    """
    turns = spec.meta.get("edit_turns") if isinstance(spec.meta, dict) else None
    messages: list[Message] = []
    if isinstance(turns, list):
        for turn in turns[-_MAX_HISTORY:]:
            if isinstance(turn, dict) and turn.get("role") in {"user", "model"} and isinstance(turn.get("text"), str):
                messages.append(Message(turn["role"], turn["text"]))
    return messages


def _build_messages(spec: Spec, schema: dict[str, Any], utterance: str) -> list[Message]:
    history_block = "\n".join(f"{m.role}: {m.text}" for m in _history(spec)) or "(no earlier turns)"
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        template_key=spec.template,
        params_block=_param_lines(schema, spec.params),
        rules_block=_rule_lines(spec),
        history_block=history_block,
    )
    return [Message("user", prompt), Message("user", utterance)]


# ---------------------------------------------------------------------------------------------
# Patch validation


def _coerce_and_validate(name: str, value: Any, prop: dict[str, Any]) -> tuple[Any, str | None]:
    """Validate/clamp one value against its schema property. Returns (value, note).

    Raises ValueError for an unknown enum value or a wrong type. `note` describes a clamp, if any.
    """
    types = prop.get("type")
    type_set = set(types) if isinstance(types, list) else {types}

    if "enum" in prop:
        if value not in prop["enum"]:
            raise ValueError(f"{name} must be one of {', '.join(map(str, prop['enum']))}")
        return value, None

    if type_set & {"number", "integer"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number")
        num = float(value)
        note = None
        lo, hi = prop.get("minimum"), prop.get("maximum")
        if lo is not None and num < lo:
            num, note = float(lo), f"{name} can't go below {_fmt(lo)}, so I set it to the minimum"
        elif hi is not None and num > hi:
            num, note = float(hi), f"{name} can't go above {_fmt(hi)}, so I set it to the maximum"
        if type_set == {"integer"}:
            num = int(round(num))
        return num, note

    if type_set & {"boolean"}:
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be true or false")
        return value, None

    # string or anything else: accept as-is if it's a string
    if isinstance(value, str):
        return value, None
    raise ValueError(f"{name} has an unexpected value")


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def _validate_patch(patch: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return (clean_patch, clamp_notes). Raises ValueError on an unknown name/enum/type."""
    props = schema.get("properties", {})
    clean: dict[str, Any] = {}
    notes: list[str] = []
    for name, value in patch.items():
        if name not in props:
            raise ValueError(f"There's no setting called {name!r}")
        coerced, note = _coerce_and_validate(name, value, props[name])
        clean[name] = coerced
        if note:
            notes.append(note)
    if not clean:
        raise ValueError("empty patch")
    return clean, notes


# ---------------------------------------------------------------------------------------------
# Applying a patch to the spec params


def _apply_patch(spec: Spec, patch: dict[str, Any]) -> dict[str, ParamValue]:
    params = dict(spec.params)
    for name, value in patch.items():
        params[name] = ParamValue(value=value, source="user")
    return params


def _spoken_change(patch: dict[str, Any], schema: dict[str, Any], notes: list[str]) -> str:
    """One-sentence spoken confirmation built from the real patched values (never from the LLM)."""
    props = schema.get("properties", {})
    parts = []
    for name, value in patch.items():
        prop = props.get(name, {})
        label = _spoken_param_name(name)
        types = prop.get("type")
        type_set = set(types) if isinstance(types, list) else {types}
        if type_set & {"number", "integer"} and "enum" not in prop:
            if name.endswith("_in"):
                spoken_val = numwords.inches_words(float(value))
            elif float(value).is_integer():
                spoken_val = numwords.cardinal_words(int(value))
            else:
                spoken_val = str(value)
            parts.append(f"{label} to {spoken_val}")
        elif type_set & {"boolean"}:
            parts.append(f"{label} {'on' if value else 'off'}")
        else:
            parts.append(f"{label} to {str(value).replace('_', ' ')}")
    sentence = "Set " + _join(parts) + "."
    if notes:
        sentence += " " + _join(notes).capitalize() + "."
    return sentence


def _spoken_param_name(name: str) -> str:
    base = name[:-3] if name.endswith("_in") else name
    return base.replace("_", " ")


def _join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---------------------------------------------------------------------------------------------
# The route logic


def handle_edit(spec: Spec, utterance: str) -> EditResponse:
    """Interpret `utterance` against `spec`, regenerate, and return the edit response.

    Raises EditError on any AI failure (the route maps it to AI_UNAVAILABLE / 503).
    """
    messages_spec = spec
    # The conversation is request-only context: never regenerate (and so persist) it into the spec.
    if isinstance(spec.meta, dict) and "edit_turns" in spec.meta:
        spec = spec.model_copy(update={"meta": {k: v for k, v in spec.meta.items() if k != "edit_turns"}})
    schema = _template_schema(spec.template)
    rule_ids = [rc.id for rc in spec.rule_checks if rc.fix is not None]
    tools = _tools_for(schema, rule_ids)
    messages = _build_messages(messages_spec, schema, utterance)

    try:
        turn = call_with_tools(messages, tools, call="edit", force_tool=True)
    except AIError as exc:
        raise EditError(str(exc)) from exc

    if isinstance(turn, Text):
        return _clarify(spec, turn.text or "Sorry, could you say that another way?")

    assert isinstance(turn, ToolCall)
    if turn.name == "ask_clarification":
        question = str(turn.args.get("question") or "Could you say that another way?")
        return _clarify(spec, question)

    if turn.name == "apply_fix":
        return _apply_fix(spec, str(turn.args.get("rule_id", "")))

    if turn.name == "set_params":
        return _set_params(spec, schema, dict(turn.args.get("patch") or {}))

    # An unexpected tool name would already have been rejected by the client, but be safe.
    return _clarify(spec, "Could you say that another way?")


def _set_params(spec: Spec, schema: dict[str, Any], patch: dict[str, Any]) -> EditResponse:
    try:
        clean, notes = _validate_patch(patch, schema)
    except ValueError as exc:
        return _clarify(spec, f"{exc}. Could you try that again?")

    params = _apply_patch(spec, clean)
    new_spec, plan = engine.generate(spec.template, params, spec.meta)
    return EditResponse(
        spec=new_spec,
        plan=plan,
        patch=clean,
        message=_spoken_change(clean, schema, notes),
        needs_clarification=False,
    )


def _apply_fix(spec: Spec, rule_id: str) -> EditResponse:
    match = next((rc for rc in spec.rule_checks if rc.id == rule_id and rc.fix is not None), None)
    if match is None:
        return _clarify(spec, "I'm not sure which fix you mean. Which rule should I address?")
    patch = dict(match.fix.params_patch)
    params = _apply_patch(spec, patch)
    new_spec, plan = engine.generate(spec.template, params, spec.meta)
    return EditResponse(
        spec=new_spec,
        plan=plan,
        patch=patch,
        message=f"Applied the fix: {match.fix.label.lower()}.",
        needs_clarification=False,
    )


def _clarify(spec: Spec, question: str) -> EditResponse:
    """No change: regenerate the posted spec unchanged and flag that we need more input."""
    new_spec, plan = engine.generate(spec.template, spec.params, spec.meta)
    return EditResponse(
        spec=new_spec,
        plan=plan,
        patch={},
        message=question if question.endswith(("?", ".")) else question + "?",
        needs_clarification=True,
    )
