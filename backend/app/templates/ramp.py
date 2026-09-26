"""Ramp template: params, derived layout, and the template interface.

Interface every template module exposes (found automatically by `app.templates`):

    KEY, NAME, DESCRIPTION
    class Params(BaseModel)                                  # defaults, bounds, descriptions -> JSON Schema
    derive(params) -> Derived                                # computed layout: runs, landings, angles
    generate_parts(params) -> list[Part]
    build_skeleton(params, parts) -> list[SkeletonStep]      # deterministic step outline

The geometry is a simplified construction model for planning, NOT an engineered design.

Layout decisions made here (they matter for the rules and the demo):
- The top landing is the existing porch (the ledger attaches to it) and the bottom meets the ground,
  so the only landings the ramp builds are the ones BETWEEN runs: "intermediate" landings when a
  straight ramp is split into several runs, and "turn" landings in a switchback.
- A run's rise is limited by MAX_RISE_PER_RUN, and a stringer must be buyable as ONE board (the
  longest 2x6/2x8 sold is 16 ft). `layout: auto` therefore picks straight only if the straight ramp
  fits the available length AND its stringers fit the lumber; otherwise switchback. Forcing
  `straight` still derives the design (the rules flag it).
"""

import math
from dataclasses import dataclass, replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.data import lumber_spec
from app.models import Part, SkeletonStep
from app.rules.constants import HANDRAIL_RISE_THRESHOLD_IN, MAX_RISE_PER_RUN_IN
from app.templates.ramp_geometry import sloped_length, stringer_length

KEY = "ramp"
NAME = "Accessibility ramp"
DESCRIPTION = "Wooden ramp with optional switchback, landings, curbs and handrails."

# Gap between the side-by-side runs of a switchback: room for a row of posts and rails on each run.
RUN_GAP_IN = 12.0

Layout = Literal["auto", "straight", "switchback"]
ResolvedLayout = Literal["straight", "switchback"]


class Params(BaseModel):
    """Ramp parameters. Bounds not stated in the original spec are marked (inferred)."""

    model_config = ConfigDict(extra="forbid")

    total_rise_in: float = Field(..., ge=1, le=60, title="Total rise (in)", description="Height from the ground to the top of the porch", json_schema_extra={"unit": "in"})
    clear_width_in: float = Field(36, ge=30, le=60, title="Clear width (in)", description="Usable width between the edges", json_schema_extra={"unit": "in"})
    available_length_in: float | None = Field(None, ge=12, le=1200, title="Available length (in)", description="Length of the yard or site available; leave empty for no limit (bounds inferred)", json_schema_extra={"unit": "in"})
    layout: Layout = Field("auto", title="Layout", description="auto picks straight when it fits the site and the lumber, otherwise switchback")
    slope_ratio: float = Field(12, ge=2, le=40, title="Slope (run per unit rise)", description="12 means 1:12; 12 or more is recommended (bounds inferred)")
    landing_length_in: float = Field(60, ge=12, le=240, title="Landing length (in)", description="Length of each landing between runs (bounds inferred)", json_schema_extra={"unit": "in"})
    framing: Literal["2x6_PT", "2x8_PT"] = Field("2x6_PT", title="Framing lumber", description="Stringer and landing framing material")
    stringer_spacing_in: float = Field(16, ge=8, le=24, title="Stringer spacing (in)", description="On center (bounds inferred)", json_schema_extra={"unit": "in"})
    decking: Literal["5/4x6_PT_deck", "3/4_ext_ply"] = Field("5/4x6_PT_deck", title="Decking", description="Deck boards or exterior plywood")
    deck_gap_in: float = Field(0.125, ge=0, le=0.5, title="Deck gap (in)", description="Gap between deck boards (bounds inferred)", json_schema_extra={"unit": "in"})
    handrails: Literal["auto", "yes", "no"] = Field("auto", title="Handrails", description="auto adds handrails when the rise requires them")
    edge_curb: bool = Field(True, title="Edge curb", description="2x4 curb on the open sides")


@dataclass(frozen=True)
class Run:
    """One straight climb. `x_start`, `y_start` and `z_center` are the bottom of the run on the walking
    surface; `direction` is +1 when it climbs toward +X and -1 when it climbs back toward -X."""

    index: int
    rise_in: float
    run_in: float
    sloped_in: float
    direction: Literal[1, -1]
    x_start: float
    x_end: float
    y_start: float
    y_end: float
    z_center: float
    stringer_length_in: float  # length of board one stringer needs; 0.0 when the run has no stringers

    @property
    def has_stringers(self) -> bool:
        """False for a very low run (rise under ~2.5 in): decking lies on the ground, with no stringers or ledger."""
        return self.stringer_length_in > 0


@dataclass(frozen=True)
class Landing:
    """A level platform between two runs. Its walking surface is at `elevation_in`."""

    index: int
    kind: Literal["intermediate", "turn"]
    x_min: float
    x_max: float
    z_min: float
    z_max: float
    elevation_in: float


@dataclass(frozen=True)
class Derived:
    requested_layout: Layout
    layout: ResolvedLayout
    total_rise_in: float
    total_run_in: float
    slope_ratio: float
    slope_angle_rad: float
    slope_angle_deg: float
    clear_width_in: float
    landing_length_in: float
    deck_thickness_in: float
    framing_thickness_in: float
    framing_width_in: float
    stringer_count: int  # per run
    runs: tuple[Run, ...]
    landings: tuple[Landing, ...]
    footprint_x_min: float
    footprint_x_max: float
    footprint_z_min: float
    footprint_z_max: float
    max_stringer_length_in: float
    max_stock_length_in: float  # longest board sold for the framing
    stringers_fit_stock: bool
    fits_site: bool  # footprint length <= available_length_in (True when no limit is given)
    handrails_required: bool  # rise above the handrail threshold
    handrails_included: bool

    @property
    def footprint_length_in(self) -> float:
        return self.footprint_x_max - self.footprint_x_min

    @property
    def footprint_width_in(self) -> float:
        return self.footprint_z_max - self.footprint_z_min

    @property
    def run_count(self) -> int:
        return len(self.runs)


