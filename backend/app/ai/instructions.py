"""AI-6: turn the engine's deterministic build outline + cut list into friendly, spoken steps.

Flow (see `handle_instructions`):
1. `engine.get_skeleton(spec)` gives the ordered outline (phase, title, part labels per step).
2. `engine.generate(...)` gives the cut list (labels, materials, actual lengths).
3. Gemini rewrites the outline into warm, plain-language steps with optional safety tips. It is told
   never to state a measurement, quantity or price.
4. We validate the rewrite: same-ish step count (within ±3 of the outline), every `part_labels`
   entry must exist in the cut list, and each step must fit in one TTS request once its code-built
   cut callouts are added (`_spoken_length` <= `voice.tts.MAX_TEXT_CHARS`), or Build mode would get
   a 422 for that step instead of audio. If it fails — or the AI is unavailable — we fall back to
   skeleton-derived steps. The route always returns 200.
5. `cut_callouts` are built in code from the cut list via `numwords`, never from Gemini, and
   attached to each step for the labels that step cuts.

Both engine calls go through `app.engine` so tests can monkeypatch them.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app import engine
from app.ai import numwords
from app.ai.client import AIError, generate_json
from app.models import BuildStep, CutCallout, CutListRow, InstructionsResponse, SkeletonStep, Spec
from app.voice.tts import MAX_TEXT_CHARS

_PROMPT_PATH = Path(__file__).parent / "prompts" / "instructions.md"
_STEP_COUNT_TOLERANCE = 3


class _AIStep(BaseModel):
    title: str
    text: str
    part_labels: list[str] = []
    safety_tip: str | None = None


class _AISteps(BaseModel):
    steps: list[_AIStep]


_RESPONSE_SCHEMA = _AISteps


# ---------------------------------------------------------------------------------------------
# Cut callouts (code-generated), keyed by part label


def _callouts_by_label(cut_list: list[CutListRow]) -> dict[str, CutCallout]:
    out: dict[str, CutCallout] = {}
    for row in cut_list:
        out[row.label] = CutCallout(label=row.label, spoken=numwords.cut_callout_spoken(row.material, row.length_in))
    return out


def _callouts_for(labels: list[str], by_label: dict[str, CutCallout]) -> list[CutCallout]:
    return [by_label[label] for label in labels if label in by_label]


# ---------------------------------------------------------------------------------------------
# Prompt / context


def _skeleton_block(skeleton: list[SkeletonStep]) -> str:
    lines = []
    for i, step in enumerate(skeleton, 1):
        labels = ", ".join(step.part_labels) if step.part_labels else "none"
        lines.append(f"{i}. [{step.phase}] {step.title} — parts: {labels}")
    return "\n".join(lines)


def _parts_block(cut_list: list[CutListRow]) -> str:
    if not cut_list:
        return "(no parts)"
    return "\n".join(f"- {row.label}: {row.name}, {row.material}" for row in cut_list)


def _prompt(skeleton: list[SkeletonStep], cut_list: list[CutListRow]) -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").format(
        skeleton_block=_skeleton_block(skeleton),
        parts_block=_parts_block(cut_list),
    )


# ---------------------------------------------------------------------------------------------
# Fallback steps built straight from the skeleton


def _fallback_steps(skeleton: list[SkeletonStep], by_label: dict[str, CutCallout]) -> list[BuildStep]:
    steps = []
    for i, sk in enumerate(skeleton, 1):
        steps.append(
            BuildStep(
                n=i,
                title=sk.title,
                text=sk.title + ".",
                part_labels=list(sk.part_labels),
                cut_callouts=_callouts_for(sk.part_labels, by_label),
                safety_tip=None,
            )
        )
    return steps


# ---------------------------------------------------------------------------------------------
# Validation of the AI rewrite


def _spoken_length(step: _AIStep, by_label: dict[str, CutCallout]) -> int:
    """Characters Build mode sends to /voice/tts for this step, with some headroom.

    Mirrors `spokenText` in frontend/src/components/build/audioQueue.ts (title, text, then each
    callout, each ending in a period, joined by spaces) and also counts the safety tip, in case
    Build mode starts reading it.
    """
    parts = [step.title, step.text, *(c.spoken for c in _callouts_for(step.part_labels, by_label))]
    if step.safety_tip:
        parts.append(step.safety_tip)
    parts = [p.strip() for p in parts if p and p.strip()]
    return sum(len(p) + 1 for p in parts) + max(len(parts) - 1, 0)  # +1 for a period, + spaces


def _valid_rewrite(
    ai_steps: list[_AIStep],
    skeleton: list[SkeletonStep],
    known_labels: set[str],
    by_label: dict[str, CutCallout],
) -> bool:
    if abs(len(ai_steps) - len(skeleton)) > _STEP_COUNT_TOLERANCE:
        return False
    for step in ai_steps:
        for label in step.part_labels:
            if label not in known_labels:
                return False
        if _spoken_length(step, by_label) > MAX_TEXT_CHARS:
            return False
    return True


def _to_build_steps(ai_steps: list[_AIStep], by_label: dict[str, CutCallout]) -> list[BuildStep]:
    steps = []
    for i, step in enumerate(ai_steps, 1):
        steps.append(
            BuildStep(
                n=i,
                title=step.title,
                text=step.text,
                part_labels=list(step.part_labels),
                cut_callouts=_callouts_for(step.part_labels, by_label),
                safety_tip=step.safety_tip,
            )
        )
    return steps


# ---------------------------------------------------------------------------------------------
# Public entry point


def handle_instructions(spec: Spec) -> InstructionsResponse:
    """Build the spoken instructions. Never raises for an AI failure — falls back to the skeleton."""
    skeleton = engine.get_skeleton(spec)
    _, plan = engine.generate(spec.template, spec.params, spec.meta)
    by_label = _callouts_by_label(plan.cut_list)
    known_labels = set(by_label)

    try:
        raw = generate_json(_prompt(skeleton, plan.cut_list), _RESPONSE_SCHEMA, call="instructions")
        ai_steps = _AISteps.model_validate(raw).steps
    except AIError:
        return InstructionsResponse(steps=_fallback_steps(skeleton, by_label))

    if not _valid_rewrite(ai_steps, skeleton, known_labels, by_label):
        return InstructionsResponse(steps=_fallback_steps(skeleton, by_label))

    return InstructionsResponse(steps=_to_build_steps(ai_steps, by_label))
