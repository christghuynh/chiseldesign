"""Ramp parts: `build_parts(params, derived)` turns the derived layout into 3D parts.

Every run is built in its own frame (`PartBuilder.frame`): local x runs from 0 (bottom of the run) to
`run_in` (top), local y is relative to the run's start elevation and local z is relative to the run's
centerline. See `ramp_geometry` for the slope math. Part order is deterministic: for each run its
stringers, ledger, decking and curbs, then each landing (`ramp_landings`), then the handrails
(`ramp_handrails`).

Part names and groups are a contract shared with the cut list, pricing and skeleton code:

    Stringer, Ledger, Deck board, Deck panel, Edge curb                     group run_1, run_2, ...
    Landing rim (end), Landing rim (side), Landing joist,
    Landing deck board, Landing deck panel, Landing post                    group landing_1, ...
    Handrail post, Handrail                                                 group handrail

Decisions worth knowing:
- Decking, curbs and handrails are only built on runs; landings get no curbs and no handrails (they
  are flat and the rules module reports open edges separately).
- The one ledger sits on the LAST run, where the ramp meets the porch. A switchback's turn landing
  needs none because the landing frame is free-standing on its posts.
- A run whose stringers would be too shallow (a very low ramp) has none: its decking lies on the ground.
- The deck layout avoids sliver boards (`ramp_boards.layout_boards` documents the rule).
"""

from app.data import lumber_spec
from app.models import Part
from app.templates.geometry import PartBuilder, Point, clip_y, normalize_profile, signed_area
from app.templates.ramp import Derived, Params, Run
from app.templates.ramp_boards import equal_pieces, layout_boards
from app.templates.ramp_geometry import deck_underside, stringer_bottom, stringer_profile, surface_point
from app.util.units import format_fraction

CURB_MATERIAL = "2x4_PT"
PLYWOOD = "3/4_ext_ply"
MAX_PANEL_LENGTH_IN = 96.0
MAX_PANEL_WIDTH_IN = 48.0
_GRADE_TOL = 1e-6


def run_group(run: Run) -> str:
    return f"run_{run.index + 1}"


def usable_profile(poly: list[Point]) -> bool:
    """True when `poly` survives rounding as a real (non-degenerate) polygon."""
    try:
        normalize_profile(poly)
    except ValueError:
        return False
    return signed_area(poly) > 1e-3


def _add_stringers(b: PartBuilder, params: Params, derived: Derived, run: Run) -> None:
    profile = stringer_profile(run.run_in, params.slope_ratio, derived.deck_thickness_in, derived.framing_width_in, run.y_start)
    if not profile:
        return
    theta = derived.slope_angle_deg
    grounded = stringer_bottom(0.0, params.slope_ratio, derived.deck_thickness_in, derived.framing_width_in) < -run.y_start - _GRADE_TOL
    if grounded:
        notes = [f"{90 - theta:.1f}° level cut at bottom end (sits on grade)", f"{theta:.1f}° plumb cut at top end"]
    else:
        notes = [f"{theta:.1f}° plumb cut at both ends"]
    t, width, count = derived.framing_thickness_in, derived.clear_width_in, derived.stringer_count
    for i in range(count):
        z = -width / 2 + i * (width - t) / (count - 1) if count > 1 else -t / 2
        b.add("Stringer", params.framing, profile, t, (0.0, 0.0, z), notes, run_group(run))


def _add_ledger(b: PartBuilder, params: Params, derived: Derived, run: Run) -> None:
    """The ledger fastens to the porch face at the top of the last run, just past the stringer ends."""
    t = derived.framing_thickness_in
    top = deck_underside(run.run_in, params.slope_ratio, derived.deck_thickness_in)
    bottom = max(top - derived.framing_width_in, -run.y_start)  # a ledger never goes below grade
    notes = ["Square cut both ends"]
    if top - bottom < derived.framing_width_in - 1e-6:
        notes.append(f"Rip to {format_fraction(top - bottom)} in wide")
    profile = [(run.run_in, bottom), (run.run_in + t, bottom), (run.run_in + t, top), (run.run_in, top)]
    b.add("Ledger", params.framing, profile, derived.clear_width_in, (0.0, 0.0, -derived.clear_width_in / 2), notes, run_group(run))


