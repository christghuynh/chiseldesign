"""Accessibility rule constants (GEO-8, verified under NC-3).

ONE guideline source: the 2010 ADA Standards for Accessible Design (US Department of Justice). Every
number below was checked against the published text of the standard on 2026-09-26; the section is named in
each comment and in `sources.json` (a test enforces that every constant cites a source that exists there).

This is a US federal standard, not the Canadian or Ontario building code. The app shows GUIDELINES and never
claims code compliance; the UI always tells people to check their local permit and code requirements.

Each constant says how its number relates to the standard:
  "stated"  - the standard states exactly this number.
  "chosen"  - the standard states a range and the app picks a value inside it.
  "derived" - computed from a stated number (see the comment).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleConstant:
    value: float
    source_key: str
    unit: str
    description: str


# --- Ramp -------------------------------------------------------------------------------------
# stated, ADA 405.2: running slope not steeper than 1:12.
MIN_SLOPE_RATIO = RuleConstant(12.0, "ada-405-2", "run per unit rise", "Slope no steeper than 1:12, i.e. slope_ratio >= 12")
# stated, ADA 405.6: rise of any ramp run is 30 inches maximum.
MAX_RISE_PER_RUN_IN = RuleConstant(30.0, "ada-405-6", "in", "Maximum rise of a single run before an intermediate landing is needed")
# stated, ADA 405.5: clear width 36 inches minimum (also between handrails).
MIN_CLEAR_WIDTH_IN = RuleConstant(36.0, "ada-405-5", "in", "Minimum clear width between edges")
# stated, ADA 405.7.3: landing clear length 60 inches minimum (405.7.4: 60 x 60 where the ramp changes direction).
MIN_LANDING_LENGTH_IN = RuleConstant(60.0, "ada-405-7", "in", "Minimum landing length (turn and intermediate landings)")
# stated, ADA 405.8: handrails on runs with a rise greater than 6 inches.
HANDRAIL_RISE_THRESHOLD_IN = RuleConstant(6.0, "ada-405-8", "in", "Rise above which handrails are required")
# chosen, ADA 505.4: top of the handrail gripping surface is 34 to 38 inches above the walking surface.
HANDRAIL_HEIGHT_IN = RuleConstant(36.0, "ada-505-4", "in", "Height of the handrail top above the walking surface (allowed 34 to 38)")
# stated, ADA 405.9.2: a curb or barrier must stop a 4 inch sphere wherever any part of it is within 4 inches of
# the surface, so a curb has to stand at least 4 inches tall (a 2x4 on edge is only 3.5 inches).
EDGE_CURB_MIN_HEIGHT_IN = RuleConstant(4.0, "ada-405-9", "in", "Minimum height of an edge curb above the walking surface")
# Sources for checks that have no number of their own.
EDGE_PROTECTION_SOURCE = RuleConstant(0.0, "ada-405-9", "", "Source for edge protection on open sides (ADA 405.9)")
PERMIT_NOTICE_SOURCE = RuleConstant(0.0, "local-code-notice", "", "Source for the always-shown permit and local code notice")
SITE_FIT_SOURCE = RuleConstant(0.0, "site-fit", "", "Source for the ramp having to fit the available length (geometry)")
# Not an accessibility guideline: the stringer must be buyable as one board (lumber data, not the ADA standard).
LUMBER_FIT_SOURCE = RuleConstant(0.0, "lumber-stock-lengths", "", "Longest board sold for the chosen framing (data/lumber.json)")

# --- Raised garden bed (stretch) ----------------------------------------------------------------
# stated, ADA 308.2.1: low reach 15 inches minimum above the ground.
BED_MIN_HEIGHT_IN = RuleConstant(15.0, "ada-308-reach", "in", "Lowest bed height within the low reach range")
# stated, ADA 308.3.2: a side reach over an obstruction allows the obstruction 34 inches maximum high.
BED_MAX_HEIGHT_IN = RuleConstant(34.0, "ada-308-reach", "in", "Highest bed height for a reach over its edge")
# stated, ADA 308.3.2: the obstruction is 24 inches maximum deep (reach from one side).
BED_MAX_WIDTH_ONE_SIDE_IN = RuleConstant(24.0, "ada-308-reach", "in", "Maximum bed width when reachable from one side only")
# derived from ADA 308.3.2: 24 inches of reach from each of two opposite sides.
BED_MAX_WIDTH_BOTH_SIDES_IN = RuleConstant(48.0, "ada-308-reach", "in", "Maximum bed width when reachable from both sides")
# stated, ADA 403.5.1: walking surfaces on an accessible route are 36 inches minimum wide.
BED_PATH_CLEARANCE_IN = RuleConstant(36.0, "ada-403-5-1", "in", "Clear path to leave around a bed")

# --- Step platform (stretch) --------------------------------------------------------------------
# stated, ADA 504.2: risers 4 to 7 inches high (the app checks the 7 inch maximum).
STEP_MAX_RISER_IN = RuleConstant(7.0, "ada-504-2", "in", "Maximum riser height")
# stated, ADA 504.2: treads 11 inches deep minimum.
STEP_MIN_TREAD_IN = RuleConstant(11.0, "ada-504-2", "in", "Minimum tread depth")

ALL: dict[str, RuleConstant] = {
    name: value for name, value in sorted(globals().items()) if isinstance(value, RuleConstant)
}
