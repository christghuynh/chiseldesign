"""Slope math and the stringer profile for the ramp. One source of truth used by `derive`, the part
builders and the rules, so they cannot disagree about how long a stringer is.

A run is described in its own frame: it starts at local x = 0 on level `e0` (its height above the
ground) and rises toward +x at 1:`slope_ratio`. The WALKING SURFACE passes through the local origin,
`S(x) = x / slope_ratio`. The deck sits below the surface, the stringer below the deck:

    deck underside   D(x) = S(x) - deck_thickness / cos(theta)          (vertical offset)
    stringer bottom  B(x) = D(x) - framing_width / cos(theta)

The stringer is that band over x in [0, run], clipped so it never goes below the ground. At a run that
starts on the ground this makes a LEVEL cut at the bottom (a long, thin wedge: the first ~12" of the
ramp has no stringer under the deck) and a PLUMB cut at the top, which is why the profile is a
quadrilateral, not a plain parallelogram. A run that starts on a landing is never clipped.
"""

import math

from app.templates.geometry import Point, clip_y, extent_along, normalize_profile, r3, signed_area

# A stringer whose top (plumb) cut would be shallower than this is not worth building: the run is a
# ground-level run with the decking laid on the ground. Happens for rises under about 2.5 in.
MIN_STRINGER_END_DEPTH_IN = 1.5


def slope_angle(slope_ratio: float) -> float:
    """Angle of the walking surface in radians: atan(1 / ratio)."""
    return math.atan(1.0 / slope_ratio)


def surface_point(a: float, offset: float, slope_ratio: float) -> Point:
    """Point at slope distance `a` along the walking surface, `offset` inches above it (perpendicular)."""
    theta = slope_angle(slope_ratio)
    c, s = math.cos(theta), math.sin(theta)
    return (a * c - offset * s, a * s + offset * c)


def sloped_length(run_in: float, slope_ratio: float) -> float:
    """Length of the walking surface for a horizontal run."""
    return run_in / math.cos(slope_angle(slope_ratio))


def deck_underside(x: float, slope_ratio: float, deck_thickness_in: float) -> float:
    return x / slope_ratio - deck_thickness_in / math.cos(slope_angle(slope_ratio))


def stringer_bottom(x: float, slope_ratio: float, deck_thickness_in: float, framing_width_in: float) -> float:
    return deck_underside(x, slope_ratio, deck_thickness_in) - framing_width_in / math.cos(slope_angle(slope_ratio))


def stringer_profile(
    run_in: float,
    slope_ratio: float,
    deck_thickness_in: float,
    framing_width_in: float,
    start_elevation_in: float = 0.0,
) -> list[Point]:
    """Counter-clockwise stringer outline in the run's local XY plane (3-decimal rounded).

    Returns [] when there is nothing worth building: the band is entirely below ground, or the plumb
    cut at the top would be shallower than MIN_STRINGER_END_DEPTH_IN (a very low run).
    """
    band = [
        (0.0, stringer_bottom(0.0, slope_ratio, deck_thickness_in, framing_width_in)),
        (run_in, stringer_bottom(run_in, slope_ratio, deck_thickness_in, framing_width_in)),
        (run_in, deck_underside(run_in, slope_ratio, deck_thickness_in)),
        (0.0, deck_underside(0.0, slope_ratio, deck_thickness_in)),
    ]
    clipped = clip_y(band, -start_elevation_in)
    if len(clipped) < 3 or signed_area(clipped) <= 1e-6:
        return []
    end_ys = [y for x, y in clipped if abs(x - run_in) < 1e-6]
    if not end_ys or max(end_ys) - min(end_ys) < MIN_STRINGER_END_DEPTH_IN - 1e-9:
        return []
    return normalize_profile(clipped)


def stringer_length(
    run_in: float,
    slope_ratio: float,
    deck_thickness_in: float,
    framing_width_in: float,
    start_elevation_in: float = 0.0,
) -> float:
    """Length of board needed for one stringer: the profile's extent along the slope. 0.0 when the run
    has no stringers (see stringer_profile)."""
    theta = slope_angle(slope_ratio)
    profile = stringer_profile(run_in, slope_ratio, deck_thickness_in, framing_width_in, start_elevation_in)
    if not profile:
        return 0.0
    return r3(extent_along(profile, (math.cos(theta), math.sin(theta))))
