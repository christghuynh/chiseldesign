"""Regenerates the shared fixtures from the REAL engine (task GEO-16).

Run from backend/:  uv run python scripts/regenerate_fixtures.py

Writes fixtures/specs/ramp_straight.json, fixtures/specs/ramp_switchback.json (each a full
`{spec, plan}` generate response), fixtures/skeletons/ramp_straight.json, and refreshes the part labels
and spoken cut callouts in fixtures/instructions/ramp_switchback.json (its wording is hand-written; only the
labels move when the cut list changes). The frontend runs on these in fixture mode, so re-run this and
announce it whenever the engine's output changes.

Scenario (not the demo numbers): a 15 in rise with 160 in available. The straight ramp needs 15 ft, so it
fails the site-fit rule with a one-click switchback fix; the switchback fits.
"""

import json
import math
from pathlib import Path

from app import engine
from app.models import BuildStep, CutCallout, CutListRow, GenerateResponse, ParamValue

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

META = {
    "contractor_quote_cad": 4000.0,
    "notes": "Generated from the real engine by backend/scripts/regenerate_fixtures.py. Prices are placeholders.",
    "image_ref": None,
}
COMMON = {
    "total_rise_in": ParamValue(value=15, source="inferred", confidence=0.7),
    "available_length_in": ParamValue(value=160, source="user"),
}


def _is_number_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(x, (int, float, str)) and not isinstance(x, bool) for x in value) and len(json.dumps(value)) < 100


def _dumps(obj: object, indent: int = 0) -> str:
    """JSON with short scalar lists on one line (profiles, labels) so the fixtures stay readable."""
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f'{pad}  {json.dumps(k)}: {_dumps(v, indent + 1)}' for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        if _is_number_list(obj) or (all(_is_number_list(x) for x in obj) and len(obj) <= 12):
            return json.dumps(obj, ensure_ascii=False)
        return "[\n" + ",\n".join(f"{pad}  {_dumps(x, indent + 1)}" for x in obj) + f"\n{pad}]"
    return json.dumps(obj, ensure_ascii=False)


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((_dumps(obj) + "\n").encode("utf-8"))  # bytes: keep LF on Windows
    print(f"wrote {path.relative_to(FIXTURES.parent)}")


# --- spoken numbers for the instructions fixture (the real code-generated callouts are a later task) ---
_FRACTIONS = {1: "a sixteenth", 2: "an eighth", 3: "three sixteenths", 4: "a quarter", 5: "five sixteenths", 6: "three eighths", 7: "seven sixteenths",
              8: "a half", 9: "nine sixteenths", 10: "five eighths", 11: "eleven sixteenths", 12: "three quarters", 13: "thirteen sixteenths",
              14: "seven eighths", 15: "fifteen sixteenths"}
_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_MATERIAL = {"2x4_PT": "two-by-four", "2x6_PT": "two-by-six", "2x8_PT": "two-by-eight", "4x4_PT": "four-by-four", "5/4x6_PT_deck": "five-quarter deck board"}


def _words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    hundreds, rest = divmod(n, 100)
    return _ONES[hundreds] + " hundred" + ("" if rest == 0 else " " + _words(rest))


def _spoken_length(inches: float) -> str:
    whole, frac = divmod(math.floor(inches * 16 + 0.5), 16)
    return f"{_words(whole)} inches" if frac == 0 else f"{_words(whole)} and {_FRACTIONS[frac]} inches"


# Which part names each instruction step concerns (by step number), and which steps read cut callouts.
_STEP_NAMES = {
    2: {"Stringer"},
    3: {"Ledger", "Landing rim (end)", "Landing rim (side)", "Landing joist"},
    4: {"Landing rim (end)", "Landing rim (side)", "Landing joist", "Landing post", "Landing deck board"},
    5: {"Ledger"},
    6: {"Stringer"},
    7: {"Stringer"},
    8: {"Deck board"},
    9: {"Edge curb"},
    10: {"Handrail post", "Handrail"},
}
_CALLOUT_NAMES = {
    2: {"Stringer"},
    3: {"Ledger", "Landing rim (end)", "Landing rim (side)", "Landing joist"},
    4: {"Landing deck board"},
    8: {"Deck board"},
    9: {"Edge curb"},
    10: {"Handrail post", "Handrail"},
}


def _refresh_instructions(rows: list[CutListRow]) -> None:
    path = FIXTURES / "instructions" / "ramp_switchback.json"
    steps = json.loads(path.read_text("utf-8"))["steps"]
    for step in steps:
        n = step["n"]
        step["part_labels"] = sorted({r.label for r in rows if r.name in _STEP_NAMES.get(n, set())})
        step["cut_callouts"] = [
            CutCallout(label=r.label, spoken=f"{_MATERIAL[r.material]}, {_spoken_length(r.length_in)}").model_dump(mode="json")
            for r in rows
            if r.name in _CALLOUT_NAMES.get(n, set())
        ]
        BuildStep.model_validate(step)  # still a valid step
    _write(path, {"steps": steps})


def main() -> None:
    straight_spec, straight_plan = engine.generate("ramp", {**COMMON, "layout": ParamValue(value="straight", source="user")}, META)
    switch_spec, switch_plan = engine.generate("ramp", {**COMMON, "layout": ParamValue(value="switchback", source="user")}, META)
    _write(FIXTURES / "specs" / "ramp_straight.json", GenerateResponse(spec=straight_spec, plan=straight_plan).model_dump(mode="json"))
    _write(FIXTURES / "specs" / "ramp_switchback.json", GenerateResponse(spec=switch_spec, plan=switch_plan).model_dump(mode="json"))
    _write(FIXTURES / "skeletons" / "ramp_straight.json", [s.model_dump(mode="json") for s in engine.get_skeleton(straight_spec)])
    _refresh_instructions(switch_plan.cut_list)


if __name__ == "__main__":
    main()
