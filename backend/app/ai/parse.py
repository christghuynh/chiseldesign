"""AI-2 / AI-3: read a sketch or site photo into template parameters.

`parse_image()` is the whole parse pipeline minus HTTP: it asks Gemini to read the image
(structured output), normalizes every length it reports to inches, validates the values against
the chosen template's JSON Schema, fills unknowns with the template defaults, lets explicit user
measurements override, and returns a `ParseResponse` (spec has params + `assumed`, no parts).

Design notes for this lane:
- Gemini returns params as a LIST of {name, value, unit, confidence, source}; a fixed-key list is
  easier for structured output than an object keyed by unknown param names.
- The template catalog in the prompt is rebuilt from `engine.list_templates()` every call, so new
  templates from P1 show up without touching this file.
- Numbers are never computed here. Gemini reads; code normalizes, validates, defaults and merges.
- Required params with no reading and no default are NOT invented: they are left out, a question is
  added, and the caller still returns a spec so the UI can prompt for them.

The AI never computes dimensions, quantities or prices.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import jsonschema

from app import engine
from app.ai import client
from app.models import ParamValue, ParseResponse, Spec, TemplateInfo
from app.util.units import parse_length

log = logging.getLogger("app.ai")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "parse.md"

# Units Gemini may tag a length with. Everything internal is inches.
_LENGTH_UNITS_TO_INCHES = {
    "in": 1.0,
    "inch": 1.0,
    "inches": 1.0,
    '"': 1.0,
    "ft": 12.0,
    "foot": 12.0,
    "feet": 12.0,
    "'": 12.0,
    "cm": 1.0 / 2.54,
    "mm": 1.0 / 25.4,
    "m": 1000.0 / 25.4,
}

# The structured-output schema we hand to Gemini. A JSON Schema dict (not a Pydantic model) so we
# fully control the shape and can keep params as a list of loosely-typed values.
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "template": {"type": ["string", "null"]},
        "template_confidence": {"type": "number"},
        "params": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": ["number", "string", "boolean"]},
                    "unit": {"type": ["string", "null"]},
                    "confidence": {"type": ["number", "null"]},
                    "source": {"type": "string", "enum": ["read", "inferred"]},
                },
                "required": ["name", "value", "source"],
            },
        },
        "questions": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": ["template", "template_confidence", "params", "questions", "notes"],
}

# Measurement keys the frontend may send (form field -> canonical param name). The Capture form
# offers total rise, available length and desired width plus a contractor quote; accept both the
# form names and the canonical param keys.
_MEASUREMENT_ALIASES = {
    "total_rise": "total_rise_in",
    "total_rise_in": "total_rise_in",
    "rise": "total_rise_in",
    "available_length": "available_length_in",
    "available_length_in": "available_length_in",
    "length": "available_length_in",
    "desired_width": "clear_width_in",
    "clear_width": "clear_width_in",
    "clear_width_in": "clear_width_in",
    "width": "clear_width_in",
}
_QUOTE_KEYS = {"contractor_quote", "contractor_quote_cad", "quote"}
# The form's fields use the ramp's names; other templates call the same measurement something else.
_EQUIVALENTS = {"clear_width_in": ("clear_width_in", "width_in")}


class ParseError(Exception):
    """Gemini answered but its output could not be turned into a spec after one retry."""


# ---------------------------------------------------------------------------------------------
# Prompt


def _templates() -> list[TemplateInfo]:
    return engine.list_templates()


def build_prompt(templates: list[TemplateInfo]) -> str:
    """Fill the parse template with a human-readable catalog of every engine template."""
    catalog = "\n\n".join(_describe_template(t) for t in templates)
    return _PROMPT_PATH.read_text(encoding="utf-8").replace("{templates}", catalog)


def _describe_template(t: TemplateInfo) -> str:
    props: dict[str, Any] = t.params_schema.get("properties", {})
    required = set(t.params_schema.get("required", []))
    lines = [f"## {t.key} — {t.name}", t.description, "", "Parameters:"]
    for name, spec in props.items():
        lines.append(f"- {name}: {_describe_param(name, spec, name in required)}")
    return "\n".join(lines)


def _describe_param(name: str, spec: dict[str, Any], is_required: bool) -> str:
    bits: list[str] = []
    title = spec.get("title")
    if title and title != name:
        bits.append(title)
    if "enum" in spec:
        bits.append("one of " + ", ".join(str(v) for v in spec["enum"]))
    else:
        bits.append(f"type {_type_text(spec.get('type'))}")
    lo, hi = spec.get("minimum"), spec.get("maximum")
    if lo is not None or hi is not None:
        bits.append(f"range {lo if lo is not None else '-'}..{hi if hi is not None else '-'}")
    if spec.get("description"):
        bits.append(spec["description"])
    bits.append("required" if is_required else "optional")
    return "; ".join(bits)


def _type_text(t: Any) -> str:
    if isinstance(t, list):
        return "/".join(str(x) for x in t)
    return str(t)


# ---------------------------------------------------------------------------------------------
# Normalization + merge


def _normalize_length(value: Any, unit: str | None) -> float:
    """Turn a reading into inches. Handles numeric+unit and feet-and-inches strings."""
    if isinstance(value, str):
        # A string value (e.g. "1' 9\"" or "5 1/2") is a length regardless of the unit tag.
        inches = parse_length(value)
    elif isinstance(value, bool):
        raise ValueError("boolean is not a length")
    else:
        factor = _LENGTH_UNITS_TO_INCHES.get((unit or "in").strip().lower(), None)
        if factor is None:
            raise ValueError(f"unknown length unit {unit!r}")
        inches = float(value) * factor
    return round(inches, 4)


def _is_length_param(spec: dict[str, Any]) -> bool:
    """A param is a length if its type admits numbers and it isn't an enum."""
    if "enum" in spec:
        return False
    t = spec.get("type")
    types = t if isinstance(t, list) else [t]
    return "number" in types or "integer" in types


