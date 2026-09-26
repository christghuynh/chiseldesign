"""Ramp rule checks (GEO-9): accessibility GUIDELINE checks, never a code-compliance claim.

`check(params, derived, parts)` returns RAMP-001 .. RAMP-009 in that order. The checks are computed
from `params` and `derived` alone; `parts` is accepted for the template interface and ignored.

How it is put together:
- Each check is a small pure function `(params, derived) -> RuleCheck` WITHOUT a fix.
- A check that can be fixed has a matching "fix proposal" function that returns a label and a
  params patch (or None when no sensible fix exists).
- Safety net (`_verified_fix`): a proposed fix is attached only after it is applied to the params,
  the design is re-derived and that ONE check is re-evaluated (without computing fixes, so there is
  no recursion) and comes back `pass`. A patch that would leave the check failing, or that makes the
  params invalid, is dropped. Fixes therefore only ever appear on `fail` / `warn` checks.

Decisions on things the spec left open:
- Thresholds are compared with a 1e-9 tolerance so float noise never flips a boundary case.
- RAMP-002 compares the largest run rise in `derived.runs`. `derive` splits the rise into runs
  that respect the maximum, so this passes for derived designs; it stays as an independent check.
- RAMP-005 uses `derived.handrails_required` / `derived.handrails_included` ("auto" counts as
  included when required). Only an explicit `handrails: "no"` on a required design warns.
- RAMP-007 and RAMP-009 only offer the switchback fix when the current resolved layout is straight
  and a switchback actually satisfies that check. A switchback that still does not fit has no fix
  (for example rise 21 in with 144 in available: a two-run switchback needs 186 in).
- Each fix changes only the parameter that check is about; it does not promise that OTHER checks
  stay green (for example a longer landing can make the ramp longer than the site).
"""

from collections.abc import Callable

from pydantic import ValidationError

from app.models import Part, RuleCheck, RuleFix
from app.rules.constants import (
    EDGE_PROTECTION_SOURCE,
    HANDRAIL_RISE_THRESHOLD_IN,
    LUMBER_FIT_SOURCE,
    MAX_RISE_PER_RUN_IN,
    MIN_CLEAR_WIDTH_IN,
    MIN_LANDING_LENGTH_IN,
    MIN_SLOPE_RATIO,
    PERMIT_NOTICE_SOURCE,
    SITE_FIT_SOURCE,
)
from app.templates.ramp import Derived, Params, derive, derive_layout
from app.util.units import format_ft_in

_EPS = 1e-9

Evaluator = Callable[[Params, Derived], RuleCheck]
FixProposal = tuple[str, dict]  # (label, params_patch)


def _make(check_id: str, title: str, status: str, detail: str, source_key: str) -> RuleCheck:
    return RuleCheck(id=check_id, title=title, status=status, detail=detail, source_ref=source_key)  # type: ignore[arg-type]


# --- Evaluators: (params, derived) -> RuleCheck without a fix ----------------------------------------


def _slope(params: Params, derived: Derived) -> RuleCheck:
    ok = params.slope_ratio >= MIN_SLOPE_RATIO.value - _EPS
    guideline = f"{MIN_SLOPE_RATIO.value:g}"
    return _make(
        "RAMP-001",
        "Slope no steeper than 1:12",
        "pass" if ok else "fail",
        f"Slope is 1:{params.slope_ratio:g}; guideline is 1:{guideline} or gentler",
        MIN_SLOPE_RATIO.source_key,
    )


def _rise_per_run(params: Params, derived: Derived) -> RuleCheck:
    largest = max(run.rise_in for run in derived.runs)
    ok = largest <= MAX_RISE_PER_RUN_IN.value + _EPS
    return _make(
        "RAMP-002",
        "Rise per run within maximum",
        "pass" if ok else "fail",
        f"Rise per run is {format_ft_in(largest)}; guideline maximum is {format_ft_in(MAX_RISE_PER_RUN_IN.value)}",
        MAX_RISE_PER_RUN_IN.source_key,
    )


def _clear_width(params: Params, derived: Derived) -> RuleCheck:
    ok = params.clear_width_in >= MIN_CLEAR_WIDTH_IN.value - _EPS
    return _make(
        "RAMP-003",
        "Clear width at least the minimum",
        "pass" if ok else "fail",
        f"Clear width is {format_ft_in(params.clear_width_in)}; guideline minimum is {format_ft_in(MIN_CLEAR_WIDTH_IN.value)}",
        MIN_CLEAR_WIDTH_IN.source_key,
    )


def _landings(params: Params, derived: Derived) -> RuleCheck:
    title = "Landings long enough"
    key = MIN_LANDING_LENGTH_IN.source_key
    if not derived.landings:
        return _make(
            "RAMP-004",
            title,
            "pass",
            "Porch is the top landing and the bottom meets the ground; this design needs no landings between runs",
            key,
        )
    ok = params.landing_length_in >= MIN_LANDING_LENGTH_IN.value - _EPS
    return _make(
        "RAMP-004",
        title,
        "pass" if ok else "fail",
        f"Landings are {format_ft_in(params.landing_length_in)} long; guideline minimum is {format_ft_in(MIN_LANDING_LENGTH_IN.value)}",
        key,
    )


def _handrails(params: Params, derived: Derived) -> RuleCheck:
    title = "Handrails present when required"
    key = HANDRAIL_RISE_THRESHOLD_IN.source_key
    rise = format_ft_in(derived.total_rise_in)
    threshold = format_ft_in(HANDRAIL_RISE_THRESHOLD_IN.value)
    if not derived.handrails_required:
        return _make("RAMP-005", title, "pass", f"Rise is {rise}; handrails are not required for a rise of {threshold} or less", key)
    if derived.handrails_included:
        return _make("RAMP-005", title, "pass", f"Rise is {rise}; handrails are included", key)
    return _make("RAMP-005", title, "warn", f"Rise is {rise}, above {threshold}, and handrails are turned off; the guideline is to include them", key)


