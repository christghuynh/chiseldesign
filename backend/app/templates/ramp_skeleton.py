"""Ramp build-step outline (GEO-7): the deterministic skeleton the instruction writer fills in.

`build_skeleton_steps(params, parts)` gets the LABELED parts of a design (cut-list labels; the temporary
label `T` from `build_parts` works too) and returns the steps that apply, always in this order:

    prepare_site (prep)          always
    cut_stringers (cut)          any Stringer
    cut_ledger (cut)             a Ledger
    cut_landing_framing (cut)    any landing rim, joist or post (the posts are cut with the framing)
    build_landings (assemble)    any landing part
    attach_ledger (assemble)     a Ledger
    set_stringers (assemble)     any Stringer
    check_slope (check)          any Stringer
    install_decking (install)    any Deck board, Deck panel, Landing deck board or Landing deck panel
    install_curbs (install)      any Edge curb
    install_handrails (install)  any Handrail post or Handrail
    final_check (check)          always

A step's `part_labels` are the sorted, unique labels of the parts it concerns, chosen by part NAME.
Steps with no matching parts are left out (so a stringerless ramp has no stringer or ledger steps).
"""

from app.models import Part, SkeletonStep
from app.templates.ramp import Params

STRINGER = ("Stringer",)
LEDGER = ("Ledger",)
LANDING_FRAMING = ("Landing rim (end)", "Landing rim (side)", "Landing joist", "Landing post")
LANDING_ALL = (*LANDING_FRAMING, "Landing deck board", "Landing deck panel")
DECKING = ("Deck board", "Deck panel", "Landing deck board", "Landing deck panel")
CURBS = ("Edge curb",)
HANDRAILS = ("Handrail post", "Handrail")

# (action_key, phase, title, part names it concerns, or None for a step that always applies with no parts)
STEPS: tuple[tuple[str, str, str, tuple[str, ...] | None], ...] = (
    ("prepare_site", "prep", "Prepare the site", None),
    ("cut_stringers", "cut", "Cut all stringers", STRINGER),
    ("cut_ledger", "cut", "Cut the ledger", LEDGER),
    ("cut_landing_framing", "cut", "Cut the landing framing", LANDING_FRAMING),
    ("build_landings", "assemble", "Build the landings", LANDING_ALL),
    ("attach_ledger", "assemble", "Attach the ledger", LEDGER),
    ("set_stringers", "assemble", "Set the stringers", STRINGER),
    ("check_slope", "check", "Check the slope with a level", STRINGER),
    ("install_decking", "install", "Install the decking", DECKING),
    ("install_curbs", "install", "Install the edge curbs", CURBS),
    ("install_handrails", "install", "Install the handrail posts and rails", HANDRAILS),
    ("final_check", "check", "Final check", None),
)


def build_skeleton_steps(params: Params, parts: list[Part]) -> list[SkeletonStep]:
    steps: list[SkeletonStep] = []
    for action_key, phase, title, names in STEPS:
        if names is None:
            labels: list[str] = []
        else:
            labels = sorted({p.label for p in parts if p.name in names})
            if not labels:
                continue
        steps.append(SkeletonStep(phase=phase, title=title, part_labels=labels, action_key=action_key))
    return steps
