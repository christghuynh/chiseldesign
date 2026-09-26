"""AI-8: the parse eval runner works in fake mode (no network).

Imports the runner from evals/ (added to sys.path) and runs it with fake=True. The shipped fake
returns the ramp reading, so the runner should complete with exit 0 (no case errored) and print a
per-param summary.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "evals" / "run_parse_eval.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_parse_eval", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_parse_eval"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch):
    monkeypatch.setenv("FAKE_AI", "1")

    def _refuse(*_a, **_k):
        raise AssertionError("the eval test tried to create a real Gemini client")

    from app.ai import client

    monkeypatch.setattr(client, "_client_for", _refuse)


def test_eval_runner_exists_and_cases_file_is_valid():
    assert RUNNER.is_file()
    import json

    cases = json.loads((REPO_ROOT / "evals" / "parse_cases.json").read_text())
    assert len(cases["cases"]) >= 2
    assert all("image" in c and "expect" in c for c in cases["cases"])


def test_eval_runs_in_fake_mode_without_network(capsys):
    runner = _load_runner()
    rc = runner.run(fake=True)
    out = capsys.readouterr().out
    assert rc == 0  # fake mode skips missing images, so no case errors
    assert "overall:" in out
    assert "[FAKE]" in out
    # The shipped fake reads a ramp, so at least the template line should PASS somewhere.
    assert "template" in out