def _clip_note(poly: list[Point], run: Run) -> tuple[list[Point], list[str]]:
    clipped = clip_y(poly, -run.y_start)
    was_clipped = any(y < -run.y_start - _GRADE_TOL for _, y in poly)
    return clipped, (["Bevel bottom edge to sit on grade"] if was_clipped else [])


def _add_deck_boards(b: PartBuilder, params: Params, derived: Derived, run: Run) -> None:
    spec = lumber_spec(params.decking)
    t, width = spec.thickness_in, derived.clear_width_in
    for span in layout_boards(run.sloped_in, spec.width_in or 5.5, params.deck_gap_in):
        poly = [
            surface_point(span.start, -t, params.slope_ratio),
            surface_point(span.end, -t, params.slope_ratio),
            surface_point(span.end, 0.0, params.slope_ratio),
            surface_point(span.start, 0.0, params.slope_ratio),
        ]
        poly, notes = _clip_note(poly, run)
        if not usable_profile(poly):
            continue
        if span.ripped:
            notes = [f"Rip to {format_fraction(span.width)} in wide", *notes]
        b.add("Deck board", params.decking, poly, width, (0.0, 0.0, -width / 2), notes, run_group(run))


def _add_deck_panels(b: PartBuilder, params: Params, derived: Derived, run: Run) -> None:
    t, width = lumber_spec(PLYWOOD).thickness_in, derived.clear_width_in
    if width <= MAX_PANEL_WIDTH_IN:
        columns = [(-width / 2, width)]
    else:
        columns = [(-width / 2, width / 2), (0.0, width / 2)]
    for start, end in equal_pieces(run.sloped_in, MAX_PANEL_LENGTH_IN, params.deck_gap_in):
        poly = [
            surface_point(start, -t, params.slope_ratio),
            surface_point(end, -t, params.slope_ratio),
            surface_point(end, 0.0, params.slope_ratio),
            surface_point(start, 0.0, params.slope_ratio),
        ]
        poly, notes = _clip_note(poly, run)
        if not usable_profile(poly):
            continue
        for z, panel_width in columns:
            b.add("Deck panel", params.decking, poly, panel_width, (0.0, 0.0, z), notes, run_group(run))


def _add_curbs(b: PartBuilder, params: Params, derived: Derived, run: Run) -> None:
    """2x4 curbs stand on the deck surface along both edges, spliced when longer than the longest 2x4."""
    spec = lumber_spec(CURB_MATERIAL)
    assert spec.width_in is not None
    segments = equal_pieces(run.sloped_in, spec.max_stock_length_in)
    note = "Splice: butt joint over a stringer" if len(segments) > 1 else "Square cut both ends"
    width = derived.clear_width_in
    for start, end in segments:
        poly = [
            surface_point(start, 0.0, params.slope_ratio),
            surface_point(end, 0.0, params.slope_ratio),
            surface_point(end, spec.width_in, params.slope_ratio),
            surface_point(start, spec.width_in, params.slope_ratio),
        ]
        for z in (-width / 2, width / 2 - spec.thickness_in):
            b.add("Edge curb", CURB_MATERIAL, poly, spec.thickness_in, (0.0, 0.0, z), [note], run_group(run))


def add_run_parts(b: PartBuilder, params: Params, derived: Derived, run: Run, is_last: bool) -> None:
    with b.frame(origin=(run.x_start, run.y_start, run.z_center), flip=run.direction == -1):
        if run.has_stringers:
            _add_stringers(b, params, derived, run)
            if is_last:
                _add_ledger(b, params, derived, run)
        if params.decking == PLYWOOD:
            _add_deck_panels(b, params, derived, run)
        else:
            _add_deck_boards(b, params, derived, run)
        if params.edge_curb:
            _add_curbs(b, params, derived, run)


def build_parts(params: Params, derived: Derived) -> list[Part]:
    b = PartBuilder()
    for run in derived.runs:
        add_run_parts(b, params, derived, run, is_last=run.index == len(derived.runs) - 1)
    return b.parts