def _coerce_reading(name: str, value: Any, unit: str | None, spec: dict[str, Any]) -> float | int | str | bool:
    """Coerce one Gemini reading to the param's type, normalizing lengths to inches."""
    if "enum" in spec:
        return value  # validated below against the schema
    t = spec.get("type")
    types = t if isinstance(t, list) else [t]
    if "boolean" in types:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "1"}
        return bool(value)
    if _is_length_param(spec):
        # Length params carry the `_in` convention; normalize the unit to inches.
        return _normalize_length(value, unit)
    if "string" in types:
        return str(value)
    # Bare number, no unit convention.
    return float(value)


def _validate_value(name: str, value: Any, spec: dict[str, Any]) -> None:
    jsonschema.validate(value, spec)


def parse_measurements(measurements: dict[str, Any] | None) -> tuple[dict[str, float], float | None]:
    """Split the frontend measurements blob into {canonical_param: inches} and a contractor quote.

    Values may be numbers (inches) or length strings ("5' 4\"", "12 ft" is not accepted here as a
    bare string — the form sends inches; strings are parsed as inches/ft-in via parse_length).
    Unknown keys are ignored.
    """
    overrides: dict[str, float] = {}
    quote: float | None = None
    for raw_key, raw_val in (measurements or {}).items():
        key = str(raw_key).strip().lower()
        if key in _QUOTE_KEYS:
            if raw_val not in (None, ""):
                quote = float(raw_val)
            continue
        param = _MEASUREMENT_ALIASES.get(key)
        if param is None or raw_val in (None, ""):
            continue
        overrides[param] = parse_length(raw_val) if isinstance(raw_val, str) else float(raw_val)
    return overrides, quote


