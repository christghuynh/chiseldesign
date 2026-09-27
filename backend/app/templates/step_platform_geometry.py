"""Stringer geometry and board sizes for the step platform. One source of truth used by `derive`, the
part builders and the tests, so they cannot disagree about how long a stringer is.

Frame of a stringer profile: local x = 0 is its FRONT face (the face the first riser's back touches),
local y = 0 is the ground. The stringer is a 2x10 cut into a sawtooth. Going up the steps (n risers of
height `h`, pitch `T` between riser fronts, tread thickness `t`):

    notch k floor   y = k*h - t     for x in [(k-1)*T, k*T]          k = 1 .. n-1   (tread underside)
    notch k wall    x = k*T         from y = k*h - t up to (k+1)*h - t                (riser back)
    top ledge       y = n*h - t     for x in [(n-1)*T, (n-1)*T + LEDGE]               (under the porch)
    plumb cut       x = (n-1)*T + LEDGE, from the top ledge down to the lower edge

The lower edge is parallel to the line through the notch corners and sits one board width below the
tooth tips, so it leaves a "throat" of solid wood under every notch. Wherever that line would go below
the ground the profile is clipped level, which gives the flat cut on the ground.
"""

import math

from app.cutlist.geometry import part_length
from app.models import Part, Transform
from app.templates.geometry import Point, clip_y, normalize_profile

# How far the stringer runs past the last riser's back face, under the porch edge, before its plumb
# cut. A design choice for the planning model, not a code figure.
LEDGE_IN = 3.5

# Thinnest throat (wood left under a notch, measured square to the slope) we still draw.
MIN_THROAT_IN = 1.0  # placeholder, to verify


def notch_depth(riser_h: float, tread_depth: float) -> float:
    """Depth of one notch measured square to the slope: the altitude of the h x T right triangle."""
    return riser_h * tread_depth / math.hypot(riser_h, tread_depth)


def throat(riser_h: float, tread_depth: float, board_width: float) -> float:
    """Solid wood left under the notches, square to the slope: board width minus the notch depth."""
    return board_width - notch_depth(riser_h, tread_depth)


def stringer_profile(
    riser_count: int,
    riser_h: float,
    tread_depth: float,
    tread_t: float,
    board_width: float,
    ledge_in: float = LEDGE_IN,
) -> list[Point]:
    """Counter-clockwise sawtooth outline of one stringer, 3-decimal rounded, starting at the
    front-bottom corner (0, 0). Needs at least two risers (one tread). Raises ValueError when the
    notches leave less than MIN_THROAT_IN of wood. `ledge_in` is how far the stringer runs past the last
    riser's back face before its plumb cut: under a porch edge, or 0 when it butts against a top platform."""
    n, h, T, t = riser_count, riser_h, tread_depth, tread_t
    if n < 2:
        raise ValueError("a stringer needs at least two risers")
    wood = throat(h, T, board_width)
    if wood < MIN_THROAT_IN - 1e-9:
        raise ValueError(f"notches of {h} x {T} leave only {wood:.2f} in of wood in a {board_width} in wide stringer")
    hyp = math.hypot(h, T)
    drop = wood * hyp / T  # vertical distance from the notch-corner line down to the lower edge, plus t below

    def lower(x: float) -> float:
        return (h / T) * x - t - drop

    x_end = (n - 1) * T + ledge_in
    raw: list[Point] = [(0.0, lower(0.0)), (x_end, lower(x_end))]
    if ledge_in > 1e-9:  # the seat that runs under the porch edge
        raw.append((x_end, n * h - t))
    for k in range(n - 1, -1, -1):
        # Butting a platform, the plumb cut stops at the last notch: the platform carries the top step.
        if not (k == n - 1 and ledge_in <= 1e-9):
            raw.append((k * T, (k + 1) * h - t))  # tooth tip
        if k >= 1:
            raw.append((k * T, k * h - t))  # notch corner
    clipped = clip_y(raw, 0.0)
    # Start at the lowest, then leftmost, vertex: the front-bottom corner.
    start = min(range(len(clipped)), key=lambda i: (round(clipped[i][1], 6), round(clipped[i][0], 6)))
    return normalize_profile(clipped[start:] + clipped[:start])


def profile_board_length(profile: list[Point], thickness: float, material: str) -> float:
    """Board length the cut list will report for a part with this profile (`app.cutlist.part_length`)."""
    part = Part(
        id="T-0",
        label="T",
        name="probe",
        material=material,
        profile=normalize_profile(profile),
        thickness=thickness,
        transform=Transform(pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0)),
    )
    return part_length(part)
