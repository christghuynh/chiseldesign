"""The step platform's top platform: frame, posts, deck, stringers butting it, summary, shopping and build steps."""

import pytest

from app import engine
from app.engine_errors import ParamValidationError
from app.models import ParamValue, Part
from app.templates import step_platform as sp

RISER_T = 1.5  # 2x8 / 2x10 thickness
TREAD = 11.0


def _generate(**params):
    return engine.generate("step_platform", {k: ParamValue(value=v, source="user") for k, v in params.items()})


def _named(parts: list[Part], prefix: str) -> list[Part]:
    return [p for p in parts if p.name.startswith(prefix)]


def _x_range(part: Part) -> tuple[float, float]:
    xs = [x for x, _ in part.profile]
    return part.transform.pos[0] + min(xs), part.transform.pos[0] + max(xs)


def _y_top(part: Part) -> float:
    return part.transform.pos[1] + max(y for _, y in part.profile)


def test_default_steps_climb_onto_a_framed_platform():
    spec, _ = _generate(total_rise_in=21)
    d = sp.derive(sp.Params(total_rise_in=21))
    assert d.has_platform and d.riser_count == 3
    # 36 in rounded up to whole 5-1/2 in deck boards with 1/8 in gaps: 7 boards = 39-1/4 in
    assert (d.platform_deck_boards, d.platform_depth_in) == (7, 39.25)
    front = (d.riser_count - 1) * TREAD + RISER_T  # back face of the top riser
    deck = _named(spec.parts, "Landing deck board")
    assert len(deck) == 7 and all(_y_top(p) == pytest.approx(21) for p in deck)  # flush with the top step
    assert min(_x_range(p)[0] for p in deck) == pytest.approx(front)
    assert len(_named(spec.parts, "Landing rim (side)")) == 2 and len(_named(spec.parts, "Landing rim (end)")) == 2
    assert len(_named(spec.parts, "Landing joist")) == 2  # 33 in inside, joists at 16 in or less
    posts = _named(spec.parts, "Landing post")
    assert len(posts) == 4 and all(_y_top(p) == pytest.approx(20) for p in posts)  # ground to the underside of the deck
    # The stringers stop at the platform instead of running under it.
    stringers = _named(spec.parts, "Stringer")
    assert stringers and max(_x_range(p)[1] for p in stringers) == pytest.approx(front)


def test_summary_describes_the_platform_and_the_whole_length():
    spec, _ = _generate(total_rise_in=21)
    s = {f["label"]: f for f in spec.meta["summary"]}
    assert s["Each step"]["detail"] == "the top step is the top platform"
    assert s["Top platform"]["value"] == "3' 3-1/4\" deep × 3' 0\" wide"
    assert s["Top platform"]["detail"] == "7 deck boards on a 2x6 frame, 4 posts"
    # 2 treads (22) + the top riser (1-1/2) + the platform (39-1/4) = 62-3/4
    assert s["Space needed"]["value"] == "5' 2-3/4\" long × 3' 0\" wide"


def test_a_low_platform_rips_its_frame_and_sits_on_the_ground():
    spec, _ = _generate(total_rise_in=5)
    d = sp.derive(sp.Params(total_rise_in=5))
    assert d.platform_frame_rip_in == pytest.approx(4.0) and d.platform_post_count == 0
    assert not _named(spec.parts, "Landing post")
    assert all(p.cut_notes == ["Rip to 4 in wide"] for p in _named(spec.parts, "Landing rim"))
    s = {f["label"]: f for f in spec.meta["summary"]}
    assert s["Top platform"]["detail"].endswith("ripped to 4\", sitting on the ground")


def test_a_rise_too_low_for_any_frame_says_to_turn_the_platform_off():
    with pytest.raises(ParamValidationError, match="Turn Top platform off"):
        sp.derive(sp.Params(total_rise_in=2))
    assert not sp.derive(sp.Params(total_rise_in=2, top_platform=False)).has_platform


def test_platform_depth_rounds_up_to_whole_deck_boards():
    d = sp.derive(sp.Params(total_rise_in=21, platform_depth_in=24))
    assert (d.platform_deck_boards, d.platform_depth_in) == (5, 28.0)


def test_the_shopping_list_counts_joist_hangers_and_post_bases():
    _, plan = _generate(total_rise_in=21)
    qty = {item.key: item.qty for item in plan.shopping}
    assert qty.get("post_base") == 4
    assert qty.get("joist_hanger") == 4  # 2 joists x 2 ends


def test_the_build_steps_include_the_platform():
    spec, _ = _generate(total_rise_in=21)
    titles = [step.title for step in sp.build_skeleton(sp.Params(total_rise_in=21), spec.parts)]
    assert titles.index("Build the top platform frame") < titles.index("Set the stringers")
    assert "Deck the top platform" in titles


def test_turning_it_off_builds_steps_up_to_a_porch():
    spec, _ = _generate(total_rise_in=21, top_platform=False)
    assert not _named(spec.parts, "Landing")
    s = {f["label"]: f for f in spec.meta["summary"]}
    assert "Top platform" not in s and s["Each step"]["detail"] == "the top step is the porch"
