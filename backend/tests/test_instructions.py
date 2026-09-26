"""AI-6 tests for /instructions. FAKE_AI mode; engine is monkeypatched where needed.

The engine stubs return the straight-ramp skeleton (10 steps) and a fixed cut list. We assert the
AI rewrite passes through when valid, that an invented label triggers the skeleton fallback, that
cut callouts are generated in code from the cut list, and that AI errors fall back with a 200.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai import numwords
from app.ai.client import AIInvalidOutput, AIUnavailable, fake_responses
from app.main import app
from app.models import InstructionsResponse

client = TestClient(app)

_STRAIGHT = json.loads((Path(__file__).resolve().parents[2] / "fixtures/specs/ramp_straight.json").read_text())
SPEC = _STRAIGHT["spec"]


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch):
    monkeypatch.setenv("FAKE_AI", "1")


def _post():
    return client.post("/api/instructions", json={"spec": SPEC})


def _valid_ai_steps(n=10):
    # n steps, each using labels that exist in the straight cut list (A..J).
    labels_cycle = [[], ["C"], ["D"], ["D"], ["C"], ["C"], ["H", "I", "J"], ["A"], ["B", "E", "F", "G"], []]
    steps = []
    for i in range(n):
        steps.append(
            {
                "title": f"Step {i + 1}",
                "text": "Do the thing carefully.",
                "part_labels": labels_cycle[i % len(labels_cycle)],
                "safety_tip": "Be careful." if i % 3 == 0 else None,
            }
        )
    return {"steps": steps}


def test_valid_rewrite_passes_through():
    with fake_responses("instructions", _valid_ai_steps(10)):
        r = _post()
    assert r.status_code == 200
    steps = InstructionsResponse.model_validate(r.json()).steps
    assert len(steps) == 10
    assert [s.n for s in steps] == list(range(1, 11))
    assert steps[0].title == "Step 1"
    assert steps[0].safety_tip == "Be careful."


def test_step_count_within_tolerance_passes():
    # skeleton is 10; 13 is within +3.
    with fake_responses("instructions", _valid_ai_steps(13)):
        r = _post()
    steps = InstructionsResponse.model_validate(r.json()).steps
    assert len(steps) == 13


def test_step_count_outside_tolerance_falls_back_to_the_skeleton():
    with fake_responses("instructions", _valid_ai_steps(20)):
        r = _post()
    steps = InstructionsResponse.model_validate(r.json()).steps
    # Fallback uses the 10-step skeleton titles.
    assert len(steps) == 10
    assert steps[1].title == "Cut all stringers"


def test_an_invented_label_triggers_the_fallback():
    bad = _valid_ai_steps(10)
    bad["steps"][2]["part_labels"] = ["ZZZ"]  # not in the cut list
    with fake_responses("instructions", bad):
        r = _post()
    steps = InstructionsResponse.model_validate(r.json()).steps
    # Fell back to skeleton, so titles come from the skeleton, not "Step 3".
    assert steps[0].title == "Prepare the site"
    assert all("Step " not in s.title for s in steps)


def test_cut_callouts_are_generated_in_code_from_the_cut_list():
    with fake_responses("instructions", _valid_ai_steps(10)):
        r = _post()
    steps = InstructionsResponse.model_validate(r.json()).steps
    # Step 2 cuts label C: 2x6_PT, 168.541 in.
    step_c = next(s for s in steps if s.part_labels == ["C"])
    assert len(step_c.cut_callouts) == 1
    callout = step_c.cut_callouts[0]
    assert callout.label == "C"
    assert callout.spoken == numwords.cut_callout_spoken("2x6_PT", 168.541)
    assert callout.spoken == "two-by-six, one hundred sixty-eight and nine sixteenths inches"


def test_callouts_only_appear_for_labels_that_cut_in_that_step():
    with fake_responses("instructions", _valid_ai_steps(10)):
        r = _post()
    steps = InstructionsResponse.model_validate(r.json()).steps
    for step in steps:
        callout_labels = [c.label for c in step.cut_callouts]
        assert callout_labels == [lab for lab in step.part_labels if lab in set("ABCDEFGHIJ")]


@pytest.mark.parametrize("exc", [AIUnavailable("down"), AIInvalidOutput("bad json")])
def test_ai_error_falls_back_with_a_200(exc):
    with fake_responses("instructions", exc):
        r = _post()
    assert r.status_code == 200
    steps = InstructionsResponse.model_validate(r.json()).steps
    assert len(steps) == 10
    assert steps[0].title == "Prepare the site"
    # Fallback still attaches code-generated callouts.
    step_c = next(s for s in steps if s.part_labels == ["C"])
    assert step_c.cut_callouts and step_c.cut_callouts[0].spoken.startswith("two-by-six,")


def test_shipped_instructions_fake_is_valid_and_used_by_default():
    r = _post()  # no queued response -> uses fakes/instructions.json
    assert r.status_code == 200
    steps = InstructionsResponse.model_validate(r.json()).steps
    assert len(steps) == 10
    assert steps[0].title == "Prepare the site"
