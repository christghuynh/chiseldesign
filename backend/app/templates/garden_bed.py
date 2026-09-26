"""Raised garden bed template (GEO-19): params, derived layout, parts and build outline.

Implements the template interface described in `ramp.py`. The geometry is a simplified construction
model for planning, NOT an engineered design.

Frame: inches, Y-up. The origin is on the GROUND at the CENTER of the bed footprint; X runs along the
bed length, Z across its width. Nothing rotates (a Part is a profile in local XY extruded along +Z), so:
- boards whose length runs along X (long courses, long cap boards) carry the length in the profile;
- boards whose length runs along Z (end courses, end cap boards) carry it in `thickness` (the depth);
- posts are vertical, so their height is in the profile and the 3.5 in cross-section depth in `thickness`.

Layout decisions made here (the brief left them open):
- The four 4x4 corner posts stand in the corners; long courses butt between them on the front and
  back, short courses butt between them on the ends. All boards are flush with the OUTER faces, so the
  outer footprint is exactly `length_in x width_in` and the inner (soil) footprint is smaller by twice
  the board thickness in each direction.
- The cap rail (when present) is four 2x6 boards laid flat on top, flush with the outer faces and
  reaching inward; the long boards run the full length and the end boards fit between them. It sits ON
  TOP of the posts and courses and its thickness counts inside `height_in`, so the posts (and the
  course stack) are `height_in - 1.5` tall with a cap and `height_in` without.
- Course count is `ceil(course_height / board_width)`. The LAST (top) course is ripped when the height
  is not a multiple of the board width; only that one course is ripped. A very thin rip (a strip a
  few tenths of an inch wide) is legal but impractical; the spec prescribes ceil, so it is kept.
- `access` does not change the geometry; it only selects the reach limit used by the rules.
- The cut list infers a board's length as the longest of its three extents. For an end course or end
  cap board shorter than its own cross-section (only very narrow beds) that would be wrong, so such
  parts get a "Cut to <length> in long" note; the note also keeps them off the label of longer boards.
- `width_in` 12..48 and `height_in` 12..48 are inferred bounds; `length_in` 24..144 is capped by
  the longest 2x10 sold (144 in) so the long sides are single boards.
"""

import math
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.models import Part, SkeletonStep
from app.templates.geometry import PartBuilder
from app.util.units import format_fraction, format_ft_in

KEY = "garden_bed"
NAME = "Raised garden bed"
DESCRIPTION = "Raised garden bed with stacked side boards, corner posts and an optional seat-height cap rail."

POST_MATERIAL = "4x4_PT"
CAP_MATERIAL = "2x6_PT"

Access = Literal["one_side", "both_sides"]
BoardKey = Literal["2x10_PT", "2x8_PT"]


class Params(BaseModel):
    """Garden bed parameters. Bounds not stated in the original spec are marked (inferred)."""

    model_config = ConfigDict(extra="forbid")

    length_in: float = Field(72, ge=24, le=144, title="Length (in)", description="Outer length; 144 in is the longest 2x10 sold, so long sides stay single boards (bounds inferred)", json_schema_extra={"unit": "in"})
    width_in: float = Field(24, ge=12, le=48, title="Width (in)", description="Outer width (bounds inferred)", json_schema_extra={"unit": "in"})
    height_in: float = Field(30, ge=12, le=48, title="Height (in)", description="Overall height including the cap rail (bounds inferred)", json_schema_extra={"unit": "in"})
    access: Access = Field("one_side", title="Access", description="one_side when the bed sits against a wall, both_sides when you can reach it from both long sides")
    board: BoardKey = Field("2x10_PT", title="Side board", description="Lumber for the stacked side courses")
    cap_rail: bool = Field(True, title="Cap rail", description="2x6 rail around the top that doubles as a seat or armrest")


@dataclass(frozen=True)
class Derived:
    length_in: float
    width_in: float
    height_in: float
    access: Access
    board: str
    cap_rail: bool
    board_width_in: float
    board_thickness_in: float  # also the wall thickness
    post_size_in: float
    cap_width_in: float
    cap_thickness_in: float  # 0.0 without a cap rail
    course_height_in: float  # height_in minus the cap rail: the height the courses and posts cover
    course_count: int
    course_widths_in: tuple[float, ...]  # bottom to top; the last is the ripped one when there is one
    ripped_width_in: float | None
    post_height_in: float
    inner_length_in: float
    inner_width_in: float
    long_board_length_in: float  # side course on the front/back, between the posts
    end_board_length_in: float  # side course on the ends, between the posts
    cap_long_length_in: float
    cap_end_length_in: float

    @property
    def outer_length_in(self) -> float:
        return self.length_in

    @property
    def outer_width_in(self) -> float:
        return self.width_in

    @property
    def ripped_course_count(self) -> int:
        return 0 if self.ripped_width_in is None else 1


def _check_fits_stock(material: str, name: str, length_in: float) -> None:
    longest = lumber_spec(material).max_stock_length_in
    if length_in > longest + 1e-9:
        raise ParamValidationError(
            f"The {name} would need a {format_ft_in(length_in)} board, but the longest {material} sold is {format_ft_in(longest)}. Make the bed shorter."
        )


