"""Landing parts (GEO-5): a free-standing platform between two runs.

A landing is built in WORLD coordinates. Its footprint is x in [x_min, x_max], z in [z_min, z_max]
and its walking surface is at `elevation_in` (E). With deck thickness d the frame top is E - d and the
frame is `h = min(framing width, E - d)` deep, so it never reaches below the ground.

    Landing rim (end)     across Z at both X ends, full landing width
    Landing rim (side)    along X between the end rims, on both Z edges
    Landing joist         across Z every `stringer_spacing_in` from the low-x end, while clear of the far end rim
    Landing deck board    boards run ALONG X, laid across the landing width (same sliver-avoiding rule as runs)
    Landing deck panel    plywood tiled into pieces of at most 96 x 48 in
    Landing post          4x4 corner posts from the ground up to the frame bottom (none if the frame is on the ground)
    Edge curb             2x6 on edge along every open edge of the deck (only when `edge_curb` is on)

Decisions: no handrails on landings. Curbs go on the open edges only: both long sides, and on a switchback
turn landing also the far end and the 12 in gap between the two runs (a straight ramp's landing is
entered from one run and left by the next, so its two ends are not edges). Pieces longer than the longest board sold (a very
long landing) are cut into equal lengths with a butt joint, so every part can be bought.
"""

import math

from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.templates.geometry import PartBuilder
from app.templates.ramp import Derived, Landing, Params
from app.templates.ramp_boards import CURB_MATERIAL, curb_spec, equal_pieces, layout_boards
from app.util.units import format_fraction

MIN_FRAME_DEPTH_IN = 1.5
POST_MATERIAL = "4x4_PT"
PLYWOOD = "3/4_ext_ply"
MAX_PANEL_LENGTH_IN = 96.0
MAX_PANEL_WIDTH_IN = 48.0
_MIN_POST_HEIGHT_IN = 0.05


def landing_group(landing: Landing) -> str:
    return f"landing_{landing.index + 1}"


def frame_bottom(landing: Landing, derived: Derived) -> float:
    """Underside of the landing frame; raises when the landing is too low to have a frame at all."""
    top = landing.elevation_in - derived.deck_thickness_in
    depth = min(derived.framing_width_in, top)
    if depth < MIN_FRAME_DEPTH_IN - 1e-9:
        needed = math.ceil((MIN_FRAME_DEPTH_IN + derived.deck_thickness_in) * 10 - 1e-9) / 10
        raise ParamValidationError(f"The rise is too small for a switchback: each landing needs at least {needed:.1f} in of height.")
    return top - depth


def _splice_notes(segments: int, base: str = "Square cut both ends") -> list[str]:
    return ["Splice: butt joint"] if segments > 1 else [base]


def add_landing_parts(b: PartBuilder, params: Params, derived: Derived, landing: Landing) -> None:
    group = landing_group(landing)
    t = derived.framing_thickness_in
    x0, x1, z0, z1 = landing.x_min, landing.x_max, landing.z_min, landing.z_max
    width = z1 - z0
    top = landing.elevation_in - derived.deck_thickness_in
    bottom = frame_bottom(landing, derived)
    framing = params.framing
    max_frame = derived.max_stock_length_in
    # A low landing has less height than a full board is wide, so the frame lumber is ripped down to fit.
    depth = top - bottom
    rip = [f"Rip to {format_fraction(depth)} in wide"] if depth < derived.framing_width_in - 1e-6 else []

    for x in (x0, x1 - t):
        b.add("Landing rim (end)", framing, [(x, bottom), (x + t, bottom), (x + t, top), (x, top)], width, (0.0, 0.0, z0), ["Square cut both ends", *rip], group)

    inner = (x0 + t, x1 - t)
    pieces = equal_pieces(inner[1] - inner[0], max_frame)
    for z in (z0, z1 - t):
        for start, end in pieces:
            s, e = inner[0] + start, inner[0] + end
            b.add("Landing rim (side)", framing, [(s, bottom), (e, bottom), (e, top), (s, top)], t, (0.0, 0.0, z), [*_splice_notes(len(pieces)), *rip], group)

    k = 1
    while True:
        center = x0 + k * params.stringer_spacing_in
        if center + t / 2 >= x1 - t - 1e-9:  # would touch or overlap the far end rim
            break
        profile = [(center - t / 2, bottom), (center + t / 2, bottom), (center + t / 2, top), (center - t / 2, top)]
        b.add("Landing joist", framing, profile, width - 2 * t, (0.0, 0.0, z0 + t), ["Square cut both ends", *rip], group)
        k += 1

    _add_decking(b, params, derived, landing, top)
    if params.edge_curb:
        _add_curbs(b, derived, landing)

    post = lumber_spec(POST_MATERIAL).width_in or 3.5
    if bottom > _MIN_POST_HEIGHT_IN:
        for x in (x0, x1 - post):
            for z in (z0, z1 - post):
                b.add("Landing post", POST_MATERIAL, [(x, 0.0), (x + post, 0.0), (x + post, bottom), (x, bottom)], post, (0.0, 0.0, z), ["Square cut both ends"], group)