def _edge_protection(params: Params, derived: Derived) -> RuleCheck:
    title = "Edge protection on open sides"
    key = EDGE_PROTECTION_SOURCE.source_key
    if params.edge_curb:
        return _make("RAMP-006", title, "pass", "Edge curbs are included on both sides", key)
    return _make("RAMP-006", title, "warn", "No edge curbs; the open sides have no edge protection", key)


def _site_fit(params: Params, derived: Derived) -> RuleCheck:
    title = "Fits the available length"
    key = SITE_FIT_SOURCE.source_key
    available = params.available_length_in
    if available is None:
        return _make("RAMP-007", title, "pass", "No length limit was given", key)
    needs = format_ft_in(derived.footprint_length_in)
    have = format_ft_in(available)
    if derived.fits_site:
        return _make("RAMP-007", title, "pass", f"Ramp needs {needs} and {have} is available", key)
    return _make("RAMP-007", title, "fail", f"Ramp needs {needs} but only {have} is available", key)


def _permit_notice(params: Params, derived: Derived) -> RuleCheck:
    return _make(
        "RAMP-008",
        "Permit and local code notice",
        "info",
        "Guidelines, not code compliance. Check local permit requirements.",
        PERMIT_NOTICE_SOURCE.source_key,
    )


def _stringer_stock(params: Params, derived: Derived) -> RuleCheck:
    title = "Stringers can be bought as one board"
    key = LUMBER_FIT_SOURCE.source_key
    needs = format_ft_in(derived.max_stringer_length_in)
    longest = format_ft_in(derived.max_stock_length_in)
    if derived.stringers_fit_stock:
        return _make("RAMP-009", title, "pass", f"Longest stringer is {needs}; the longest board sold is {longest}", key)
    return _make("RAMP-009", title, "fail", f"A stringer needs {needs} but the longest board sold is {longest}", key)


# --- Fix proposals: (params, derived) -> (label, patch) | None -----------------------------------------


def _fix_slope(params: Params, derived: Derived) -> FixProposal:
    return f"Set slope to 1:{MIN_SLOPE_RATIO.value:g}", {"slope_ratio": MIN_SLOPE_RATIO.value}


def _fix_width(params: Params, derived: Derived) -> FixProposal:
    return f"Widen to {format_ft_in(MIN_CLEAR_WIDTH_IN.value)}", {"clear_width_in": MIN_CLEAR_WIDTH_IN.value}


def _fix_landings(params: Params, derived: Derived) -> FixProposal:
    return f"Lengthen landings to {format_ft_in(MIN_LANDING_LENGTH_IN.value)}", {"landing_length_in": MIN_LANDING_LENGTH_IN.value}


def _fix_handrails(params: Params, derived: Derived) -> FixProposal:
    return "Add handrails", {"handrails": "yes"}


def _fix_edge_curb(params: Params, derived: Derived) -> FixProposal:
    return "Add edge curbs", {"edge_curb": True}


def _fix_switchback(params: Params, derived: Derived) -> FixProposal | None:
    """Only worth proposing from a straight layout; the safety net checks that it really helps."""
    if derived.layout != "straight":
        return None
    return "Switch to switchback layout", {"layout": "switchback"}


def _fix_site_fit(params: Params, derived: Derived) -> FixProposal | None:
    if derived.layout != "straight" or not derive_layout(params, "switchback").fits_site:
        return None
    return _fix_switchback(params, derived)


def _fix_stringer_stock(params: Params, derived: Derived) -> FixProposal | None:
    if derived.layout != "straight" or not derive_layout(params, "switchback").stringers_fit_stock:
        return None
    return _fix_switchback(params, derived)


# (evaluator, optional fix proposal) in output order.
_CHECKS: tuple[tuple[Evaluator, Callable[[Params, Derived], FixProposal | None] | None], ...] = (
    (_slope, _fix_slope),
    (_rise_per_run, None),
    (_clear_width, _fix_width),
    (_landings, _fix_landings),
    (_handrails, _fix_handrails),
    (_edge_protection, _fix_edge_curb),
    (_site_fit, _fix_site_fit),
    (_permit_notice, None),
    (_stringer_stock, _fix_stringer_stock),
)


def _verified_fix(
    evaluator: Evaluator, propose: Callable[[Params, Derived], FixProposal | None], params: Params, derived: Derived
) -> RuleFix | None:
    """Build the proposed fix only if applying it makes this check pass (re-derive, re-evaluate once)."""
    proposal = propose(params, derived)
    if proposal is None:
        return None
    label, patch = proposal
    try:
        patched = Params.model_validate({**params.model_dump(), **patch})
        rederived = derive(patched)
    except (ValidationError, ValueError):
        return None
    if evaluator(patched, rederived).status != "pass":
        return None
    return RuleFix(label=label, params_patch=patch)


def check(params: Params, derived: Derived, parts: list[Part]) -> list[RuleCheck]:
    """Run RAMP-001 .. RAMP-009. `parts` is accepted for the interface and not used."""
    results: list[RuleCheck] = []
    for evaluator, propose in _CHECKS:
        result = evaluator(params, derived)
        if propose is not None and result.status in ("fail", "warn"):
            result = result.model_copy(update={"fix": _verified_fix(evaluator, propose, params, derived)})
        results.append(result)
    return results
