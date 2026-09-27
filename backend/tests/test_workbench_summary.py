"""The workbench's at-a-glance numbers (meta["summary"]) and its parameter-panel schema hints."""

import pytest

from app import engine
from app.models import ParamValue
from app.templates import params_schema
from app.templates.workbench import Params


def _summary(**params):
    spec, _ = engine.generate("workbench", {k: ParamValue(value=v, source="user") for k, v in params.items()})
    return {fact["label"]: fact for fact in spec.meta["summary"]}


def test_default_bench_with_shelf():
    s = _summary()
    assert list(s) == ["Top", "Working height", "Legs", "Lower shelf", "Clear space under the top", "Footprint"]
    assert s["Top"]["value"] == "4' 0\" × 2' 0\" (width × depth)"
    assert s["Top"]["detail"] == "cut from 25% of one 4' 0\" × 8' 0\" sheet of 3/4 exterior plywood"
    assert s["Working height"]["value"] == "2' 10\""
    assert s["Legs"]["value"] == "4 × 4x4 pressure-treated"
    assert s["Legs"]["detail"] == "each 2' 9-5/16\" long"  # 34 - 0.703 top = 33.297
    assert s["Lower shelf"]["value"] == "10\" off the floor"
    assert s["Clear space under the top"]["value"] == "1' 7-13/16\""  # 34 - 0.703 - 3.5 apron - 10 = 19.797
    assert s["Footprint"]["value"] == "4' 0\" × 2' 0\""
    assert s["Footprint"]["detail"] == "the top overhangs the legs by 3/4\" on every side"


def test_bench_without_shelf_says_so_and_has_no_clear_space():
    s = _summary(lower_shelf=False, height_in=30)
    assert s["Lower shelf"]["value"] == "None"
    assert "Clear space under the top" not in s
    assert s["Working height"]["value"] == "2' 6\""
    assert s["Legs"]["detail"] == "each 2' 5-5/16\" long"  # 30 - 0.703 = 29.297


def test_widest_top_uses_a_whole_sheet():
    s = _summary(width_in=96, depth_in=48)
    assert s["Top"]["value"] == "8' 0\" × 4' 0\" (width × depth)"
    assert s["Top"]["detail"] == "cut from a whole 4' 0\" × 8' 0\" sheet of 3/4 exterior plywood"
    assert s["Footprint"]["value"] == "8' 0\" × 4' 0\""


def test_schema_groups_and_plain_titles():
    props = params_schema(Params)["properties"]
    assert [name for name, prop in props.items() if prop.get("group") == "key"] == ["width_in", "depth_in", "height_in"]
    assert props["lower_shelf"]["group"] == "advanced"
    assert {name: prop["title"] for name, prop in props.items()} == {
        "width_in": "Width",
        "depth_in": "Depth",
        "height_in": "Working-surface height",
        "lower_shelf": "Lower shelf",
        "shelf_height_in": "Shelf height",
    }
    for prop in props.values():
        assert "(" not in prop["title"] and "inferred" not in prop["description"]


def test_the_shelf_height_can_be_changed():
    s = _summary(shelf_height_in=18)
    assert s["Lower shelf"]["value"] == '18" off the floor'
    # top underside 34 - 0.703 = 33.297, minus the 3-1/2 in apron = 29.797, minus the 18 in shelf = 11.797
    assert s["Clear space under the top"]["value"] == "11-13/16\""


def test_a_shelf_too_close_to_the_top_names_the_highest_that_fits():
    from app.engine_errors import ParamValidationError
    from app.templates.workbench import Params, derive

    with pytest.raises(ParamValidationError, match="The highest shelf that fits is 23-13/16 in"):
        derive(Params(shelf_height_in=24))
    assert derive(Params(shelf_height_in=24, lower_shelf=False)).has_shelf is False  # ignored without a shelf
