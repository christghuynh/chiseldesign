"""Rule checks for the step platform (STEP-001 .. STEP-004).

Guidelines only, never code compliance. A rule's fix is offered ONLY when applying it really makes
that rule pass (and the design still builds).
"""

import math
from typing import Any

from pydantic import ValidationError

from app.engine_errors import ParamValidationError
from app.models import Part, RuleCheck, RuleFix
from app.rules.constants import PERMIT_NOTICE_SOURCE, STEP_MAX_RISER_IN, STEP_MIN_RISER_IN, STEP_MIN_TREAD_IN
from app.templates.step_platform import Derived, Params, derive
from app.util.units import format_ft_in

_EPS = 1e-9


def _patched(params: Params, patch: dict[str, Any]) -> tuple[Params, Derived] | None:
    """The design with `patch` applied, or None when the patch is out of bounds or cannot be built."""
    try:
        new = Params.model_validate({**params.model_dump(), **patch})
        return new, derive(new)
    except (ValidationError, ParamValidationError):
        return None


def _smallest_passing_count(params: Params, limit: float) -> int | None:
    """The fewest steps whose risers are within `limit`, when that count is allowed and builds."""
    count = max(1, math.ceil(params.total_rise_in / limit - _EPS))
    result = _patched(params, {"step_count": count})
    return count if result is not None and result[1].riser_height_in <= limit + _EPS else None


def _riser_check(params: Params, derived: Derived) -> RuleCheck:
    """Fails above the guideline maximum, or above the template's own `max_riser_in` (only possible
    with a forced `step_count`)."""
    guideline = STEP_MAX_RISER_IN
    limit = min(guideline.value, params.max_riser_in)
    height = derived.riser_height_in
    over_own_max = height > params.max_riser_in + _EPS
    detail = f"Riser height is {format_ft_in(height)}; " + (
        f"the tallest step allowed is {format_ft_in(params.max_riser_in)}" if over_own_max and params.max_riser_in < guideline.value
        else f"guideline maximum is {format_ft_in(guideline.value)}"
    )
    if height <= limit + _EPS:
        return RuleCheck(id="STEP-001", title="Riser height within maximum", status="pass", source_ref=guideline.source_key, detail=detail)
    fix = None
    if params.step_count is not None:
        count = _smallest_passing_count(params, limit)
        if count is not None:
            fix = RuleFix(label=f"Use {count} steps", params_patch={"step_count": count})
    else:
        patch = {"max_riser_in": guideline.value}
        result = _patched(params, patch)
        if result is not None and result[1].riser_height_in <= guideline.value + _EPS:
            fix = RuleFix(label=f"Limit risers to {format_ft_in(guideline.value)}", params_patch=patch)
    return RuleCheck(id="STEP-001", title="Riser height within maximum", status="fail", source_ref=guideline.source_key, detail=detail, fix=fix)


def _largest_count_within(params: Params, low: float, high: float) -> int | None:
    """The most steps whose risers stay between `low` and `high`, when that count is allowed and builds."""
    count = math.floor(params.total_rise_in / low + _EPS)
    if count < 1:
        return None
    result = _patched(params, {"step_count": count})
    if result is None:
        return None
    height = result[1].riser_height_in
    return count if low - _EPS <= height <= high + _EPS else None


def _min_riser_check(params: Params, derived: Derived) -> RuleCheck:
    """Fails below the guideline minimum: a very short step is easy to miss and trip on. Usually caused by
    forcing too many steps; the fix is the largest count that keeps every riser in the 4 to 7 in range."""
    limit = STEP_MIN_RISER_IN
    height = derived.riser_height_in
    detail = f"Riser height is {format_ft_in(height)}; guideline minimum is {format_ft_in(limit.value)}"
    if height >= limit.value - _EPS:
        return RuleCheck(id="STEP-004", title="Riser height at least the minimum", status="pass", source_ref=limit.source_key, detail=detail)
    high = min(STEP_MAX_RISER_IN.value, params.max_riser_in)
    count = _largest_count_within(params, limit.value, high)
    fix = RuleFix(label=f"Use {count} step{'s' if count > 1 else ''}", params_patch={"step_count": count}) if count is not None else None
    if params.total_rise_in < limit.value - _EPS:
        detail += "; the whole rise is lower than one step should be, so a short ramp or regrading suits it better"
    elif count is None:
        detail += f"; no whole number of steps gives risers between {format_ft_in(limit.value)} and {format_ft_in(high)} for a {format_ft_in(params.total_rise_in)} rise"
    return RuleCheck(id="STEP-004", title="Riser height at least the minimum", status="fail", source_ref=limit.source_key, detail=detail, fix=fix)


def _tread_check(params: Params) -> RuleCheck:
    limit = STEP_MIN_TREAD_IN
    depth = params.tread_depth_in
    if depth >= limit.value - _EPS:
        return RuleCheck(
            id="STEP-002", title="Tread deep enough", status="pass", source_ref=limit.source_key,
            detail=f"Tread depth is {format_ft_in(depth)}; guideline minimum is {format_ft_in(limit.value)}",
        )
    fix = None
    patch = {"tread_depth_in": limit.value}
    if _patched(params, patch) is not None:
        fix = RuleFix(label=f"Make treads {format_ft_in(limit.value)} deep", params_patch=patch)
    return RuleCheck(
        id="STEP-002", title="Tread deep enough", status="fail", source_ref=limit.source_key,
        detail=f"Tread depth is {format_ft_in(depth)}; guideline minimum is {format_ft_in(limit.value)}",
        fix=fix,
    )


def check(params: Params, derived: Derived, parts: list[Part]) -> list[RuleCheck]:
    return [
        _riser_check(params, derived),
        _tread_check(params),
        RuleCheck(
            id="STEP-003", title="Permit and local code notice", status="info", source_ref=PERMIT_NOTICE_SOURCE.source_key,
            detail="Guidelines, not code compliance. Check local permit requirements.",
        ),
        _min_riser_check(params, derived),
    ]
