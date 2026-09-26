"""Raised garden bed rule checks (GEO-19): comfortable height, reach and path clearance.

These are GUIDELINES built on placeholder constants (see `constants.py`), never code compliance.

A suggested fix is attached only when applying its patch to the params (and validating them again)
really turns that check into a pass, so the UI never offers a fix that does nothing.
"""

from typing import Any

from app.models import Part, RuleCheck, RuleFix
from app.rules.constants import (
    BED_MAX_HEIGHT_IN,
    BED_MAX_WIDTH_BOTH_SIDES_IN,
    BED_MAX_WIDTH_ONE_SIDE_IN,
    BED_MIN_HEIGHT_IN,
    BED_PATH_CLEARANCE_IN,
)
from app.util.units import format_ft_in

_TOL = 1e-9


def _height_status(height_in: float) -> str:
    return "pass" if BED_MIN_HEIGHT_IN.value - _TOL <= height_in <= BED_MAX_HEIGHT_IN.value + _TOL else "warn"


def width_limit_in(access: str) -> float:
    return BED_MAX_WIDTH_BOTH_SIDES_IN.value if access == "both_sides" else BED_MAX_WIDTH_ONE_SIDE_IN.value


def _width_status(width_in: float, access: str) -> str:
    return "pass" if width_in <= width_limit_in(access) + _TOL else "warn"


def _patched(params: Any, patch: dict[str, Any]) -> Any | None:
    """The params with `patch` applied, or None when the result would not be valid."""
    try:
        return type(params).model_validate({**params.model_dump(), **patch})
    except ValueError:
        return None


def _height_check(params: Any) -> RuleCheck:
    height = params.height_in
    low, high = BED_MIN_HEIGHT_IN.value, BED_MAX_HEIGHT_IN.value
    status = _height_status(height)
    fix = None
    if status == "pass":
        detail = f"Height is {format_ft_in(height)}, inside the {format_ft_in(low)} to {format_ft_in(high)} guideline range"
    else:
        below = height < low
        target = low if below else high
        detail = f"Height is {format_ft_in(height)}; the guideline range is {format_ft_in(low)} to {format_ft_in(high)} ({'too low' if below else 'too high'} for comfortable access)"
        patch = {"height_in": target}
        fixed = _patched(params, patch)
        if fixed is not None and _height_status(fixed.height_in) == "pass":
            fix = RuleFix(label=f"Set the height to {format_ft_in(target)}", params_patch=patch)
    return RuleCheck(id="BED-001", title="Height in accessible range", status=status, detail=detail, source_ref=BED_MIN_HEIGHT_IN.source_key, fix=fix)


def _reach_check(params: Any) -> RuleCheck:
    width, access = params.width_in, params.access
    limit = width_limit_in(access)
    constant = BED_MAX_WIDTH_BOTH_SIDES_IN if access == "both_sides" else BED_MAX_WIDTH_ONE_SIDE_IN
    side_text = "both sides" if access == "both_sides" else "one side"
    status = _width_status(width, access)
    fix = None
    if status == "pass":
        detail = f"Width {format_ft_in(width)} can be reached from {side_text} (limit {format_ft_in(limit)})"
    else:
        detail = f"Width {format_ft_in(width)} is beyond comfortable reach from {side_text}; the limit is {format_ft_in(limit)}"
        patch = {"width_in": limit}
        fixed = _patched(params, patch)
        if fixed is not None and _width_status(fixed.width_in, fixed.access) == "pass":
            fix = RuleFix(label=f"Set the width to {format_ft_in(limit)}", params_patch=patch)
    return RuleCheck(id="BED-002", title="Reach: width within limit", status=status, detail=detail, source_ref=constant.source_key, fix=fix)


def _path_check(params: Any) -> RuleCheck:
    clearance = format_ft_in(BED_PATH_CLEARANCE_IN.value)
    where = "on both long sides" if params.access == "both_sides" else "along the side you work from"
    detail = f"Leave a clear path of at least {clearance} {where} of the {format_ft_in(params.length_in)} x {format_ft_in(params.width_in)} bed"
    return RuleCheck(id="BED-003", title="Path clearance around the bed", status="info", detail=detail, source_ref=BED_PATH_CLEARANCE_IN.source_key)


def check(params: Any, derived: Any, parts: list[Part]) -> list[RuleCheck]:
    return [_height_check(params), _reach_check(params), _path_check(params)]
