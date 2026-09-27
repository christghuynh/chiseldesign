"""STEP-004 (ADA 504.2 minimum riser) and BED-004 (no thin ripped top course), with their one-click fixes."""

from app import engine
from app.models import ParamValue


def _checks(template: str, **params):
    spec, _ = engine.generate(template, {k: ParamValue(value=v, source="user") for k, v in params.items()})
    return {check.id: check for check in spec.rule_checks}


def _apply(template: str, params: dict, patch: dict):
    return _checks(template, **{**params, **patch})


# --- STEP-004: risers at least 4 in ---------------------------------------------------------------------

def test_the_automatic_step_count_passes():
    assert _checks("step_platform", total_rise_in=21)["STEP-004"].status == "pass"


def test_too_many_forced_steps_fail_with_the_largest_count_that_works():
    params = {"total_rise_in": 21, "step_count": 12}  # 1-3/4 in risers
    check = _checks("step_platform", **params)["STEP-004"]
    assert check.status == "fail" and check.source_ref == "ada-504-2"
    assert check.detail.startswith('Riser height is 1-3/4"; guideline minimum is 4"')
    assert check.fix is not None and check.fix.params_patch == {"step_count": 5}  # 21 / 5 = 4.2 in
    fixed = _apply("step_platform", params, check.fix.params_patch)
    assert fixed["STEP-004"].status == "pass" and fixed["STEP-001"].status == "pass"


def test_a_rise_lower_than_one_step_suggests_a_ramp_without_a_fix():
    check = _checks("step_platform", total_rise_in=3)["STEP-004"]
    assert check.status == "fail" and check.fix is None
    assert "short ramp" in check.detail


def test_a_rise_no_step_count_can_fit_says_so_without_a_fix():
    # 7-1/2 in: one step is over 7 in, two steps are under 4 in.
    checks = _checks("step_platform", total_rise_in=7.5)
    assert checks["STEP-004"].status == "fail" and checks["STEP-004"].fix is None
    assert "no whole number of steps" in checks["STEP-004"].detail


# --- BED-004: no thin ripped top course -------------------------------------------------------------------

def test_the_default_bed_uses_full_boards():
    check = _checks("garden_bed")["BED-004"]
    assert check.status == "pass" and check.detail == "Every course is a full-width board"


def test_a_wide_enough_rip_passes():
    check = _checks("garden_bed", height_in=24)["BED-004"]  # top course ripped to 4 in
    assert check.status == "pass" and "4\"" in check.detail


def test_a_thin_rip_warns_and_lowers_the_bed_to_full_boards():
    params = {"height_in": 30}  # top course ripped to 3/4 in
    check = _checks("garden_bed", **params)["BED-004"]
    assert check.status == "warn" and check.source_ref == "thin-rip"
    assert '3/4" strip' in check.detail
    assert check.fix is not None and check.fix.params_patch == {"height_in": 29.25}
    fixed = _apply("garden_bed", params, check.fix.params_patch)
    assert fixed["BED-004"].status == "pass" and fixed["BED-001"].status == "pass"


def test_the_fix_raises_the_bed_when_lowering_would_leave_the_height_range():
    # 12 in with a cap: 9-1/4 + a 1-1/4 rip. Lowering to 10-3/4 is under the 15 in minimum, so raise to 20.
    params = {"height_in": 12}
    check = _checks("garden_bed", **params)["BED-004"]
    assert check.status == "warn" and check.fix.params_patch == {"height_in": 20.0}
    fixed = _apply("garden_bed", params, check.fix.params_patch)
    assert fixed["BED-004"].status == "pass" and fixed["BED-001"].status == "pass"
