"""Small builders shared by the geometry-engine tests (cut list, nesting, pricing, plan)."""

import math
from pathlib import Path

from app.models import GenerateResponse, Part, Transform

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SPEC_FILES = ["ramp_straight.json", "ramp_switchback.json"]


def load_fixture(name: str) -> GenerateResponse:
    return GenerateResponse.model_validate_json((FIXTURES / "specs" / name).read_text("utf-8"))


def rect_profile(w: float, h: float, x0: float = 0.0, y0: float = 0.0) -> list[tuple[float, float]]:
    return [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]


def make_part(
    name: str = "Joist",
    material: str = "2x6_PT",
    profile: list[tuple[float, float]] | None = None,
    thickness: float = 60.0,
    pos: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rot: tuple[float, float, float] = (0.0, 0.0, 0.0),
    cut_notes: list[str] | None = None,
    group: str | None = None,
    label: str = "",
    id: str = "",
) -> Part:
    """A board-style part: 1.5 x 5.5 cross-section in the profile, its length in `thickness`."""
    return Part(
        id=id,
        label=label,
        name=name,
        material=material,
        profile=profile if profile is not None else rect_profile(1.5, 5.5),
        thickness=thickness,
        transform=Transform(pos=pos, rot=rot),
        cut_notes=cut_notes or [],
        group=group,
    )


def rotate_profile(profile: list[tuple[float, float]], degrees: float, dx: float = 0.0, dy: float = 0.0):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [(x * c - y * s + dx, x * s + y * c + dy) for x, y in profile]
