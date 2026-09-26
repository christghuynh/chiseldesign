"""Loads the hand-built fixtures in /fixtures. Only the F-4 stub routes use this.

Real handlers replace these as the GEO/AI/VOX/INF tasks land.
"""

import json
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from app.config import settings
from app.models import GenerateResponse, InstructionsResponse, SkeletonStep, TemplateInfo

M = TypeVar("M", bound=BaseModel)


@lru_cache
def _read(relative: str) -> str:
    return (settings.fixtures_dir / relative).read_text(encoding="utf-8")


def _load(model: type[M], relative: str) -> M:
    # Validate on every call so handlers get their own copy and can't mutate the cache.
    return model.model_validate_json(_read(relative))


def ramp_plan(layout: str) -> GenerateResponse:
    """The straight fixture, or the switchback fixture when layout == "switchback"."""
    name = "ramp_switchback.json" if layout == "switchback" else "ramp_straight.json"
    return _load(GenerateResponse, f"specs/{name}")


def templates() -> list[TemplateInfo]:
    return [TemplateInfo.model_validate(t) for t in json.loads(_read("templates.json"))]


def ramp_instructions() -> InstructionsResponse:
    return _load(InstructionsResponse, "instructions/ramp_switchback.json")


def ramp_skeleton() -> list[SkeletonStep]:
    return [SkeletonStep.model_validate(step) for step in json.loads(_read("skeletons/ramp_straight.json"))]
