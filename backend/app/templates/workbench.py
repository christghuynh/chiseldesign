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
- Shelf: its top surface is SHELF_HEIGHT_IN (10) above the floor. It rests on two 2x4 shelf supports laid
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

KEY = "workbench"
NAME = "Workbench"
DESCRIPTION = "Workbench with 4x4 legs, 2x4 aprons, a plywood top and an optional lower shelf."

LEG_MATERIAL = "4x4_PT"
BOARD_MATERIAL = "2x4_PT"
SHEET_MATERIAL = "3/4_ext_ply"

TOP_OVERHANG_IN = 0.75  # placeholder, to verify: top overhang past the outer faces of the legs
SHELF_HEIGHT_IN = 10.0  # placeholder, to verify: floor to the top surface of the lower shelf

_LEG_IN = lumber_spec(LEG_MATERIAL).width_in or 3.5  # 4x4 actual size
_APRON_THICK_IN = lumber_spec(BOARD_MATERIAL).thickness_in  # 1.5
_APRON_WIDE_IN = lumber_spec(BOARD_MATERIAL).width_in or 3.5  # 3.5
_PLY_IN = lumber_spec(SHEET_MATERIAL).thickness_in  # 0.703


class Params(BaseModel):
    """Workbench parameters. All bounds are inferred (the spec gave sizes, not limits)."""

    model_config = ConfigDict(extra="forbid")

    width_in: float = Field(48, ge=24, le=96, title="Width (in)", description="Left to right; up to one 8 ft sheet (bounds inferred)", json_schema_extra={"unit": "in"})
    depth_in: float = Field(24, ge=12, le=48, title="Depth (in)", description="Front to back; up to the 4 ft sheet width (bounds inferred)", json_schema_extra={"unit": "in"})
    height_in: float = Field(34, ge=24, le=48, title="Height (in)", description="Floor to the top surface (bounds inferred)", json_schema_extra={"unit": "in"})
    lower_shelf: bool = Field(True, title="Lower shelf", description="Plywood shelf on 2x4 supports between the legs")


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
    shelf_bottom = SHELF_HEIGHT_IN - _PLY_IN
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
        shelf_top_y=SHELF_HEIGHT_IN,
        shelf_support_y=shelf_bottom - _APRON_THICK_IN,
        shelf_width_in=between_x,
        shelf_depth_in=leg_z_max - leg_z_min,
    )


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
