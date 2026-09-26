"""GEO-9: ramp rule checks (RAMP-001 .. RAMP-009), computed from params and derived only (no parts)."""

import random

import pytest

from app.models import RuleCheck
from app.rules import check_design, sources
from app.rules import ramp as rules
from app.rules.constants import (
    HANDRAIL_RISE_THRESHOLD_IN,
    MAX_RISE_PER_RUN_IN,
    MIN_CLEAR_WIDTH_IN,
    MIN_LANDING_LENGTH_IN,
    MIN_SLOPE_RATIO,
)
from app.templates.ramp import Params, derive

IDS = [f"RAMP-00{n}" for n in range(1, 10)]


def P(**kw) -> Params:
    kw.setdefault("total_rise_in", 21)
    return Params(**kw)


def run(**kw) -> dict[str, RuleCheck]:
    params = P(**kw)
    return {c.id: c for c in rules.check(params, derive(params), [])}


# --- shape ----------------------------------------------------------------------------------------


def test_ids_and_order():
    params = P()
    checks = rules.check(params, derive(params), [])
    assert [c.id for c in checks] == IDS
    assert [c.title for c in checks] == [
        "Slope no steeper than 1:12",
        "Rise per run within maximum",
        "Clear width at least the minimum",
        "Landings long enough",
        "Handrails present when required",
        "Edge protection on open sides",
        "Fits the available length",
        "Permit and local code notice",
        "Stringers can be bought as one board",
    ]


def test_defaults_all_pass_except_the_notice():
    checks = run(total_rise_in=12)
    assert {i: c.status for i, c in checks.items()} == {**{i: "pass" for i in IDS}, "RAMP-008": "info"}
    assert all(c.fix is None for c in checks.values())


def test_parts_argument_is_ignored():
    params = P()
    derived = derive(params)
    assert rules.check(params, derived, []) == rules.check(params, derived, ["ignored"])  # type: ignore[list-item]


def test_check_design_dispatches_to_the_ramp_module():
    params = P(available_length_in=144)
    derived = derive(params)
    assert check_design("ramp", params, derived, []) == rules.check(params, derived, [])


def test_deterministic():
    params = P(slope_ratio=10, clear_width_in=32, available_length_in=150, edge_curb=False, handrails="no")
    derived = derive(params)
    first = rules.check(params, derived, [])
    assert first == rules.check(params, derived, [])
    assert [c.model_dump() for c in first] == [c.model_dump() for c in rules.check(params, derive(params), [])]


def test_checks_validate_against_the_pydantic_model():
    for kw in [{}, {"slope_ratio": 8, "available_length_in": 100, "handrails": "no", "edge_curb": False}]:
        params = P(**kw)
        for c in rules.check(params, derive(params), []):
            assert RuleCheck.model_validate(c.model_dump()) == c
            assert c.status in ("pass", "warn", "fail", "info")
            assert c.detail and c.title


def test_every_source_ref_exists_and_uses_the_constant_keys():
    known = sources()
    checks = run(available_length_in=144)
    assert all(c.source_ref in known for c in checks.values())
    assert checks["RAMP-001"].source_ref == MIN_SLOPE_RATIO.source_key
    assert checks["RAMP-002"].source_ref == MAX_RISE_PER_RUN_IN.source_key
    assert checks["RAMP-003"].source_ref == MIN_CLEAR_WIDTH_IN.source_key
    assert checks["RAMP-004"].source_ref == MIN_LANDING_LENGTH_IN.source_key
    assert checks["RAMP-005"].source_ref == HANDRAIL_RISE_THRESHOLD_IN.source_key
    assert checks["RAMP-006"].source_ref == "tbd-edge-protection"
    assert checks["RAMP-007"].source_ref == "tbd-site-fit"
    assert checks["RAMP-008"].source_ref == "tbd-permit"
    assert checks["RAMP-009"].source_ref == "lumber-stock-lengths"


# --- RAMP-001 slope -------------------------------------------------------------------------------


