"""The garden bed's at-a-glance numbers (meta["summary"]) and its parameter-panel schema hints."""

from app import engine
from app.models import ParamValue
from app.templates import params_schema
from app.templates.garden_bed import Params


def _summary(**params):
    spec, _ = engine.generate("garden_bed", {k: ParamValue(value=v, source="user") for k, v in params.items()})
    return {fact["label"]: fact for fact in spec.meta["summary"]}


def test_default_bed():
    s = _summary()
    assert s["Outer size"]["value"] == "6' 0\" × 2' 0\" × 2' 6\""
    assert s["Outer size"]["detail"].endswith("including the cap rail")
    # 30 - 1-1/2 cap = 28-1/2 of courses: three 9-1/4 boards and a 3/4 rip
    assert s["Board courses"]["value"] == "4 courses of 2x10 pressure-treated"
    assert s["Board courses"]["detail"] == "3 full width, top one ripped to 3/4\" wide"
    # inside 69 x 21 x 28-1/2 = 41296.5 cu in = 23.9 cu ft = 0.89 cu yd
    assert s["Soil needed"]["value"] == "23.9 cu ft (0.89 cu yd)"
    assert s["Soil needed"]["detail"] == "inside 5' 9\" × 1' 9\" × 2' 4-1/2\" (length × width × depth)"
    assert s["Reach"]["value"] == "2' 0\" from the front"
    assert s["Reach"]["detail"] == "within the 2' 0\" comfortable reach guideline"
    assert s["Seat height"]["value"] == "2' 6\""
    assert s["Corner posts"]["value"] == "4 × 4x4, 2' 4-1/2\" tall"
    assert s["Longest board"]["value"] == "6' 0\" 2x6"
    assert s["Longest board"]["detail"] == "longest 2x6 sold is 16' 0\""


def test_both_sides_bed_halves_the_reach():
    s = _summary(access="both_sides", width_in=36)
    assert s["Reach"]["value"] == "1' 6\" from each long side"
    assert s["Reach"]["detail"].startswith("within")
    # inside 69 x 33 x 28-1/2 = 64894.5 cu in = 37.6 cu ft = 1.39 cu yd
    assert s["Soil needed"]["value"] == "37.6 cu ft (1.39 cu yd)"


def test_too_wide_for_one_side_is_beyond_the_guideline():
    s = _summary(width_in=36)
    assert s["Reach"]["value"] == "3' 0\" from the front"
    assert s["Reach"]["detail"] == "beyond the 2' 0\" comfortable reach guideline"


def test_bed_without_cap_rail():
    s = _summary(cap_rail=False, board="2x8_PT", height_in=29, length_in=96)
    assert "Seat height" not in s
    assert s["Outer size"]["detail"] == "length × width × height, outside faces"
    # 29 = four 7-1/4 boards exactly, so nothing is ripped
    assert s["Board courses"]["value"] == "4 courses of 2x8 pressure-treated"
    assert s["Board courses"]["detail"] == "all full-width boards"
    # inside 93 x 21 x 29 = 56637 cu in = 32.8 cu ft = 1.21 cu yd
    assert s["Soil needed"]["value"] == "32.8 cu ft (1.21 cu yd)"
    assert s["Corner posts"]["value"] == "4 × 4x4, 2' 5\" tall"
    assert s["Corner posts"]["detail"] == "flush with the top course"
    # the long side course, 96 - 2 x 3-1/2 posts = 89
    assert s["Longest board"]["value"] == "7' 5\" 2x8"


def test_schema_marks_key_dimensions_and_labels_choices():
    props = params_schema(Params)["properties"]
    key = [name for name, prop in props.items() if prop.get("group") == "key"]
    assert key == ["length_in", "width_in", "height_in"]
    advanced = [name for name, prop in props.items() if prop.get("group") == "advanced"]
    assert advanced == ["access", "board", "cap_rail"]
    for prop in props.values():
        assert "(" not in prop["title"]
        if "enum" in prop:
            assert set(prop["enum_labels"]) == set(prop["enum"])
    assert props["access"]["enum_labels"]["one_side"] == "One side (against a wall)"
    assert props["board"]["enum_labels"]["2x10_PT"] == "2x10 pressure-treated"
