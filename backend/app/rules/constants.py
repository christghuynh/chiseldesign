"""Accessibility rule constants (GEO-8).

EVERY VALUE HERE IS A PLACEHOLDER (commonly cited US ADA-style numbers). They must be verified
against ONE chosen, cited guideline source (task NC-3) before anyone relies on them; then fill in
`sources.json` with real citations and remove the VERIFY markers.

Each constant carries a `source_key` that must exist in `sources.json` (a test enforces this), and
the UI shows it as a link on each rule check. The app shows GUIDELINES, never code compliance.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleConstant:
    value: float
    source_key: str
    unit: str
    description: str


# --- Ramp -------------------------------------------------------------------------------------
# VERIFY (NC-3)
MIN_SLOPE_RATIO = RuleConstant(12.0, "tbd-slope", "run per unit rise", "Slope no steeper than 1:12, i.e. slope_ratio >= 12")
# VERIFY (NC-3)
MAX_RISE_PER_RUN_IN = RuleConstant(30.0, "tbd-rise-per-run", "in", "Maximum rise of a single run before an intermediate landing is needed")
# VERIFY (NC-3)
MIN_CLEAR_WIDTH_IN = RuleConstant(36.0, "tbd-clear-width", "in", "Minimum clear width between edges")
# VERIFY (NC-3)
MIN_LANDING_LENGTH_IN = RuleConstant(60.0, "tbd-landing", "in", "Minimum landing length (turn and intermediate landings)")
# VERIFY (NC-3)
HANDRAIL_RISE_THRESHOLD_IN = RuleConstant(6.0, "tbd-handrails", "in", "Rise above which handrails are required")
# VERIFY (NC-3)
HANDRAIL_HEIGHT_IN = RuleConstant(36.0, "tbd-handrail-height", "in", "Height of the handrail top above the walking surface")
# VERIFY (NC-3)
PERMIT_NOTICE_SOURCE = RuleConstant(0.0, "tbd-permit", "", "Source for the always-shown permit and local code notice")
# VERIFY (NC-3)
EDGE_PROTECTION_SOURCE = RuleConstant(0.0, "tbd-edge-protection", "", "Source for edge protection on open sides")
# VERIFY (NC-3)
SITE_FIT_SOURCE = RuleConstant(0.0, "tbd-site-fit", "", "Source for the ramp having to fit the available length")
# Not an accessibility guideline: the stringer must be buyable as one board (lumber data, not NC-3).
LUMBER_FIT_SOURCE = RuleConstant(0.0, "lumber-stock-lengths", "", "Longest board sold for the chosen framing (data/lumber.json)")

# --- Raised garden bed (stretch) ----------------------------------------------------------------
# VERIFY (NC-3)
BED_MIN_HEIGHT_IN = RuleConstant(24.0, "tbd-bed-height", "in", "Lowest comfortable raised-bed height for seated or standing access")
# VERIFY (NC-3)
BED_MAX_HEIGHT_IN = RuleConstant(36.0, "tbd-bed-height", "in", "Highest comfortable raised-bed height")
# VERIFY (NC-3)
BED_MAX_WIDTH_ONE_SIDE_IN = RuleConstant(24.0, "tbd-bed-reach", "in", "Maximum bed width when reachable from one side only")
# VERIFY (NC-3)
BED_MAX_WIDTH_BOTH_SIDES_IN = RuleConstant(48.0, "tbd-bed-reach", "in", "Maximum bed width when reachable from both sides")
# VERIFY (NC-3)
BED_PATH_CLEARANCE_IN = RuleConstant(36.0, "tbd-bed-path", "in", "Clear path to leave around a bed")

# --- Step platform (stretch) --------------------------------------------------------------------
# VERIFY (NC-3)
STEP_MAX_RISER_IN = RuleConstant(7.0, "tbd-step-riser", "in", "Maximum riser height")
# VERIFY (NC-3)
STEP_MIN_TREAD_IN = RuleConstant(11.0, "tbd-step-tread", "in", "Minimum tread depth")

ALL: dict[str, RuleConstant] = {
    name: value for name, value in sorted(globals().items()) if isinstance(value, RuleConstant)
}
