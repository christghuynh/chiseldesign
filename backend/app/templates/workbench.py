"""Workbench template (GEO-21): a plain bench with 4x4 legs, 2x4 aprons, a plywood top and an optional lower shelf.

It exists to show the engine is general (a second template next to the ramp). It is a simplified
construction model for planning, NOT an engineered design, and it has no accessibility rules
(`check_design` returns no findings for a template without a rules module).

Coordinates: inches, Y-up, origin on the FLOOR at the centre of the footprint; X is the width and Z
the depth. Parts are never rotated (rot is always (0, 0, 0)), so every part is a profile in its local XY
plane extruded along +Z. That decides how each part is expressed:

- Leg: profile 3.5 wide x leg height, extruded 3.5 (a vertical post).
- Long apron / long shelf support: profile carries the board length along X, extruded by the board's
  other dimension. Short apron: profile is the 1.5 x 3.5 cross-section, its length is the extrusion.
- Plywood top and shelf: profile = (piece width along X) x (sheet thickness), extruded by the piece depth
  along Z. The cut list drops the extent equal to the sheet thickness, so the pieces come out as
  width x depth.

Decisions where the spec was silent (all marked here, none engineered):
- Top overhang: the top overhangs the leg outer faces by TOP_OVERHANG_IN (0.75) on every side. With 0.75 the
  shortest apron (depth 12) is exactly 3.5 in, so a board's cut length is never its 3.5 in cross-section.
- Aprons are 2x4s on edge (3.5 tall), flush with the outer faces of the legs, their top touching the
  underside of the top. Long aprons run along X between the legs at the front and back; short aprons run
  along Z between the legs at each end.
- Shelf: its top surface is `shelf_height_in` (default 10) above the floor, and it must leave at least
  MIN_SHELF_CLEARANCE_IN below the aprons (otherwise ParamValidationError says the highest shelf that fits).
  It rests on two 2x4 shelf supports laid
  flat (3.5 wide, as deep as a leg) between the front legs and between the back legs. The shelf runs
  between the legs along X and from the front to the back leg faces along Z, so it needs no notches. It
  has no clearance gap to the legs (a builder trims it to fit).
- Every part must be buyable as one piece: boards no longer than the longest stock of their material,
  plywood pieces no bigger than a 48 x 96 sheet. Otherwise `generate_parts` raises ParamValidationError.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from app.cutlist import part_length, sheet_piece_dims
from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.models import Part, SkeletonStep
from app.templates.geometry import PartBuilder
from app.util.units import format_fraction, format_ft_in

KEY = "workbench"
NAME = "Workbench"
DESCRIPTION = "Workbench with 4x4 legs, 2x4 aprons, a plywood top and an optional lower shelf."

LEG_MATERIAL = "4x4_PT"
BOARD_MATERIAL = "2x4_PT"
SHEET_MATERIAL = "3/4_ext_ply"

TOP_OVERHANG_IN = 0.75  # placeholder, to verify: top overhang past the outer faces of the legs
SHELF_HEIGHT_IN = 10.0  # default floor-to-shelf-top height (placeholder, to verify)
MIN_SHELF_CLEARANCE_IN = 6.0  # room left between the shelf and the aprons, so it can still hold something

_LEG_IN = lumber_spec(LEG_MATERIAL).width_in or 3.5  # 4x4 actual size
_APRON_THICK_IN = lumber_spec(BOARD_MATERIAL).thickness_in  # 1.5
_APRON_WIDE_IN = lumber_spec(BOARD_MATERIAL).width_in or 3.5  # 3.5
_PLY_IN = lumber_spec(SHEET_MATERIAL).thickness_in  # 0.703


class Params(BaseModel):
    """Workbench parameters. All bounds are inferred (the spec gave sizes, not limits): the width and depth
    stop at one 48 x 96 in plywood sheet because the top is a single piece.

    Schema hints for the parameter panel (in `json_schema_extra`), as on the ramp: `group` is "key" for the
    overall size a homeowner decides and "advanced" for construction choices, which the panel folds away;
    `unit` is the unit of a number.
    """

    model_config = ConfigDict(extra="forbid")

    width_in: float = Field(48, ge=24, le=96, title="Width", description="Length of the top from left to right, edge to edge. The top is one piece of plywood, so it can be at most 96 in (the long side of a sheet).", json_schema_extra={"unit": "in", "group": "key"})
    depth_in: float = Field(24, ge=12, le=48, title="Depth", description="Size of the top from front to back, edge to edge. It can be at most 48 in (the short side of a plywood sheet).", json_schema_extra={"unit": "in", "group": "key"})
    height_in: float = Field(34, ge=24, le=48, title="Working-surface height", description="From the floor to the top of the work surface, measured straight up.", json_schema_extra={"unit": "in", "group": "key"})
    lower_shelf: bool = Field(True, title="Lower shelf", description="A plywood shelf between the legs, resting on 2x4 supports.", json_schema_extra={"group": "advanced"})
    shelf_height_in: float = Field(SHELF_HEIGHT_IN, ge=4, le=36, title="Shelf height", description="From the floor to the top of the lower shelf. It has to stay at least 6 in below the frame under the top.", json_schema_extra={"unit": "in", "group": "advanced"})


@dataclass(frozen=True)
class Derived:
    width_in: float
    depth_in: float
    height_in: float
    has_shelf: bool
    top_thickness_in: float
    leg_height_in: float  # full height minus the top thickness
    leg_size_in: float
    leg_x_min: float  # outer x face of the left legs
    leg_x_max: float  # outer x face of the right legs
    leg_z_min: float  # outer z face of the front legs
    leg_z_max: float
    apron_top_y: float  # underside of the top
    apron_bottom_y: float
    long_apron_length_in: float
    short_apron_length_in: float
    shelf_top_y: float
    shelf_support_y: float  # bottom of the shelf supports
    shelf_width_in: float  # along X
    shelf_depth_in: float  # along Z
    shelf_clearance_in: float  # top of the shelf up to the bottom of the aprons (0.0 without a shelf)
    leg_count: int
    top_overhang_in: float  # top edge past the outer faces of the legs, on every side
    sheet_width_in: float  # plywood sheet the top is cut from
    sheet_length_in: float
    top_sheet_fraction: float  # share of one sheet's area the top uses

    @property
    def footprint_x(self) -> tuple[float, float]:
        return (-self.width_in / 2, self.width_in / 2)

    @property
    def footprint_z(self) -> tuple[float, float]:
        return (-self.depth_in / 2, self.depth_in / 2)


def derive(params: Params) -> Derived:
    w, d, h = params.width_in, params.depth_in, params.height_in
    leg_x_min, leg_x_max = -w / 2 + TOP_OVERHANG_IN, w / 2 - TOP_OVERHANG_IN
    leg_z_min, leg_z_max = -d / 2 + TOP_OVERHANG_IN, d / 2 - TOP_OVERHANG_IN
    between_x = leg_x_max - leg_x_min - 2 * _LEG_IN
    between_z = leg_z_max - leg_z_min - 2 * _LEG_IN
    top_underside = h - _PLY_IN
    shelf = params.shelf_height_in
    highest = top_underside - _APRON_WIDE_IN - MIN_SHELF_CLEARANCE_IN
    if params.lower_shelf and shelf > highest + 1e-9:
        raise ParamValidationError(
            f"A shelf {format_fraction(shelf)} in off the floor is too close to the top of a {format_fraction(h)} in bench. "
            f"The highest shelf that fits is {format_fraction(highest)} in."
        )
    shelf_bottom = shelf - _PLY_IN
    sheet_w, sheet_l = lumber_spec(SHEET_MATERIAL).sheet_size_in or (48.0, 96.0)
    return Derived(
        width_in=w,
        depth_in=d,
        height_in=h,
        has_shelf=params.lower_shelf,
        top_thickness_in=_PLY_IN,
        leg_height_in=top_underside,
        leg_size_in=_LEG_IN,
        leg_x_min=leg_x_min,
        leg_x_max=leg_x_max,
        leg_z_min=leg_z_min,
        leg_z_max=leg_z_max,
        apron_top_y=top_underside,
        apron_bottom_y=top_underside - _APRON_WIDE_IN,
        long_apron_length_in=between_x,
        short_apron_length_in=between_z,
        shelf_top_y=shelf,
        shelf_support_y=shelf_bottom - _APRON_THICK_IN,
        shelf_width_in=between_x,
        shelf_depth_in=leg_z_max - leg_z_min,
        shelf_clearance_in=top_underside - _APRON_WIDE_IN - shelf if params.lower_shelf else 0.0,
        leg_count=4,
        top_overhang_in=TOP_OVERHANG_IN,
        sheet_width_in=sheet_w,
        sheet_length_in=sheet_l,
        top_sheet_fraction=(w * d) / (sheet_w * sheet_l),
    )


def _in(inches: float) -> str:
    return f'{format_fraction(inches)}"'


def _size(width_in: float, depth_in: float) -> str:
    return f"{format_ft_in(width_in)} × {format_ft_in(depth_in)}"


def summarize(params: Params, derived: Derived) -> list[dict[str, str]]:
    """The numbers a builder wants at a glance, as display text (`label`, `value`, optional `detail`).

    Optional template hook: the engine stores the result on the spec as `meta["summary"]`. Every value
    is formatted here from `derive`, so the UI only displays text and computes nothing.
    """
    d = derived
    sheet = f"{format_ft_in(d.sheet_width_in)} × {format_ft_in(d.sheet_length_in)} sheet of {lumber_spec(SHEET_MATERIAL).description}"
    if d.top_sheet_fraction >= 1 - 1e-9:
        top_from = f"cut from a whole {sheet}"
    else:
        top_from = f"cut from {min(99, max(1, round(d.top_sheet_fraction * 100)))}% of one {sheet}"
    facts: list[dict[str, str]] = [
        {"label": "Top", "value": f"{_size(d.width_in, d.depth_in)} (width × depth)", "detail": top_from},
        {"label": "Working height", "value": format_ft_in(d.height_in), "detail": "floor to the top of the work surface"},
        {"label": "Legs", "value": f"{d.leg_count} × {lumber_spec(LEG_MATERIAL).description}", "detail": f"each {format_ft_in(d.leg_height_in)} long"},
    ]
    if d.has_shelf:
        facts.append({"label": "Lower shelf", "value": f"{_in(d.shelf_top_y)} off the floor", "detail": "floor to the top of the shelf"})
        facts.append({"label": "Clear space under the top", "value": format_ft_in(d.shelf_clearance_in), "detail": "from the shelf up to the bottom of the aprons"})
    else:
        facts.append({"label": "Lower shelf", "value": "None"})
    facts.append({"label": "Footprint", "value": _size(d.width_in, d.depth_in), "detail": f"the top overhangs the legs by {_in(d.top_overhang_in)} on every side"})
    return facts


def _rect(w: float, h: float) -> list[tuple[float, float]]:
    return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]


def _build(derived: Derived) -> list[Part]:
    d = derived
    b = PartBuilder()
    leg = d.leg_size_in
    xs = (d.leg_x_min, d.leg_x_max - leg)  # left, right leg
    zs = (d.leg_z_min, d.leg_z_max - leg)  # front, back leg

    for z in zs:
        for x in xs:
            b.add("Leg", LEG_MATERIAL, _rect(leg, d.leg_height_in), leg, pos=(x, 0.0, z), group="legs")

    for z in (d.leg_z_min, d.leg_z_max - _APRON_THICK_IN):
        b.add("Apron (long)", BOARD_MATERIAL, _rect(d.long_apron_length_in, _APRON_WIDE_IN), _APRON_THICK_IN,
              pos=(xs[0] + leg, d.apron_bottom_y, z), group="aprons")
    for x in (d.leg_x_min, d.leg_x_max - _APRON_THICK_IN):
        b.add("Apron (short)", BOARD_MATERIAL, _rect(_APRON_THICK_IN, _APRON_WIDE_IN), d.short_apron_length_in,
              pos=(x, d.apron_bottom_y, zs[0] + leg), group="aprons")

    b.add("Top", SHEET_MATERIAL, _rect(d.width_in, _PLY_IN), d.depth_in,
          pos=(-d.width_in / 2, d.apron_top_y, -d.depth_in / 2), group="top")

    if d.has_shelf:
        for z in zs:  # flat, as deep as a leg, so the shelf rests on the full width
            b.add("Shelf support", BOARD_MATERIAL, _rect(d.long_apron_length_in, _APRON_THICK_IN), _APRON_WIDE_IN,
                  pos=(xs[0] + leg, d.shelf_support_y, z), group="shelf")
        b.add("Lower shelf", SHEET_MATERIAL, _rect(d.shelf_width_in, _PLY_IN), d.shelf_depth_in,
              pos=(xs[0] + leg, d.shelf_top_y - _PLY_IN, d.leg_z_min), group="shelf")
    return b.parts


def _ensure_fits_stock(parts: list[Part]) -> None:
    problems: list[str] = []
    for part in parts:
        spec = lumber_spec(part.material)
        if spec.kind == "sheet":
            width, length = spec.sheet_size_in or (0.0, 0.0)
            big, small = sheet_piece_dims(part)
            if big > max(width, length) + 1e-6 or small > min(width, length) + 1e-6:
                problems.append(f"{part.name} is {big:g} x {small:g} in, larger than a {width:g} x {length:g} in sheet")
        elif part_length(part) > spec.max_stock_length_in + 1e-6:
            problems.append(f"{part.name} needs a {part_length(part):g} in board but {part.material} is sold up to {spec.max_stock_length_in:g} in")
    if problems:
        raise ParamValidationError("The workbench cannot be built from stock lumber: " + "; ".join(dict.fromkeys(problems)))


def generate_parts(params: Params) -> list[Part]:
    parts = _build(derive(params))
    _ensure_fits_stock(parts)
    return parts


def _labels(parts: list[Part], *names: str) -> list[str]:
    return sorted({p.label for p in parts if p.name in names})


def build_skeleton(params: Params, parts: list[Part]) -> list[SkeletonStep]:
    boards = _labels(parts, "Leg", "Apron (long)", "Apron (short)", "Shelf support")
    plywood = _labels(parts, "Top", "Lower shelf")
    frame = _labels(parts, "Leg", "Apron (long)", "Apron (short)")
    shelf = _labels(parts, "Shelf support", "Lower shelf") if params.lower_shelf else []
    top = _labels(parts, "Top")
    steps = [
        SkeletonStep(phase="cut", title="Cut the legs, aprons and shelf supports to length" if params.lower_shelf else "Cut the legs and aprons to length", part_labels=boards, action_key="cut_boards"),
        SkeletonStep(phase="cut", title="Cut the plywood top and shelf" if params.lower_shelf else "Cut the plywood top", part_labels=plywood, action_key="cut_plywood"),
        SkeletonStep(phase="assemble", title="Assemble the legs and aprons into the frame", part_labels=frame, action_key="assemble_frame"),
        SkeletonStep(phase="assemble", title="Attach the shelf supports and the lower shelf", part_labels=shelf, action_key="attach_shelf"),
        SkeletonStep(phase="install", title="Attach the top to the frame", part_labels=top, action_key="attach_top"),
    ]
    steps = [s for s in steps if s.part_labels]
    steps.append(SkeletonStep(phase="check", title="Check the bench is level and does not rock", part_labels=[], action_key="final_check"))
    return steps