def test_slope_exactly_1_in_12_passes():
    c = run(total_rise_in=12, slope_ratio=12)["RAMP-001"]
    assert c.status == "pass" and c.fix is None
    assert c.detail == "Slope is 1:12; guideline is 1:12 or gentler"


def test_slope_just_steeper_fails_with_a_fix():
    c = run(total_rise_in=12, slope_ratio=11.99)["RAMP-001"]
    assert c.status == "fail"
    assert c.detail == "Slope is 1:11.99; guideline is 1:12 or gentler"
    assert c.fix is not None and c.fix.params_patch == {"slope_ratio": 12} and c.fix.label == "Set slope to 1:12"


def test_gentler_slope_passes():
    assert run(total_rise_in=12, slope_ratio=20)["RAMP-001"].status == "pass"


# --- RAMP-002 rise per run ------------------------------------------------------------------------


def test_rise_per_run_passes_at_the_maximum():
    c = run(total_rise_in=60)["RAMP-002"]  # two runs of exactly 30 in
    assert c.status == "pass" and c.fix is None
    assert c.detail == "Rise per run is 2' 6\"; guideline maximum is 2' 6\""


def test_rise_per_run_uses_the_largest_run():
    c = run(total_rise_in=21)["RAMP-002"]
    assert c.status == "pass"
    assert c.detail == "Rise per run is 10-1/2\"; guideline maximum is 2' 6\""


def test_rise_per_run_fails_when_a_run_exceeds_the_maximum():
    params = P(total_rise_in=40)
    derived = derive(params)
    # derive splits the rise, so build an oversized run by hand to exercise the failing branch
    from dataclasses import replace

    tall = replace(derived.runs[0], rise_in=31.0)
    bad = replace(derived, runs=(tall, *derived.runs[1:]))
    c = rules._rise_per_run(params, bad)
    assert c.status == "fail" and "2' 7\"" in c.detail and "2' 6\"" in c.detail


# --- RAMP-003 width -------------------------------------------------------------------------------


def test_width_35_fails_and_36_passes():
    low = run(clear_width_in=35)["RAMP-003"]
    assert low.status == "fail" and low.detail == "Clear width is 2' 11\"; guideline minimum is 3' 0\""
    assert low.fix is not None and low.fix.params_patch == {"clear_width_in": 36} and low.fix.label == "Widen to 3' 0\""
    ok = run(clear_width_in=36)["RAMP-003"]
    assert ok.status == "pass" and ok.fix is None


# --- RAMP-004 landings ----------------------------------------------------------------------------


def test_no_landings_passes_with_the_porch_explanation():
    c = run(total_rise_in=12, landing_length_in=20)["RAMP-004"]  # a short landing is irrelevant without landings
    assert c.status == "pass" and c.fix is None
    assert "Porch is the top landing" in c.detail and "ground" in c.detail


def test_landing_59_fails_and_60_passes():
    low = run(total_rise_in=21, landing_length_in=59)["RAMP-004"]  # rise 21 -> switchback with a turn landing
    assert low.status == "fail" and low.detail == "Landings are 4' 11\" long; guideline minimum is 5' 0\""
    assert low.fix is not None and low.fix.params_patch == {"landing_length_in": 60}
    assert low.fix.label == "Lengthen landings to 5' 0\""
    assert run(total_rise_in=21, landing_length_in=60)["RAMP-004"].status == "pass"


def test_landing_check_also_applies_to_intermediate_landings():
    c = run(total_rise_in=31, landing_length_in=40)["RAMP-004"]  # straight, two runs
    assert c.status == "fail" and c.fix is not None


# --- RAMP-005 handrails ---------------------------------------------------------------------------


def test_handrails_not_required_at_exactly_6_in():
    for setting in ("no", "auto", "yes"):
        c = run(total_rise_in=6, handrails=setting)["RAMP-005"]
        assert c.status == "pass" and c.fix is None
    assert run(total_rise_in=6, handrails="no")["RAMP-005"].detail == (
        "Rise is 6\"; handrails are not required for a rise of 6\" or less"
    )