def _runs_and_landings(params: Params, layout: ResolvedLayout, run_count: int) -> tuple[tuple[Run, ...], tuple[Landing, ...]]:
    width = params.clear_width_in
    rise = params.total_rise_in / run_count
    run_in = rise * params.slope_ratio
    sloped = sloped_length(run_in, params.slope_ratio)
    deck_t = lumber_spec(params.decking).thickness_in
    frame_w = lumber_spec(params.framing).width_in or 0.0
    landing_len = params.landing_length_in

    runs: list[Run] = []
    for k in range(run_count):
        if layout == "straight":
            direction: Literal[1, -1] = 1
            x_start = k * (run_in + landing_len)
            z_center = 0.0
        else:
            direction = 1 if k % 2 == 0 else -1
            x_start = 0.0 if direction == 1 else run_in
            z_center = k * (width + RUN_GAP_IN)
        y_start = k * rise
        runs.append(
            Run(
                index=k,
                rise_in=rise,
                run_in=run_in,
                sloped_in=sloped,
                direction=direction,
                x_start=x_start,
                x_end=x_start + direction * run_in,
                y_start=y_start,
                y_end=y_start + rise,
                z_center=z_center,
                stringer_length_in=stringer_length(run_in, params.slope_ratio, deck_t, frame_w, y_start),
            )
        )

    landings: list[Landing] = []
    for k in range(run_count - 1):
        run = runs[k]
        if layout == "straight":
            landings.append(Landing(k, "intermediate", run.x_end, run.x_end + landing_len, -width / 2, width / 2, run.y_end))
        else:
            x_min, x_max = (run_in, run_in + landing_len) if run.direction == 1 else (-landing_len, 0.0)
            landings.append(Landing(k, "turn", x_min, x_max, run.z_center - width / 2, runs[k + 1].z_center + width / 2, run.y_end))
    return tuple(runs), tuple(landings)


def derive_layout(params: Params, layout: ResolvedLayout) -> Derived:
    """Derive the design for a specific layout (the rules use this to test whether a fix would work)."""
    rise_runs = max(1, math.ceil(params.total_rise_in / MAX_RISE_PER_RUN_IN.value - 1e-9))
    run_count = rise_runs if layout == "straight" else max(2, rise_runs)
    runs, landings = _runs_and_landings(params, layout, run_count)

    xs = [x for r in runs for x in (r.x_start, r.x_end)] + [x for l in landings for x in (l.x_min, l.x_max)]
    zs = [z for r in runs for z in (r.z_center - params.clear_width_in / 2, r.z_center + params.clear_width_in / 2)]
    zs += [z for l in landings for z in (l.z_min, l.z_max)]
    footprint_length = max(xs) - min(xs)

    framing = lumber_spec(params.framing)
    max_stringer = max(r.stringer_length_in for r in runs)
    required = params.total_rise_in > HANDRAIL_RISE_THRESHOLD_IN.value
    theta = math.atan(1.0 / params.slope_ratio)
    return Derived(
        requested_layout=params.layout,
        layout=layout,
        total_rise_in=params.total_rise_in,
        total_run_in=params.total_rise_in * params.slope_ratio,
        slope_ratio=params.slope_ratio,
        slope_angle_rad=theta,
        slope_angle_deg=math.degrees(theta),
        clear_width_in=params.clear_width_in,
        landing_length_in=params.landing_length_in,
        deck_thickness_in=lumber_spec(params.decking).thickness_in,
        framing_thickness_in=framing.thickness_in,
        framing_width_in=framing.width_in or 0.0,
        stringer_count=math.ceil(params.clear_width_in / params.stringer_spacing_in) + 1,
        runs=runs,
        landings=landings,
        footprint_x_min=min(xs),
        footprint_x_max=max(xs),
        footprint_z_min=min(zs),
        footprint_z_max=max(zs),
        max_stringer_length_in=max_stringer,
        max_stock_length_in=framing.max_stock_length_in,
        stringers_fit_stock=max_stringer <= framing.max_stock_length_in + 1e-9,
        fits_site=params.available_length_in is None or footprint_length <= params.available_length_in + 1e-9,
        handrails_required=required,
        handrails_included=params.handrails == "yes" or (params.handrails == "auto" and required),
    )


def derive(params: Params) -> Derived:
    straight = derive_layout(params, "straight")
    if params.layout == "straight":
        return straight
    switchback = derive_layout(params, "switchback")
    if params.layout == "switchback":
        return switchback
    # auto: straight only when it fits the site AND every stringer is buyable as one board
    return straight if straight.fits_site and straight.stringers_fit_stock else replace(switchback, requested_layout="auto")


def generate_parts(params: Params) -> list[Part]:
    from app.templates.ramp_parts import build_parts  # imported lazily: that module imports this one

    return build_parts(params, derive(params))


def build_skeleton(params: Params, parts: list[Part]) -> list[SkeletonStep]:
    from app.templates.ramp_skeleton import build_skeleton_steps

    return build_skeleton_steps(params, parts)
