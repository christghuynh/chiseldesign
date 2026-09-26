"""Part geometry helpers: board extents and a placement-independent shape signature.

Convention (see models/core.py): a Part is a counter-clockwise 2D `profile` extruded along local +Z
by `thickness`. `thickness` is the extrusion depth, NOT necessarily the board thickness: stringers
carry their length in the profile, while deck boards, ledgers, joists and posts carry a small
cross-section in the profile and their length in `thickness`. So a part's board length is the longest
of three extents: the profile's extent along its longest edge, the profile's extent perpendicular to
that, and `thickness`.
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
    """(extent along the longest profile edge, extent perpendicular to it, thickness), each rounded to 3 decimals.

    When several edges tie for longest (rectangles, rhombi) the one giving the largest along-extent is
    used, so the result does not depend on which vertex the profile list starts at.
    """
    _require_polygon(part)
    edges = _edges(part.profile)
    lengths = [math.hypot(ex, ey) for ex, ey in edges]
    longest = max(lengths)
    if longest <= _EPS:
        raise ValueError(f"Part {part.id!r} has a degenerate profile")
    best: tuple[float, float] | None = None
    for (ex, ey), length in zip(edges, lengths, strict=True):
        if length < longest - 1e-6:
            continue
        ux, uy = ex / length, ey / length
        along = [x * ux + y * uy for x, y in part.profile]
        perp = [-x * uy + y * ux for x, y in part.profile]
        candidate = (max(along) - min(along), max(perp) - min(perp))
        if best is None or (candidate[0], -candidate[1]) > (best[0], -best[1]):
            best = candidate
    assert best is not None
    return (round(best[0], 3), round(best[1], 3), round(part.thickness, 3))


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
