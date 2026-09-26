"""GEO-7: the ramp build-step skeleton."""

import pytest

from app.models import SkeletonStep
from app.templates.ramp import Params, build_skeleton, derive
from app.templates.ramp_parts import build_parts
from app.templates.ramp_skeleton import STEPS, build_skeleton_steps
from tests.test_ramp_support import make

ORDER = [key for key, *_ in STEPS]
STRAIGHT_FULL = ["prepare_site", "cut_stringers", "cut_ledger", "attach_ledger", "set_stringers", "check_slope", "install_decking", "install_curbs", "install_handrails", "final_check"]


def labeled(parts):
    """Stand-in for the cut list's labels: one letter per part name, in first-seen order."""
    letters: dict[str, str] = {}
    out = []
    for p in parts:
        label = letters.setdefault(p.name, chr(ord("A") + len(letters)))
        out.append(p.model_copy(update={"label": label, "id": f"{label}-{len(out) + 1}"}))
    return out


def keys(steps):
    return [s.action_key for s in steps]


def test_order_list_matches_the_spec():
    assert ORDER == ["prepare_site", "cut_stringers", "cut_ledger", "cut_landing_framing", "build_landings", "attach_ledger", "set_stringers", "check_slope", "install_decking", "install_curbs", "install_handrails", "final_check"]


def test_straight_ramp_with_everything_has_the_exact_action_keys():
    params, _, parts = make(total_rise_in=12)
    steps = build_skeleton_steps(params, labeled(parts))
    assert keys(steps) == STRAIGHT_FULL
    assert all(isinstance(s, SkeletonStep) for s in steps)
    by_key = {s.action_key: s for s in steps}
    assert {k: s.phase for k, s in by_key.items()} == {
        "prepare_site": "prep", "cut_stringers": "cut", "cut_ledger": "cut", "attach_ledger": "assemble", "set_stringers": "assemble",
        "check_slope": "check", "install_decking": "install", "install_curbs": "install", "install_handrails": "install", "final_check": "check",
    }  # fmt: skip
    assert by_key["cut_stringers"].title == "Cut all stringers"
    assert by_key["prepare_site"].part_labels == [] and by_key["final_check"].part_labels == []


def test_part_labels_belong_to_the_right_parts_and_exist():
    params, _, parts = make(total_rise_in=20, layout="switchback")
    parts = labeled(parts)
    existing = {p.label for p in parts}
    label_of = {p.name: p.label for p in parts}
    for step in build_skeleton_steps(params, parts):
        assert set(step.part_labels) <= existing
        assert step.part_labels == sorted(set(step.part_labels))
    by_key = {s.action_key: s for s in build_skeleton_steps(params, parts)}
    assert by_key["cut_stringers"].part_labels == [label_of["Stringer"]]
    assert by_key["attach_ledger"].part_labels == [label_of["Ledger"]]
    assert by_key["install_curbs"].part_labels == [label_of["Edge curb"]]
    assert by_key["install_handrails"].part_labels == sorted({label_of["Handrail post"], label_of["Handrail"]})
    assert by_key["install_decking"].part_labels == sorted({label_of["Deck board"], label_of["Landing deck board"]})
    assert label_of["Landing post"] in by_key["build_landings"].part_labels


def test_switchback_has_the_landing_steps_in_order():
    params, _, parts = make(total_rise_in=20, layout="switchback")
    assert keys(build_skeleton_steps(params, labeled(parts))) == [
        "prepare_site", "cut_stringers", "cut_ledger", "cut_landing_framing", "build_landings", "attach_ledger",
        "set_stringers", "check_slope", "install_decking", "install_curbs", "install_handrails", "final_check",
    ]  # fmt: skip


def test_straight_ramp_with_an_intermediate_landing_has_landing_steps_too():
    params, _, parts = make(total_rise_in=31, layout="straight")
    assert "build_landings" in keys(build_skeleton_steps(params, labeled(parts)))


def test_no_handrail_step_without_handrails():
    params, _, parts = make(total_rise_in=12, handrails="no")
    assert "install_handrails" not in keys(build_skeleton_steps(params, labeled(parts)))
    params, _, parts = make(total_rise_in=4)  # auto and under the threshold
    assert "install_handrails" not in keys(build_skeleton_steps(params, labeled(parts)))


def test_no_curb_step_without_curbs():
    params, _, parts = make(total_rise_in=12, edge_curb=False)
    assert "install_curbs" not in keys(build_skeleton_steps(params, labeled(parts)))


def test_stringerless_ramp_has_no_stringer_or_ledger_steps():
    params, _, parts = make(total_rise_in=2)
    assert keys(build_skeleton_steps(params, labeled(parts))) == ["prepare_site", "install_decking", "install_curbs", "final_check"]


def test_works_with_the_temporary_label_from_build_parts():
    params = Params(total_rise_in=12)
    parts = build_parts(params, derive(params))
    assert {p.label for p in parts} == {"T"}
    steps = build_skeleton_steps(params, parts)
    assert keys(steps) == STRAIGHT_FULL
    assert [s.part_labels for s in steps if s.part_labels] == [["T"]] * 8


def test_deterministic_and_reachable_through_the_template_interface():
    params = Params(total_rise_in=31, layout="straight")
    parts = labeled(build_parts(params, derive(params)))
    assert build_skeleton_steps(params, parts) == build_skeleton_steps(params, list(parts))
    assert build_skeleton(params, parts) == build_skeleton_steps(params, parts)


@pytest.mark.parametrize("overrides", [{"total_rise_in": r, "layout": lay} for r in (3, 8, 14, 25, 45) for lay in ("straight", "switchback", "auto")])
def test_steps_always_follow_the_fixed_order(overrides):
    from app.engine_errors import ParamValidationError

    try:
        params, _, parts = make(**overrides)
    except ParamValidationError:
        return
    ks = keys(build_skeleton_steps(params, labeled(parts)))
    assert ks[0] == "prepare_site" and ks[-1] == "final_check"
    assert ks == [k for k in ORDER if k in ks]
    assert len(set(ks)) == len(ks)
