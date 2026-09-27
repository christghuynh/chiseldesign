"""Step platform template: a set of wooden steps up to a porch. Params, derived layout and the
template interface (see `ramp.py` for the interface every template exposes).

The geometry is a simplified construction model for planning, NOT an engineered design.

Frame: the origin is on the ground at the front face of the FIRST riser, centered across the width.
+X is the direction of travel up the steps, +Z the walker's right, Y is up.

Layout decisions made here (they matter for the rules and the demo):
- The top step surface is the porch, so no top tread is built: n risers and n - 1 treads, where
  n = `step_count` when it is set, otherwise ceil(total rise / max riser) (the fewest steps that keep
  every riser within the maximum). A forced `step_count` can give risers taller than the maximum:
  that still derives, and the riser rule (STEP-001) flags it. The stringers end in a plumb cut against the porch edge.
  A single riser (rise no taller than one riser) is just the riser board: no treads, no stringers.
- `tread_depth_in` is the pitch, the distance between the front faces of two successive risers. That
  is what a person walking up sees: the top of a riser board plus the tread behind it. `run_in` is
  (n - 1) * tread depth.
- Risers are full height, `total_rise / n` (never taller than max_riser_in), and stand on the
  stringer's plumb faces. Treads sit on the notch floors directly behind each riser, top flush with
  the top of that riser; the next riser stands on the back of the tread. Riser tops = step surfaces,
  so the top of the last riser is exactly the total rise.
- A tread is ceil(depth / (5.5 + 0.125)) whole deck boards laid front to back with a 1/8 in gap.
  They are not ripped, so the rearmost board can run past the notch floor by up to one board width;
  the excess hides behind the next riser (trim on site).
- Risers are 2x8 on edge, ripped to the riser height. A riser taller than the 2x8 (7-1/4 in) uses
  a 2x10 instead. A riser taller than a 2x10 (only possible with a forced `step_count`) is built from
  equal strips stacked on edge, the fewest that fit the widest board. Stringers are 2x10 (a 9-1/4 in
  board cut into a sawtooth).
- A rise that would need a stringer longer than the longest 2x10 sold raises ParamValidationError.
"""

import math
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.models import Part, SkeletonStep
from app.templates.step_platform_geometry import MIN_THROAT_IN, profile_board_length, stringer_profile, throat
from app.util.units import format_fraction, format_ft_in

KEY = "step_platform"
NAME = "Step platform"
DESCRIPTION = "Wooden steps up to a porch, with notched stringers, deck-board treads and risers."

STRINGER_MATERIAL = "2x10_PT"
TREAD_MATERIAL = "5/4x6_PT_deck"
RISER_MATERIALS = ("2x8_PT", "2x10_PT")  # narrowest first; the first one wide enough is used
TREAD_GAP_IN = 0.125  # gap between the boards of a tread (same as the ramp deck gap default)
RIP_TOLERANCE_IN = 1 / 16  # a riser this close to the board width is not ripped


class Params(BaseModel):
    """Step platform parameters. Bounds not stated in the original spec were inferred: width_in,
    tread_depth_in, max_riser_in and step_count.

    Schema hints for the parameter panel (see `ramp.Params`): `group` "key" for what a homeowner measures
    or decides, "advanced" for construction choices; `unit` is the unit of a number; `empty_label` is
    what an empty optional value means (the panel says "No limit" without it).
    """

    model_config = ConfigDict(extra="forbid")

    total_rise_in: float = Field(..., ge=1, le=60, title="Rise (height to climb)", description="From the ground to the top of the porch or doorway, measured straight up. The top step is the porch itself.", json_schema_extra={"unit": "in", "group": "key"})
    width_in: float = Field(36, ge=24, le=72, title="Step width", description="Width of every step, from one side edge to the other.", json_schema_extra={"unit": "in", "group": "key"})
    tread_depth_in: float = Field(11, ge=8, le=16, title="Step depth", description="How far each step goes back, from the front of one step to the front of the next. 11 in is the usual minimum.", json_schema_extra={"unit": "in", "group": "advanced"})
    max_riser_in: float = Field(7, ge=4, le=9, title="Tallest step allowed", description="The most any one step may rise, top of one step to the top of the next. Sets how many steps are built when the number of steps is left empty.", json_schema_extra={"unit": "in", "group": "advanced"})
    step_count: int | None = Field(None, ge=1, le=12, title="Number of steps", description="How many times you step up, counting the step onto the porch. Leave empty for the fewest steps that keep each riser under the tallest step allowed.", json_schema_extra={"group": "key", "empty_label": "Automatic"})