def derive(params: Params) -> Derived:
    side = lumber_spec(params.board)
    post = lumber_spec(POST_MATERIAL)
    cap = lumber_spec(CAP_MATERIAL)
    board_w = side.width_in or 0.0
    wall = side.thickness_in
    post_size = post.width_in or 0.0
    cap_t = cap.thickness_in if params.cap_rail else 0.0
    cap_w = cap.width_in or 0.0

    course_height = params.height_in - cap_t
    count = max(1, math.ceil(course_height / board_w - 1e-9))
    remainder = course_height - (count - 1) * board_w
    ripped = remainder if remainder < board_w - 1e-9 else None
    widths = (board_w,) * (count - 1) + (board_w if ripped is None else ripped,)

    long_len = params.length_in - 2 * post_size
    end_len = params.width_in - 2 * post_size
    cap_long = params.length_in
    cap_end = params.width_in - 2 * cap_w
    _check_fits_stock(params.board, "long side course", long_len)
    _check_fits_stock(params.board, "end course", end_len)
    _check_fits_stock(POST_MATERIAL, "corner post", course_height)
    if params.cap_rail:
        _check_fits_stock(CAP_MATERIAL, "long cap rail", cap_long)
        _check_fits_stock(CAP_MATERIAL, "end cap rail", cap_end)

    return Derived(
        length_in=params.length_in,
        width_in=params.width_in,
        height_in=params.height_in,
        access=params.access,
        board=params.board,
        cap_rail=params.cap_rail,
        board_width_in=board_w,
        board_thickness_in=wall,
        post_size_in=post_size,
        cap_width_in=cap_w,
        cap_thickness_in=cap_t,
        course_height_in=course_height,
        course_count=count,
        course_widths_in=widths,
        ripped_width_in=ripped,
        post_height_in=course_height,
        inner_length_in=params.length_in - 2 * wall,
        inner_width_in=params.width_in - 2 * wall,
        long_board_length_in=long_len,
        end_board_length_in=end_len,
        cap_long_length_in=cap_long,
        cap_end_length_in=cap_end,
    )


def _rect(w: float, h: float) -> list[tuple[float, float]]:
    return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]


def _notes(rip_to: float | None, full_width: float, length: float, section_w: float, thickness: float) -> list[str]:
    """Cut notes: the rip, and the true length when it is shorter than the board's own cross-section."""
    notes = [] if rip_to is None or abs(rip_to - full_width) < 1e-9 else [f"Rip to {format_fraction(rip_to)} in wide"]
    if length < max(section_w, thickness) - 1e-9:
        notes.append(f"Cut to {format_fraction(length)} in long")
    return notes


def generate_parts(params: Params) -> list[Part]:
    d = derive(params)
    builder = PartBuilder()
    half_l, half_w = d.length_in / 2, d.width_in / 2
    t, ps = d.board_thickness_in, d.post_size_in

    y = 0.0
    for index, width in enumerate(d.course_widths_in):
        rip = width if d.ripped_width_in is not None and index == d.course_count - 1 else None
        long_notes = _notes(rip, d.board_width_in, d.long_board_length_in, width, t)
        end_notes = _notes(rip, d.board_width_in, d.end_board_length_in, width, t)
        for z in (half_w - t, -half_w):
            builder.add("Side course (long)", d.board, _rect(d.long_board_length_in, width), t, pos=(-half_l + ps, y, z), cut_notes=long_notes, group="sides")
        for x in (-half_l, half_l - t):
            builder.add("Side course (end)", d.board, _rect(t, width), d.end_board_length_in, pos=(x, y, -half_w + ps), cut_notes=end_notes, group="sides")
        y += width

    for x in (-half_l, half_l - ps):
        for z in (-half_w, half_w - ps):
            builder.add("Corner post", POST_MATERIAL, _rect(ps, d.post_height_in), ps, pos=(x, 0.0, z), group="posts")

    if d.cap_rail:
        ct, cw = d.cap_thickness_in, d.cap_width_in
        for z in (half_w - cw, -half_w):
            builder.add("Cap rail", CAP_MATERIAL, _rect(d.cap_long_length_in, ct), cw, pos=(-half_l, d.course_height_in, z), group="cap")
        end_notes = _notes(None, cw, d.cap_end_length_in, cw, ct)
        for x in (-half_l, half_l - cw):
            builder.add("Cap rail", CAP_MATERIAL, _rect(cw, ct), d.cap_end_length_in, pos=(x, d.course_height_in, -half_w + cw), cut_notes=end_notes, group="cap")
    return builder.parts


def _labels(parts: list[Part], *names: str) -> list[str]:
    return sorted({p.label for p in parts if p.name in names})


def build_skeleton(params: Params, parts: list[Part]) -> list[SkeletonStep]:
    """Build outline; a step appears only when it applies (no cap parts -> no cap step)."""
    structure = _labels(parts, "Side course (long)", "Side course (end)", "Corner post")
    every = sorted({p.label for p in parts})
    cap = _labels(parts, "Cap rail")
    steps: list[SkeletonStep] = []
    if every:
        steps.append(SkeletonStep(phase="cut", title="Cut the boards and posts to length", part_labels=every, action_key="cut_boards"))
    if structure:
        steps.append(SkeletonStep(phase="assemble", title="Assemble the courses on the posts", part_labels=structure, action_key="assemble_courses"))
    if cap:
        steps.append(SkeletonStep(phase="install", title="Attach the cap rail", part_labels=cap, action_key="attach_cap_rail"))
    if structure:
        steps.append(SkeletonStep(phase="check", title="Level the bed and fill it", part_labels=structure, action_key="level_and_fill"))
    return steps
