"""Handrails (GEO-6): 4x4 posts and a 2x4 rail on both sides of every run.

All handrail parts share the group `handrail`. They sit OUTSIDE the clear width, beside the stringers:

    posts   local z in [-W/2 - 3.5, -W/2] and [W/2, W/2 + 3.5]
    rails   local z in [-W/2 - 5, -W/2 - 3.5] and [W/2 + 3.5, W/2 + 5], fastened to the outside of the posts

Posts are at most 72 in apart measured along the slope: n = ceil(sloped length / 72) + 1, the first
and last a half post (1.75 in) in from the ends of the run. Each post is plumb, its top is at
`HANDRAIL_HEIGHT` above the walking surface measured perpendicular to it (so vertically
H / cos(theta) above the surface). The rail is a parallelogram parallel to the slope whose top edge is
that same height and whose centerline runs from post center to post center.

A rail longer than the longest 2x4 sold is cut into segments that break at posts (each break is
"centered on a post"). Because breaks must land on a post the segments are as equal as the post
spacing allows, never longer than a board that can be bought.

Landings get no handrails (a decision: the landing edges are protected by the ramp rules, not built here).
"""

import math

from app.data import lumber_spec
from app.rules.constants import HANDRAIL_HEIGHT_IN
from app.templates.geometry import PartBuilder
from app.templates.ramp import Derived, Params, Run
from app.templates.ramp_geometry import stringer_bottom, surface_point

POST_MATERIAL = "4x4_PT"
RAIL_MATERIAL = "2x4_PT"
GROUP = "handrail"
MAX_POST_SPACING_IN = 72.0


def post_centers(run: Run, post_width: float) -> list[float]:
    """Local x of each post center on a run."""
    count = math.ceil(run.sloped_in / MAX_POST_SPACING_IN - 1e-9) + 1
    first, last = post_width / 2, run.run_in - post_width / 2
    return [first + i * (last - first) / (count - 1) for i in range(count)]


def _segment_groups(interval_count: int, max_segments: int) -> list[tuple[int, int]]:
    """Split `interval_count` post-to-post intervals into `max_segments` contiguous groups (first, last+1)."""
    segments = max(1, min(max_segments, interval_count))
    base, extra = divmod(interval_count, segments)
    groups, start = [], 0
    for i in range(segments):
        size = base + (1 if i < extra else 0)
        groups.append((start, start + size))
        start += size
    return groups


def add_handrail_parts(b: PartBuilder, params: Params, derived: Derived, run: Run) -> None:
    post_spec, rail_spec = lumber_spec(POST_MATERIAL), lumber_spec(RAIL_MATERIAL)
    post_w = post_spec.width_in or 3.5
    height = HANDRAIL_HEIGHT_IN.value
    ratio = params.slope_ratio
    theta = derived.slope_angle_rad
    width = derived.clear_width_in
    xs = post_centers(run, post_w)

    def slope_distance(x: float) -> float:
        """Slope distance whose point, lifted `height - rail/2` perpendicular to the surface, is at local x."""
        return (x + (height - (rail_spec.width_in or 3.5) / 2) * math.sin(theta)) / math.cos(theta)

    intervals = len(xs) - 1
    rail_length = (xs[-1] - xs[0]) / math.cos(theta)
    max_segments = math.ceil(rail_length / rail_spec.max_stock_length_in - 1e-9)
    groups = _segment_groups(intervals, max_segments)

    with b.frame(origin=(run.x_start, run.y_start, run.z_center), flip=run.direction == -1):
        for post_z, rail_z in ((-width / 2 - post_w, -width / 2 - post_w - rail_spec.thickness_in), (width / 2, width / 2 + post_w)):
            for xp in xs:
                bottom = -run.y_start
                if run.has_stringers:
                    bottom = max(stringer_bottom(xp, ratio, derived.deck_thickness_in, derived.framing_width_in), bottom)
                top = xp / ratio + height / math.cos(theta)
                profile = [(xp - post_w / 2, bottom), (xp + post_w / 2, bottom), (xp + post_w / 2, top), (xp - post_w / 2, top)]
                b.add("Handrail post", POST_MATERIAL, profile, post_w, (0.0, 0.0, post_z), ["Square cut both ends"], GROUP)
            note = "Splice: butt joint centered on a post" if len(groups) > 1 else "Square cut both ends"
            for first, last in groups:
                a0, a1 = slope_distance(xs[first]), slope_distance(xs[last])
                lo, hi = height - (rail_spec.width_in or 3.5), height
                profile = [surface_point(a0, lo, ratio), surface_point(a1, lo, ratio), surface_point(a1, hi, ratio), surface_point(a0, hi, ratio)]
                b.add("Handrail", RAIL_MATERIAL, profile, rail_spec.thickness_in, (0.0, 0.0, rail_z), [note], GROUP)