def _merge(
    template: str,
    schema: dict[str, Any],
    defaults: dict[str, Any],
    readings: list[dict[str, Any]],
    user_overrides: dict[str, float],
) -> tuple[dict[str, ParamValue], list[str], list[str]]:
    """Combine readings, defaults and user overrides into params + assumed + questions-to-add.

    Precedence: user > read/inferred > default. A required param with neither a reading nor a
    default is left out and reported as a missing param (the caller turns it into a question).
    """
    props: dict[str, Any] = schema.get("properties", {})
    required = set(schema.get("required", []))
    params: dict[str, ParamValue] = {}

    # 1. Readings from Gemini (skip anything not in the template).
    for r in readings:
        name = r.get("name")
        spec = props.get(name)
        if spec is None:
            continue
        try:
            value = _coerce_reading(name, r.get("value"), r.get("unit"), spec)
            _validate_value(name, value, spec)
        except (ValueError, TypeError, jsonschema.ValidationError) as exc:
            log.info("parse: dropped reading %s=%r (%s)", name, r.get("value"), exc)
            continue
        source = r.get("source") if r.get("source") in {"read", "inferred"} else "inferred"
        conf = r.get("confidence")
        params[name] = ParamValue(value=value, source=source, confidence=conf)

    # 2. User measurements override (source user, no confidence).
    for field, inches in user_overrides.items():
        name = next((n for n in _EQUIVALENTS.get(field, (field,)) if n in props), None)
        spec = props.get(name) if name else None
        if spec is None:
            continue
        try:
            _validate_value(name, inches, spec)
        except jsonschema.ValidationError as exc:
            log.info("parse: dropped user override %s=%r (%s)", name, inches, exc)
            continue
        params[name] = ParamValue(value=inches, source="user")

    # 3. Fill unknowns with defaults where one exists and is not null.
    #    ParamValue.value cannot be None, so a null default (e.g. available_length_in = "no limit")
    #    is left unset; the engine treats a missing optional param as its own default.
    for name, spec in props.items():
        if name in params:
            continue
        has_default = name in defaults or "default" in spec
        if not has_default:
            continue
        default = defaults.get(name, spec.get("default"))
        if default is None:
            continue
        params[name] = ParamValue(value=default, source="default")

    # 4. assumed = names whose source is inferred or default.
    assumed = sorted(n for n, p in params.items() if p.source in {"inferred", "default"})

    # 5. Required params still missing (no reading, no default): must not be invented.
    missing_required = sorted(n for n in required if n not in params)
    return params, assumed, missing_required


# ---------------------------------------------------------------------------------------------
# Public entry point


def parse_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    measurements: dict[str, Any] | None = None,
    note: str | None = None,
) -> ParseResponse:
    """Run the full parse pipeline. Raises ParseError if Gemini's output is unusable after retry.

    `client.AIUnavailable` propagates (the route maps it to 503). Image validation/resizing is the
    route's job (A4); this takes already-prepared bytes.
    """
    templates = _templates()
    schema_by_key = {t.key: t for t in templates}
    prompt = build_prompt(templates)
    if note:
        prompt = f"{prompt}\n\n# User note\n{note.strip()}"

    reading = _read_with_retry(prompt, image_bytes, mime_type)

    template = reading.get("template")
    notes = str(reading.get("notes") or "")
    questions = [str(q) for q in (reading.get("questions") or [])][:3]
    template_confidence = reading.get("template_confidence")

    user_overrides, quote = parse_measurements(measurements)

    # Unknown / unsupported object: no spec, reason in raw_notes.
    if not template or template not in schema_by_key:
        return ParseResponse(
            spec=None,
            template_confidence=template_confidence,
            questions=questions,
            raw_notes=notes or "The image did not match any supported template.",
        )

    info = schema_by_key[template]
    params, assumed, missing_required = _merge(
        template, info.params_schema, info.defaults, reading.get("params") or [], user_overrides
    )

    for name in missing_required:
        q = f"What is the {_friendly(info.params_schema, name)}? I could not read it from the image."
        if q not in questions and len(questions) < 3:
            questions.append(q)

    meta: dict[str, Any] = {}
    if quote is not None:
        meta["contractor_quote_cad"] = quote

    spec = Spec(template=template, params=params, assumed=assumed, meta=meta)
    return ParseResponse(
        spec=spec,
        template_confidence=template_confidence,
        questions=questions,
        raw_notes=notes,
    )


def _friendly(schema: dict[str, Any], name: str) -> str:
    spec = schema.get("properties", {}).get(name, {})
    return str(spec.get("title") or name)


def _read_with_retry(prompt: str, image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """One generate_json call, retried once on invalid output (AI-4). AIUnavailable propagates."""
    image = client.Image(data=image_bytes, mime_type=mime_type)
    try:
        return client.generate_json(prompt, RESPONSE_SCHEMA, images=[image], call="parse")
    except client.AIInvalidOutput as first:
        log.info("parse: invalid output, retrying once (%s)", first)
        try:
            return client.generate_json(prompt, RESPONSE_SCHEMA, images=[image], call="parse")
        except client.AIInvalidOutput as second:
            raise ParseError(str(second)) from second
