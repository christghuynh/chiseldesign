"""Shared helpers for the ramp parts tests (no tests here; the name keeps it with the `test_ramp_` files)."""

import math

from app.models import Part
from app.templates.ramp import Params, derive
from app.templates.ramp_parts import build_parts

KNOWN_NAMES = {
    "Stringer",
    "Ledger",
    "Deck board",
    "Deck panel",
    "Edge curb",
    "Landing rim (end)",
    "Landing rim (side)",
    "Landing joist",
    "Landing deck board",
    "Landing deck panel",
    "Landing post",
    "Handrail post",
    "Handrail",
}


def make(**overrides) -> tuple[Params, object, list[Part]]:
    """Params (rise defaults to 12), the derived layout and the built parts."""
    values = {"total_rise_in": 12, **overrides}
    params = Params(**values)
    derived = derive(params)
    return params, derived, build_parts(params, derived)


def world_points(part: Part) -> list[tuple[float, float, float]]:
    """World-space corners of a part. Only rotation about Y is used by the templates."""
    rx, ry, rz = part.transform.rot
    assert rx == 0 and rz == 0 and (ry == 0 or abs(ry - math.pi) < 1e-9), f"unexpected rotation {part.transform.rot}"
    sign = -1.0 if ry else 1.0
    px, py, pz = part.transform.pos
    points = []
    for x, y in part.profile:
        for z in (0.0, part.thickness):
            points.append((px + sign * x, py + y, pz + sign * z))
    return points


def bbox(parts: list[Part]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    pts = [p for part in parts for p in world_points(part)]
    return tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3))  # type: ignore[return-value]


def named(parts: list[Part], name: str, group: str | None = None) -> list[Part]:
    return [p for p in parts if p.name == name and (group is None or p.group == group)]


def signed_area2(profile) -> float:
    n = len(profile)
    return sum(profile[i][0] * profile[(i + 1) % n][1] - profile[(i + 1) % n][0] * profile[i][1] for i in range(n))


def assert_invariants(parts: list[Part]) -> None:
    """Invariants every generated part list must satisfy."""
    assert parts
    assert len({p.id for p in parts}) == len(parts)
    for p in parts:
        where = f"{p.id} {p.name}"
        assert p.name in KNOWN_NAMES, where
        assert p.group, where
        assert p.thickness > 0 and math.isfinite(p.thickness), where
        assert len(p.profile) >= 3 and len(set(p.profile)) == len(p.profile), where
        assert all(math.isfinite(v) for pt in p.profile for v in pt), where
        assert all(math.isfinite(v) for v in (*p.transform.pos, *p.transform.rot)), where
        assert signed_area2(p.profile) > 0, f"{where} is not counter-clockwise"
        assert min(y for _, y in p.profile) + p.transform.pos[1] >= -1e-3, f"{where} goes below grade"
