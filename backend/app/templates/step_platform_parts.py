"""Step platform parts: stringers, treads, risers and the top platform. See `step_platform.py` for the layout rules.

Coordinates (world, inches): x runs up the steps from the front face of the first riser, y is up from
the ground, z across the width from -width/2 to +width/2. Riser k (1..n) has its front face at
x = (k - 1) * T and spans y from (k - 1) * h to k * h. Tread k (1..n-1) sits behind riser k with its top
at y = k * h. The top platform starts at x = (n - 1) * T + riser thickness (the top riser's back face)
and its deck top is at y = total rise. Every part has rot (0, 0, 0).
"""

from app.data import lumber_spec
from app.models import Part
from app.templates.geometry import PartBuilder
from app.templates.step_platform import (
    PLATFORM_FRAME_MATERIAL,
    PLATFORM_POST_MATERIAL,
    STRINGER_MATERIAL,
    TREAD_GAP_IN,
    TREAD_MATERIAL,
    Derived,
    Params,
)
from app.templates.step_platform_geometry import LEDGE_IN, stringer_profile
from app.util.units import format_fraction, format_ft_in


def _rect(w: float, h: float) -> list[tuple[float, float]]:
    return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]


def build_parts(params: Params, derived: Derived) -> list[Part]:
    builder = PartBuilder()
    n, h, pitch, width = derived.riser_count, derived.riser_height_in, derived.tread_depth_in, derived.width_in
    riser = lumber_spec(derived.riser_material)
    tread = lumber_spec(TREAD_MATERIAL)
    tread_w, tread_t = tread.width_in or 0.0, tread.thickness_in
    z0 = -width / 2

    if derived.has_stringers:
        stringer = lumber_spec(STRINGER_MATERIAL)
        profile = stringer_profile(n, h, pitch, tread_t, stringer.width_in or 0.0, ledge_in=0.0 if derived.has_platform else LEDGE_IN)
        notes = [
            f"{n - 1} notches, {format_ft_in(h)} rise by {format_ft_in(pitch)} run",
            "Notched, with a level cut at the bottom and a plumb cut against the platform" if derived.has_platform else "Level cut at the bottom, plumb cut at the top",
        ]
        # Outer stringers are flush with the side edges; the profile starts at the riser's back face.
        for z in (z0, width / 2 - stringer.thickness_in):
            builder.add("Stringer", STRINGER_MATERIAL, profile, stringer.thickness_in, pos=(riser.thickness_in, 0.0, z), cut_notes=notes, group="frame")

    for k in range(1, derived.tread_count + 1):
        for j in range(derived.tread_boards_per_tread):
            x = (k - 1) * pitch + riser.thickness_in + j * (tread_w + TREAD_GAP_IN)
            builder.add("Tread board", TREAD_MATERIAL, _rect(tread_w, tread_t), width, pos=(x, k * h - tread_t, z0), group="treads")

    riser_notes = [] if derived.riser_rip_width_in is None else [f"Rip to {format_fraction(derived.riser_rip_width_in)} in wide"]
    strips = derived.riser_boards_per_riser  # more than 1 only when a forced step count makes a riser very tall
    strip_h = h / strips
    for k in range(1, n + 1):
        for j in range(strips):
            builder.add("Riser", derived.riser_material, _rect(riser.thickness_in, strip_h), width, pos=((k - 1) * pitch, (k - 1) * h + j * strip_h, z0), cut_notes=riser_notes, group="risers")
    if derived.has_platform:
        _add_platform(builder, derived, x0=(n - 1) * pitch + riser.thickness_in)
    return builder.parts


def _add_platform(builder: PartBuilder, derived: Derived, x0: float) -> None:
    """The top platform: rims around the outside, joists between the end rims, 4x4 posts in the inside
    corners down to the ground, and deck boards across the width. Names match the ramp's landings, so the
    shopping list counts their joist hangers and post bases the same way."""
    frame = lumber_spec(PLATFORM_FRAME_MATERIAL)
    post = lumber_spec(PLATFORM_POST_MATERIAL)
    deck = lumber_spec(TREAD_MATERIAL)
    deck_w, deck_t = deck.width_in or 0.0, deck.thickness_in
    ft, fw = frame.thickness_in, derived.platform_frame_width_in
    depth, width = derived.platform_depth_in, derived.width_in
    z0 = -width / 2
    y_frame = derived.total_rise_in - deck_t - fw  # bottom of the rims and joists
    notes = [] if derived.platform_frame_rip_in is None else [f"Rip to {format_fraction(fw)} in wide"]

    # Side rims run front to back along the edges; end rims fit between them.
    for z in (z0, width / 2 - ft):
        builder.add("Landing rim (side)", PLATFORM_FRAME_MATERIAL, _rect(depth, fw), ft, pos=(x0, y_frame, z), cut_notes=notes, group="platform")
    for x in (x0, x0 + depth - ft):
        builder.add("Landing rim (end)", PLATFORM_FRAME_MATERIAL, _rect(ft, fw), width - 2 * ft, pos=(x, y_frame, z0 + ft), cut_notes=notes, group="platform")
    # Joists between the end rims, evenly spaced across the inside width.
    inside = width - 2 * ft
    spaces = derived.platform_joist_count + 1
    for i in range(1, spaces):
        z = z0 + ft + i * inside / spaces - ft / 2
        builder.add("Landing joist", PLATFORM_FRAME_MATERIAL, _rect(depth - 2 * ft, fw), ft, pos=(x0 + ft, y_frame, z), cut_notes=notes, group="platform")
    # Posts in the inside corners, from the ground to the underside of the deck.
    if derived.platform_post_count:
        ps = post.thickness_in
        for x in (x0 + ft, x0 + depth - ft - ps):
            for z in (z0 + ft, width / 2 - ft - ps):
                builder.add("Landing post", PLATFORM_POST_MATERIAL, _rect(ps, derived.platform_post_height_in), ps, pos=(x, 0.0, z), group="platform")
    # Deck boards across the full width, front to back with the tread gap.
    for j in range(derived.platform_deck_boards):
        builder.add("Landing deck board", TREAD_MATERIAL, _rect(deck_w, deck_t), width, pos=(x0 + j * (deck_w + TREAD_GAP_IN), derived.total_rise_in - deck_t, z0), group="platform")