def test_handrails_off_just_above_6_in_warns_with_a_fix():
    c = run(total_rise_in=6.01, handrails="no")["RAMP-005"]
    assert c.status == "warn"
    assert c.fix is not None and c.fix.params_patch == {"handrails": "yes"}


@pytest.mark.parametrize("setting", ["auto", "yes"])
def test_handrails_required_and_included_passes(setting):
    c = run(total_rise_in=15, handrails=setting)["RAMP-005"]
    assert c.status == "pass" and c.fix is None
    assert c.detail == "Rise is 1' 3\"; handrails are included"


# --- RAMP-006 edge protection ---------------------------------------------------------------------


def test_edge_curb():
    off = run(edge_curb=False)["RAMP-006"]
    assert off.status == "warn" and off.fix is not None and off.fix.params_patch == {"edge_curb": True}
    on = run(edge_curb=True)["RAMP-006"]
    assert on.status == "pass" and on.fix is None


# --- RAMP-007 site fit ----------------------------------------------------------------------------


def test_no_length_limit_passes():
    c = run(total_rise_in=21)["RAMP-007"]
    assert c.status == "pass" and c.detail == "No length limit was given"


def test_forced_straight_too_long_fails_with_the_switchback_fix():
    c = run(total_rise_in=15, layout="straight", available_length_in=160)["RAMP-007"]
    assert c.status == "fail"
    assert c.detail == "Ramp needs 15' 0\" but only 13' 4\" is available"
    assert c.fix is not None and c.fix.params_patch == {"layout": "switchback"}
    assert c.fix.label == "Switch to switchback layout"


def test_demo_rise_21_in_144_in_yard_fails_without_a_fix():
    """A two-run switchback needs 126 + 60 = 186 in, so switching layout cannot help."""
    checks = run(total_rise_in=21, available_length_in=144)
    c = checks["RAMP-007"]
    assert c.status == "fail" and c.fix is None
    assert c.detail == "Ramp needs 15' 6\" but only 12' 0\" is available"
    assert checks["RAMP-009"].status == "pass"  # the switchback derive picked has buyable stringers


def test_forced_straight_at_the_demo_offers_no_site_fix_either():
    c = run(total_rise_in=21, layout="straight", available_length_in=144)["RAMP-007"]
    assert c.status == "fail" and c.fix is None  # the switchback (186 in) still does not fit 144 in


def test_auto_layout_that_fits_after_switching_passes():
    c = run(total_rise_in=15, available_length_in=160)["RAMP-007"]  # derive already picked the switchback
    assert c.status == "pass"


def test_site_fit_is_inclusive():
    exact = run(total_rise_in=15, available_length_in=150)["RAMP-007"]
    assert exact.status == "pass"


# --- RAMP-009 stringer stock ----------------------------------------------------------------------


def test_forced_straight_at_rise_21_fails_stock_with_the_switchback_fix():
    c = run(total_rise_in=21, layout="straight")["RAMP-009"]
    assert c.status == "fail"
    assert "A stringer needs 20' " in c.detail and "longest board sold is 16' 0\"" in c.detail
    assert c.fix is not None and c.fix.params_patch == {"layout": "switchback"}


def test_rise_60_stringers_cannot_be_fixed():
    for layout in ("auto", "straight", "switchback"):
        c = run(total_rise_in=60, layout=layout)["RAMP-009"]
        assert c.status == "fail" and c.fix is None


def test_stock_passes_for_the_switchback_auto_picks():
    c = run(total_rise_in=21)["RAMP-009"]
    assert c.status == "pass" and c.fix is None
    assert c.detail.endswith("the longest board sold is 16' 0\"")


# --- notice ---------------------------------------------------------------------------------------


def test_permit_notice_is_always_info():
    for kw in [{}, {"slope_ratio": 5, "clear_width_in": 30, "available_length_in": 100}, {"total_rise_in": 60}]:
        c = run(**kw)["RAMP-008"]
        assert c.status == "info" and c.fix is None
        assert c.detail == "Guidelines, not code compliance. Check local permit requirements."


def test_details_use_feet_and_inches():
    checks = run(total_rise_in=21, available_length_in=144, clear_width_in=33)
    for i in ("RAMP-002", "RAMP-003", "RAMP-004", "RAMP-007"):
        assert '"' in checks[i].detail