@dataclass(frozen=True)
class Derived:
    total_rise_in: float
    width_in: float
    tread_depth_in: float
    riser_count: int  # n
    tread_count: int  # n - 1: the top step surface is the porch
    riser_height_in: float  # total rise / n
    run_in: float  # (n - 1) * tread depth
    tread_boards_per_tread: int
    tread_span_in: float  # front-to-back length of one tread's boards including gaps
    riser_material: str
    riser_rip_width_in: float | None  # width of each riser board; None when it fills the whole board width
    riser_boards_per_riser: int  # 1, or more when a forced step count makes a riser taller than the widest board
    stringer_length_in: float  # board length one stringer needs; 0.0 when there are no stringers
    stringer_stock_length_in: float  # longest stringer board sold
    stringer_diagonal_in: float  # hypot(run, rise): the slope length the stringer follows
    stringer_throat_in: float  # wood left under the notches, square to the slope; 0.0 without stringers
    slope_angle_deg: float

    @property
    def has_stringers(self) -> bool:
        return self.stringer_length_in > 0

    @property
    def has_treads(self) -> bool:
        return self.tread_count > 0


def _riser_boards(height: float) -> tuple[str, int]:
    """The riser board and how many strips of it are stacked: the narrowest board that is wide enough,
    or equal strips of the widest board when no single board is."""
    for material in RISER_MATERIALS:
        if height <= (lumber_spec(material).width_in or 0.0) + 1e-9:
            return material, 1
    widest = RISER_MATERIALS[-1]
    return widest, math.ceil(height / (lumber_spec(widest).width_in or 0.0) - 1e-9)


def _uncuttable_count_message(params: Params, n: int, height: float, board_width: float) -> str:
    """Why a forced step count can't be cut from the stringer board, and the fewest steps that can."""
    fits = [c for c in range(n + 1, 13) if throat(params.total_rise_in / c, params.tread_depth_in, board_width) >= MIN_THROAT_IN - 1e-9]
    advice = f"Use at least {fits[0]} steps" if fits else "Use more steps"
    return (
        f"{n} steps of {format_fraction(height)}\" are too tall to cut from a {lumber_spec(STRINGER_MATERIAL).nominal} stringer. "
        f"{advice}, or leave Number of steps empty."
    )