def _add_decking(b: PartBuilder, params: Params, derived: Derived, landing: Landing, top: float) -> None:
    group = landing_group(landing)
    x0, x1, z0, z1 = landing.x_min, landing.x_max, landing.z_min, landing.z_max
    if params.decking == PLYWOOD:
        columns = equal_pieces(z1 - z0, MAX_PANEL_WIDTH_IN)
        for start, end in equal_pieces(x1 - x0, MAX_PANEL_LENGTH_IN, params.deck_gap_in):
            for c0, c1 in columns:
                profile = [(x0 + start, top), (x0 + end, top), (x0 + end, landing.elevation_in), (x0 + start, landing.elevation_in)]
                b.add("Landing deck panel", params.decking, profile, c1 - c0, (0.0, 0.0, z0 + c0), [], group)
        return
    spec = lumber_spec(params.decking)
    lengths = equal_pieces(x1 - x0, spec.max_stock_length_in)
    notes = _splice_notes(len(lengths), base="")
    for span in layout_boards(z1 - z0, spec.width_in or 5.5, params.deck_gap_in):
        for start, end in lengths:
            profile = [(x0 + start, top), (x0 + end, top), (x0 + end, landing.elevation_in), (x0 + start, landing.elevation_in)]
            board_notes = [n for n in notes if n]
            if span.ripped:
                board_notes.insert(0, f"Rip to {format_fraction(span.width)} in wide")
            b.add("Landing deck board", params.decking, profile, span.width, (0.0, 0.0, z0 + span.start), board_notes, group)


def _add_curbs(b: PartBuilder, derived: Derived, landing: Landing) -> None:
    """Edge curbs (ADA 405.9) stand on the deck surface along every open edge of the landing."""
    group = landing_group(landing)
    spec = curb_spec()
    assert spec.width_in is not None
    t, h = spec.thickness_in, spec.width_in
    x0, x1, z0, z1 = landing.x_min, landing.x_max, landing.z_min, landing.z_max
    top = landing.elevation_in

    # The curb on the run that leaves this landing has a slanted end (its ends are square to the slope, so its
    # top leans back over the landing by h * tan(angle)). The landing curb is cut to the same slant so the two
    # meet without overlapping.
    lean = h * math.tan(derived.slope_angle_rad)
    following = derived.runs[landing.index + 1] if landing.index + 1 < len(derived.runs) else None
    slant_at_max = following is not None and abs(following.x_start - x1) < abs(following.x_start - x0)

    def along_x(z: float) -> None:
        pieces = equal_pieces(x1 - x0, spec.max_stock_length_in)
        for i, (start, end) in enumerate(pieces):
            notes = _splice_notes(len(pieces))
            top_start, top_end = x0 + start, x0 + end
            if following is not None and slant_at_max and i == len(pieces) - 1:
                top_end -= lean
                notes = [*notes, "Bevel the top end to match the run curb"]
            elif following is not None and not slant_at_max and i == 0:
                top_start += lean
                notes = [*notes, "Bevel the top end to match the run curb"]
            profile = [(x0 + start, top), (x0 + end, top), (top_end, top + h), (top_start, top + h)]
            b.add("Edge curb", CURB_MATERIAL, profile, t, (0.0, 0.0, z), notes, group)

    def across_z(x: float, za: float, zb: float) -> None:
        pieces = equal_pieces(zb - za, spec.max_stock_length_in)
        for start, end in pieces:
            profile = [(x, top), (x + t, top), (x + t, top + h), (x, top + h)]
            b.add("Edge curb", CURB_MATERIAL, profile, end - start, (0.0, 0.0, za + start), _splice_notes(len(pieces)), group)

    along_x(z0)
    along_x(z1 - t)
    if landing.kind == "turn":
        # The run arrives at one X end and the next run leaves from the same end, so that end is open only
        # across the gap between them; the opposite end is open across the whole landing.
        run, following = derived.runs[landing.index], derived.runs[landing.index + 1]
        far_is_max = run.direction == 1
        far_x = x1 - t if far_is_max else x0
        across_z(far_x, z0 + t, z1 - t)
        gap_a, gap_b = run.z_center + derived.clear_width_in / 2, following.z_center - derived.clear_width_in / 2
        across_z(x0 if far_is_max else x1 - t, gap_a, gap_b)
