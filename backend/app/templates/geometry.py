"""Pure 2D geometry helpers and the `PartBuilder` shared by every template.

Conventions (verified by the frame tests): Y-up world in inches. A Part is a counter-clockwise 2D
`profile` in the part's local XY plane, extruded along local +Z by `thickness`, rotated by Euler XYZ
(radians) and translated by `pos`. Templates only ever rotate by 0 or pi about Y (to mirror a run
that travels back toward -X), so `PartBuilder` refuses any other rotation.
"""

import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from app.models import Part, Transform

Point = tuple[float, float]


def r3(value: float) -> float:
    """Round to 3 decimals and turn -0.0 into 0.0, so output is deterministic and clean."""
    return round(value, 3) + 0.0


def signed_area(poly: Sequence[Point]) -> float:
    """Positive for a counter-clockwise polygon."""
    n = len(poly)
    return sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) / 2


def ensure_ccw(poly: Sequence[Point]) -> list[Point]:
    pts = list(poly)
    return pts if signed_area(pts) > 0 else pts[::-1]


def dedupe(poly: Sequence[Point], tol: float = 1e-9) -> list[Point]:
    """Drop consecutive duplicate points, and a last point equal to the first. Keeps the first vertex."""
    out: list[Point] = []
    for pt in poly:
        if not out or math.dist(pt, out[-1]) > tol:
            out.append(pt)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= tol:
        out.pop()
    return out


def clip_y(poly: Sequence[Point], y_min: float) -> list[Point]:
    """Sutherland-Hodgman clip of a polygon to y >= y_min. Returns [] if nothing survives."""
    out: list[Point] = []
    for i, cur in enumerate(poly):
        prev = poly[i - 1]
        cur_in, prev_in = cur[1] >= y_min - 1e-9, prev[1] >= y_min - 1e-9
        if cur_in != prev_in:
            t = (y_min - prev[1]) / (cur[1] - prev[1])
            out.append((prev[0] + t * (cur[0] - prev[0]), y_min))
        if cur_in:
            out.append(cur)
    return dedupe(out)


def extent_along(poly: Sequence[Point], direction: Point) -> float:
    """Length of the polygon's shadow on a unit direction."""
    values = [p[0] * direction[0] + p[1] * direction[1] for p in poly]
    return max(values) - min(values)


def normalize_profile(poly: Sequence[Point]) -> list[Point]:
    """Counter-clockwise, no duplicate points, rounded to 3 decimals. Raises if degenerate."""
    pts = ensure_ccw(dedupe([(r3(x), r3(y)) for x, y in poly]))
    if len(pts) < 3 or signed_area(pts) <= 1e-6:
        raise ValueError(f"degenerate profile: {list(poly)}")
    return pts


class PartBuilder:
    """Collects parts. Ids are temporary (`T-1`, `T-2`, ...) and the label is `T`: the cut list step
    (`cutlist.label_parts`) assigns the real labels and ids.

    Use `frame()` to build a run in its own coordinates and place it in the world:

        with builder.frame(origin=(90, 7.5, 48), flip=True):
            builder.add("Stringer", "2x6_PT", profile, 1.5, pos=(0, 0, -18), ...)

    With `flip=False` a part's pos is `origin + pos`. With `flip=True` the frame is mirrored by
    rotating pi about Y (local x -> -x, local z -> -z), so a run can travel back toward -X: the
    part's rot becomes (0, pi, 0) and its pos is `(ox - px, oy + py, oz - pz)`. Profiles are given
    in the frame's local coordinates and are never modified.
    """

    def __init__(self) -> None:
        self.parts: list[Part] = []
        self._origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._flip = False

    @contextmanager
    def frame(self, origin: tuple[float, float, float] = (0.0, 0.0, 0.0), flip: bool = False) -> Iterator["PartBuilder"]:
        previous = (self._origin, self._flip)
        self._origin, self._flip = origin, flip
        try:
            yield self
        finally:
            self._origin, self._flip = previous

    def add(
        self,
        name: str,
        material: str,
        profile: Sequence[Point],
        thickness: float,
        pos: tuple[float, float, float] = (0.0, 0.0, 0.0),
        cut_notes: Sequence[str] = (),
        group: str | None = None,
    ) -> Part:
        ox, oy, oz = self._origin
        px, py, pz = pos
        if self._flip:
            world_pos, rot = (ox - px, oy + py, oz - pz), (0.0, math.pi, 0.0)
        else:
            world_pos, rot = (ox + px, oy + py, oz + pz), (0.0, 0.0, 0.0)
        part = Part(
            id=f"T-{len(self.parts) + 1}",
            label="T",
            name=name,
            material=material,
            profile=normalize_profile(profile),
            thickness=r3(thickness),
            transform=Transform(pos=tuple(r3(v) for v in world_pos), rot=rot),
            cut_notes=list(cut_notes),
            group=group,
        )
        self.parts.append(part)
        return part
