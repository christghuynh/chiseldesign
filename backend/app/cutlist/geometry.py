"""Part geometry helpers: board extents and a placement-independent shape signature.

Convention (see models/core.py): a Part is a counter-clockwise 2D `profile` extruded along local +Z
by `thickness`. `thickness` is the extrusion depth, NOT necessarily the board thickness: stringers
carry their length in the profile, while deck boards, ledgers, joists and posts carry a small
cross-section in the profile and their length in `thickness`. So a part's board length is the longest
of three extents: the two sides of the profile's minimum-area bounding rectangle, and `thickness`.

The board axis is found as the minimum-area bounding rectangle, NOT as the direction of the longest edge:
for a notched stair stringer the longest edge is a horizontal tread, but the board runs along the slope,
and measuring along the tread would report a stringer that is too short to cut.
"""

import math

from app.models import Part

_EPS = 1e-9


def _edges(profile: list[tuple[float, float]]) -> list[tuple[float, float]]:
    n = len(profile)
    return [(profile[(i + 1) % n][0] - profile[i][0], profile[(i + 1) % n][1] - profile[i][1]) for i in range(n)]


def _require_polygon(part: Part) -> None:
    if len(part.profile) < 3:
        raise ValueError(f"Part {part.id!r} has a profile with fewer than 3 points")


def part_extents(part: Part) -> tuple[float, float, float]:
    """(longer side, shorter side, thickness), each rounded to 3 decimals.

    The two sides come from the profile's minimum-area bounding rectangle: every profile edge is tried as
    the board axis and the orientation that encloses the least area wins. Ties (a rectangle has two equal
    orientations) take the longer long side, so the result never depends on which vertex the list starts at.
    """
    _require_polygon(part)
    edges = _edges(part.profile)
    best: tuple[float, float, float] | None = None  # (area, -long side, short side) with the long side
    for ex, ey in edges:
        length = math.hypot(ex, ey)
        if length <= _EPS:
            continue
        ux, uy = ex / length, ey / length
        along = [x * ux + y * uy for x, y in part.profile]
        perp = [-x * uy + y * ux for x, y in part.profile]
        a, b = max(along) - min(along), max(perp) - min(perp)
        key = (round(a * b, 6), -max(a, b), min(a, b))
        if best is None or key < best:
            best = key
    if best is None:
        raise ValueError(f"Part {part.id!r} has a degenerate profile")
    return (round(-best[1], 3), round(best[2], 3), round(part.thickness, 3))


def part_length(part: Part) -> float:
    """Board length of a part: the longest of its three extents, rounded to 3 decimals."""
    return round(max(part_extents(part)), 3)


def shape_signature(profile: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """A hashable description of the profile's shape, invariant to translation, in-plane rotation and start vertex.

    Canonical form: the cyclic sequence of (edge length rounded to 0.01, turn angle at the edge's end
    rounded to 0.1 degree), taken from whichever start vertex gives the smallest sequence. A clockwise
    profile is reversed first so orientation does not matter. Mirror images are NOT merged (a mirrored
    part is a different cut).
    """
    pts = list(profile)
    if len(pts) < 3:
        raise ValueError("a profile needs at least 3 points")
    n = len(pts)
    twice_area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    if twice_area < 0:
        pts.reverse()
    edges = _edges(pts)
    seq: list[tuple[float, float]] = []
    for i in range(n):
        ax, ay = edges[i]
        bx, by = edges[(i + 1) % n]
        turn = math.degrees(math.atan2(ax * by - ay * bx, ax * bx + ay * by))
        # + 0.0 turns -0.0 into 0.0 so the tuples compare and sort identically
        seq.append((round(math.hypot(ax, ay), 2) + 0.0, round(turn, 1) + 0.0))
    return min(tuple(seq[i:] + seq[:i]) for i in range(n))