# --- fixes ----------------------------------------------------------------------------------------

FIXABLE = [
    ("RAMP-001", {"total_rise_in": 12, "slope_ratio": 8}),
    ("RAMP-003", {"clear_width_in": 32}),
    ("RAMP-004", {"landing_length_in": 30}),
    ("RAMP-005", {"total_rise_in": 15, "handrails": "no"}),
    ("RAMP-006", {"edge_curb": False}),
    ("RAMP-007", {"total_rise_in": 15, "layout": "straight", "available_length_in": 160}),
    ("RAMP-009", {"total_rise_in": 21, "layout": "straight"}),
]


@pytest.mark.parametrize(("check_id", "kw"), FIXABLE)
def test_applying_the_fix_turns_the_check_into_a_pass(check_id, kw):
    params = P(**kw)
    before = {c.id: c for c in rules.check(params, derive(params), [])}[check_id]
    assert before.status in ("fail", "warn") and before.fix is not None
    patched = Params.model_validate({**params.model_dump(), **before.fix.params_patch})
    after = {c.id: c for c in rules.check(patched, derive(patched), [])}[check_id]
    assert after.status == "pass" and after.fix is None


def test_fixes_only_on_fail_or_warn_checks():
    for kw in [{}, {"slope_ratio": 8, "clear_width_in": 32, "edge_curb": False, "handrails": "no", "available_length_in": 100}]:
        for c in run(**kw).values():
            if c.fix is not None:
                assert c.status in ("fail", "warn")


def test_a_fix_that_would_not_work_is_dropped():
    """Safety net: a proposal whose patch leaves the check failing must not be attached."""
    params = P(total_rise_in=21, layout="straight")
    derived = derive(params)
    useless = rules._verified_fix(rules._stringer_stock, lambda p, d: ("No-op", {"framing": "2x6_PT"}), params, derived)
    assert useless is None
    invalid = rules._verified_fix(rules._stringer_stock, lambda p, d: ("Bad", {"slope_ratio": 999}), params, derived)
    assert invalid is None
    good = rules._verified_fix(rules._stringer_stock, lambda p, d: ("Good", {"layout": "switchback"}), params, derived)
    assert good is not None and good.label == "Good"


# --- randomized sweep -----------------------------------------------------------------------------


def _random_params(rng: random.Random) -> Params:
    return Params(
        total_rise_in=round(rng.uniform(1, 60), 2),
        clear_width_in=rng.choice([30, 33, 35, 36, 42, 60]),
        available_length_in=rng.choice([None, 12, 100, 144, 160, 250, 400, 1200]),
        layout=rng.choice(["auto", "straight", "switchback"]),
        slope_ratio=rng.choice([2, 8, 11.99, 12, 14, 20, 40]),
        landing_length_in=rng.choice([12, 40, 59, 60, 72, 240]),
        framing=rng.choice(["2x6_PT", "2x8_PT"]),
        stringer_spacing_in=rng.choice([8, 12, 16, 24]),
        decking=rng.choice(["5/4x6_PT_deck", "3/4_ext_ply"]),
        handrails=rng.choice(["auto", "yes", "no"]),
        edge_curb=rng.choice([True, False]),
    )


def test_randomized_sweep_invariants():
    rng = random.Random(20240607)
    known = sources()
    fixes_seen = 0
    for _ in range(300):
        params = _random_params(rng)
        derived = derive(params)
        checks = rules.check(params, derived, [])
        assert [c.id for c in checks] == IDS
        assert checks[7].status == "info"
        for c in checks:
            assert c.status in ("pass", "warn", "fail", "info")
            assert c.source_ref in known
            if c.fix is None:
                continue
            fixes_seen += 1
            assert c.status in ("fail", "warn")
            patched = Params.model_validate({**params.model_dump(), **c.fix.params_patch})
            after = {x.id: x for x in rules.check(patched, derive(patched), [])}[c.id]
            assert after.status == "pass", (params, c)
    assert fixes_seen > 50