def derive(params: Params) -> Derived:
    """Compute the layout. Raises ParamValidationError when a board would be longer than the longest one sold."""
    n = params.step_count or max(1, math.ceil(params.total_rise_in / params.max_riser_in - 1e-9))
    height = params.total_rise_in / n
    tread = lumber_spec(TREAD_MATERIAL)
    per_tread = math.ceil(params.tread_depth_in / ((tread.width_in or 0.0) + TREAD_GAP_IN) - 1e-9)
    span = per_tread * (tread.width_in or 0.0) + (per_tread - 1) * TREAD_GAP_IN

    riser_material, riser_boards = _riser_boards(height)
    riser_width = lumber_spec(riser_material).width_in or 0.0
    board_height = height / riser_boards
    rip = None if abs(riser_width - board_height) < RIP_TOLERANCE_IN else board_height

    for material in (riser_material, TREAD_MATERIAL):
        longest = lumber_spec(material).max_stock_length_in
        if params.width_in > longest + 1e-9:
            raise ParamValidationError(f"The width {format_ft_in(params.width_in)} is longer than the longest {material} sold ({format_ft_in(longest)})")

    run = (n - 1) * params.tread_depth_in
    stringer = lumber_spec(STRINGER_MATERIAL)
    length = 0.0
    wood = 0.0
    if n >= 2:
        board_width = stringer.width_in or 0.0
        try:
            profile = stringer_profile(n, height, params.tread_depth_in, tread.thickness_in, board_width)
        except ValueError as exc:
            if params.step_count is not None:
                raise ParamValidationError(_uncuttable_count_message(params, n, height, board_width)) from None
            raise ParamValidationError(f"The stringers cannot be cut: {exc}") from None
        length = profile_board_length(profile, stringer.thickness_in, STRINGER_MATERIAL)
        wood = throat(height, params.tread_depth_in, board_width)
        if length > stringer.max_stock_length_in + 1e-9:
            raise ParamValidationError(
                f"The stringers would need a board {format_ft_in(length)} long, but the longest {STRINGER_MATERIAL} sold is "
                f"{format_ft_in(stringer.max_stock_length_in)}. Reduce the total rise or the tread depth."
            )
    return Derived(
        total_rise_in=params.total_rise_in,
        width_in=params.width_in,
        tread_depth_in=params.tread_depth_in,
        riser_count=n,
        tread_count=n - 1,
        riser_height_in=height,
        run_in=run,
        tread_boards_per_tread=per_tread,
        tread_span_in=span,
        riser_material=riser_material,
        riser_rip_width_in=rip,
        riser_boards_per_riser=riser_boards,
        stringer_length_in=length,
        stringer_stock_length_in=stringer.max_stock_length_in,
        stringer_diagonal_in=math.hypot(run, params.total_rise_in),
        stringer_throat_in=wood,
        slope_angle_deg=math.degrees(math.atan2(height, params.tread_depth_in)),
    )


def _in(inches: float) -> str:
    return f'{format_fraction(inches)}"'


def summarize(params: Params, derived: Derived) -> list[dict[str, str]]:
    """The numbers a builder wants at a glance, as display text (`label`, `value`, optional `detail`).

    Optional template hook (see `ramp.summarize`): every value is formatted here from `derive`.
    """
    n = derived.riser_count
    if params.step_count is None:
        count_detail = f"the fewest with no step taller than {_in(params.max_riser_in)}"
    else:
        count_detail = "the number you chose"
    facts: list[dict[str, str]] = [
        {"label": "Steps", "value": f"{n} step{'s' if n > 1 else ''}", "detail": count_detail},
    ]
    if derived.has_treads:
        facts.append({
            "label": "Each step",
            "value": f"{_in(derived.riser_height_in)} high, {_in(derived.tread_depth_in)} deep",
            "detail": "the top step is the porch",
        })
    else:
        facts.append({"label": "Each step", "value": f"{_in(derived.riser_height_in)} high", "detail": "one step straight onto the porch"})
    if derived.has_treads:
        facts.append({
            "label": "Space needed",
            "value": f"{format_ft_in(derived.run_in)} long × {format_ft_in(derived.width_in)} wide",
            "detail": "from the front of the first step to the porch",
        })
    facts.append({"label": "Total rise", "value": format_ft_in(derived.total_rise_in)})
    if derived.has_stringers:
        facts.append({
            "label": "Stringer length",
            "value": format_ft_in(derived.stringer_length_in),
            "detail": f"longest board sold is {format_ft_in(derived.stringer_stock_length_in)}",
        })
    return facts


def generate_parts(params: Params) -> list[Part]:
    from app.templates.step_platform_parts import build_parts  # imported lazily: that module imports this one

    return build_parts(params, derive(params))


def build_skeleton(params: Params, parts: list[Part]) -> list[SkeletonStep]:
    from app.templates.step_platform_skeleton import build_skeleton_steps

    return build_skeleton_steps(params, parts)
