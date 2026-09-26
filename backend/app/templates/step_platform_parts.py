"""Step platform parts: stringers, treads and risers. See `step_platform.py` for the layout rules.

Coordinates (world, inches): x runs up the steps from the front face of the first riser, y is up from
the ground, z across the width from -width/2 to +width/2. Riser k (1..n) has its front face at
x = (k - 1) * T and spans y from (k - 1) * h to k * h. Tread k (1..n-1) sits behind riser k with its top
at y = k * h. Every part has rot (0, 0, 0).
"""

from app.data import lumber_spec
from app.models import Part
from app.templates.geometry import PartBuilder
from app.templates.step_platform import (
    STRINGER_MATERIAL,
    TREAD_GAP_IN,
    TREAD_MATERIAL,
    Derived,
    Params,
)
from app.templates.step_platform_geometry import stringer_profile
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
        profile = stringer_profile(n, h, pitch, tread_t, stringer.width_in or 0.0)
        notes = [
            f"{n - 1} notches, {format_ft_in(h)} rise by {format_ft_in(pitch)} run",
            "Level cut at the bottom, plumb cut at the top",
        ]
        # Outer stringers are flush with the side edges; the profile starts at the riser's back face.
        for z in (z0, width / 2 - stringer.thickness_in):
            builder.add("Stringer", STRINGER_MATERIAL, profile, stringer.thickness_in, pos=(riser.thickness_in, 0.0, z), cut_notes=notes, group="frame")

    for k in range(1, derived.tread_count + 1):
        for j in range(derived.tread_boards_per_tread):
            x = (k - 1) * pitch + riser.thickness_in + j * (tread_w + TREAD_GAP_IN)
            builder.add("Tread board", TREAD_MATERIAL, _rect(tread_w, tread_t), width, pos=(x, k * h - tread_t, z0), group="treads")

    riser_notes = [] if derived.riser_rip_width_in is None else [f"Rip to {format_fraction(derived.riser_rip_width_in)} in wide"]
    for k in range(1, n + 1):
        builder.add("Riser", derived.riser_material, _rect(riser.thickness_in, h), width, pos=((k - 1) * pitch, (k - 1) * h, z0), cut_notes=riser_notes, group="risers")
    return builder.parts
