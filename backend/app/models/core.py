"""Core data contracts. The backend is authoritative.

Units are inches everywhere. World frame is Y-up (see foundation.md).
Changes here must be announced to the whole team and followed by `make types`.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    """Base for every contract model.

    Defaults are marked required in the serialization JSON Schema so the
    generated TS types treat fields the server always returns as non-optional.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ParamValue(Contract):
    value: float | int | str | bool
    source: Literal["read", "inferred", "default", "user"]
    confidence: float | None = None  # 0..1, only for read/inferred


class Transform(Contract):
    pos: tuple[float, float, float]  # inches
    rot: tuple[float, float, float]  # Euler XYZ, radians, applied in the part's local frame before translation


class Part(Contract):
    id: str  # "A-1"
    label: str  # "A"
    name: str  # "Stringer"
    material: str  # key in lumber.json, e.g. "2x6_PT"
    profile: list[tuple[float, float]]  # local XY, inches, CCW
    thickness: float  # extrusion depth along local +Z, inches
    transform: Transform
    cut_notes: list[str] = []  # ["15.0° plumb cut at top end"]
    group: str | None = None  # "run_1", "landing", "handrail"


class RuleFix(Contract):
    label: str  # "Switch to switchback layout"
    params_patch: dict[str, Any]


class RuleCheck(Contract):
    id: str  # "RAMP-001"
    title: str
    status: Literal["pass", "warn", "fail", "info"]
    detail: str  # "Slope is 1:9.8 — guideline is 1:12 or gentler"
    source_ref: str  # citation key from rules/sources.json
    fix: RuleFix | None = None


class Spec(Contract):
    schema_version: Literal["1.0"] = "1.0"
    template: str  # "ramp"
    params: dict[str, ParamValue]
    assumed: list[str]  # param names with source inferred/default
    parts: list[Part] = []  # computed by /generate
    rule_checks: list[RuleCheck] = []  # computed by /generate
    meta: dict[str, Any] = {}  # contractor_quote_cad, notes, image_ref


class CutListRow(Contract):
    label: str
    name: str
    material: str
    actual_dims: str  # "1-1/2 × 5-1/2"
    length_in: float
    length_display: str  # "5' 4-1/2\""
    qty: int
    part_ids: list[str]
    cut_notes: list[str]


class PlacedPiece(Contract):
    label: str
    part_id: str
    x: float  # inches on the stock
    y: float  # (1D: y=0, h=board width)
    w: float
    h: float
    rotated: bool = False


class StockLayout(Contract):
    stock_id: str  # "2x6_PT_144-1"
    material: str
    kind: Literal["board", "sheet"]
    length_in: float
    width_in: float
    pieces: list[PlacedPiece]
    utilization: float  # 0..1


class ShoppingItem(Contract):
    key: str
    description: str
    unit: str
    qty: int
    unit_price: float  # CAD
    subtotal: float  # CAD
    source_url: str | None


class Plan(Contract):
    cut_list: list[CutListRow]
    layouts: list[StockLayout]
    shopping: list[ShoppingItem]
    subtotal: float  # CAD, 2 decimals
    tax: float
    total: float
    contractor_quote: float | None
    savings: float | None
    # True when any priced item uses a placeholder price (a prices.json entry marked placeholder).
    # The UI must say the total is an estimate when this is set.
    has_placeholder_prices: bool = False


class CutCallout(Contract):
    label: str
    spoken: str  # generated in CODE, never by the LLM: "two-by-six, sixty-four and a half inches"


class BuildStep(Contract):
    n: int
    title: str
    text: str
    part_labels: list[str]
    cut_callouts: list[CutCallout] = []
    safety_tip: str | None = None


class SkeletonStep(Contract):
    """One step of a template's deterministic build outline (input to /instructions)."""

    phase: str  # "cut", "assemble", "install", "check"
    title: str  # "Cut all stringers"
    part_labels: list[str]  # ["A"]
    action_key: str  # "cut_stringers"
