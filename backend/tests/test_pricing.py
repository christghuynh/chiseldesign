"""GEO-13: shopping list and totals."""

import pytest

from app import data
from app.cutlist import build_cut_list, label_parts
from app.models import PlacedPiece, ShoppingItem, StockLayout
from app.nesting import BoardPiece, nest_boards
from app.pricing import build_shopping_list, hardware_quantities, lumber_price_key, price_totals
from tests.geo_helpers import SPEC_FILES, load_fixture, make_part, rect_profile


def board_layout(material: str, length: float, n: int = 1) -> StockLayout:
    return StockLayout(
        stock_id=f"{material}_{int(length)}-{n}",
        material=material,
        kind="board",
        length_in=length,
        width_in=5.5,
        pieces=[PlacedPiece(label="A", part_id=f"A-{n}", x=0, y=0, w=10, h=5.5)],
        utilization=10 / length,
    )


def sheet_layout(n: int = 1) -> StockLayout:
    return StockLayout(
        stock_id=f"3/4_ext_ply_48x96-{n}",
        material="3/4_ext_ply",
        kind="sheet",
        length_in=96,
        width_in=48,
        pieces=[PlacedPiece(label="A", part_id=f"A-{n}", x=0, y=0, w=10, h=10)],
        utilization=100 / (48 * 96),
    )


def deck(group="run_1", **kw):
    return make_part(name="Deck board", material="5/4x6_PT_deck", profile=rect_profile(5.5, 1.0), thickness=36.0, group=group, **kw)


def stringer(group="run_1"):
    return make_part(name="Stringer", group=group)


def joist(group="landing"):
    return make_part(name="Landing joist", group=group)


def post():
    return make_part(name="Handrail post", material="4x4_PT", profile=rect_profile(3.5, 3.5), thickness=36.0, group="handrail")


def by_key(items):
    return {i.key: i for i in items}


# --- lumber lines -------------------------------------------------------------------------------


def test_lumber_lines_count_layouts_per_material_and_length():
    layouts = [board_layout("2x6_PT", 144, 1), board_layout("2x6_PT", 144, 2), board_layout("2x6_PT", 96), board_layout("2x4_PT", 96)]
    items = build_shopping_list(layouts, [])
    assert [(i.key, i.qty) for i in items] == [("2x4_PT_96", 1), ("2x6_PT_96", 1), ("2x6_PT_144", 2)]
    line = by_key(items)["2x6_PT_144"]
    price = data.prices()["2x6_PT_144"]
    assert (line.unit_price, line.subtotal, line.unit, line.source_url) == (price.price_cad, round(2 * price.price_cad, 2), "each", price.source_url)


def test_sheet_lines_use_the_width_x_length_key():
    assert lumber_price_key(sheet_layout()) == "3/4_ext_ply_48x96"
    items = build_shopping_list([sheet_layout(1), sheet_layout(2)], [])
    assert [(i.key, i.qty, i.unit) for i in items] == [("3/4_ext_ply_48x96", 2, "sheet")]


def test_missing_price_names_the_key():
    with pytest.raises(KeyError, match="2x6_PT_100"):
        build_shopping_list([board_layout("2x6_PT", 100)], [])


# --- hardware -----------------------------------------------------------------------------------


def test_deck_screws_count_crossings_per_group():
    # run_1: 2 stringers x 3 deck boards = 6 crossings; landing: 3 joists x 2 boards = 6 -> 12 crossings x 2 screws
    parts = [stringer(), stringer(), deck(), deck(), deck(), joist(), joist(), joist(), deck("landing"), deck("landing")]
    assert hardware_quantities(parts)["deck_screws_box"] == 1  # 24 screws -> the one-box minimum
    many = [stringer(), stringer()] + [deck() for _ in range(90)]  # 90 x 2 x 2 = 360 screws > 350 -> 2 boxes
    assert hardware_quantities(many)["deck_screws_box"] == 2
    exactly = [stringer(), stringer()] + [deck() for _ in range(87)]  # 348 screws
    assert hardware_quantities(exactly)["deck_screws_box"] == 1


def test_hardware_counts_for_a_known_small_case():
    parts = [stringer(), stringer(), deck(), deck(), deck(), joist(), joist(), joist(), deck("landing"), post(), post()]
    # deck crossings: 3 boards x 2 stringers + 1 landing board x 3 joists = 9 -> 18 screws -> 1 box
    # hangers: 3 joists x 2 = 6; structural screws 6 x 8 = 48 -> 1 box (50 per box); posts 2 -> 2 bases
    assert hardware_quantities(parts) == {"deck_screws_box": 1, "joist_hanger": 6, "post_base": 2, "structural_screws_box": 1}
    items = by_key(build_shopping_list([], parts))
    assert [i.key for i in build_shopping_list([], parts)] == ["deck_screws_box", "joist_hanger", "post_base", "structural_screws_box"]
    assert items["joist_hanger"].qty == 6 and items["joist_hanger"].subtotal == round(6 * data.prices()["joist_hanger"].price_cad, 2)
    assert items["deck_screws_box"].unit == "box"


def test_structural_screw_boxes_round_up():
    four_joists = [joist() for _ in range(4)]  # 8 hangers x 8 = 64 screws -> 2 boxes of 50
    assert hardware_quantities(four_joists)["structural_screws_box"] == 2


def test_only_handrail_and_landing_4x4_posts_get_a_post_base():
    parts = [post(), make_part(name="Handrail post", material="2x4_PT"), make_part(name="Landing post", material="4x4_PT"), make_part(name="Brace", material="4x4_PT")]
    assert hardware_quantities(parts)["post_base"] == 2


def test_garden_bed_corner_posts_and_workbench_legs_need_no_post_base():
    parts = [make_part(name="Corner post", material="4x4_PT"), make_part(name="Leg", material="4x4_PT")]
    assert "post_base" not in hardware_quantities(parts)


def test_step_treads_are_screwed_to_the_stringers_even_in_another_group():
    parts = [make_part(name="Stringer", group="frame"), make_part(name="Stringer", group="frame"),
             make_part(name="Tread board", material="5/4x6_PT_deck", group="treads"), make_part(name="Tread board", material="5/4x6_PT_deck", group="treads")]
    assert hardware_quantities(parts)["deck_screws_box"] == 1  # 2 boards x 2 stringers x 2 screws = 8 screws, one box
    from app.pricing.shopping import _crossings

    assert _crossings(parts) == 4


def test_lines_with_zero_quantity_are_omitted():
    assert build_shopping_list([], []) == []
    parts = [make_part(name="Ledger")]  # no deck boards, joists or posts
    assert build_shopping_list([board_layout("2x6_PT", 96)], parts) == build_shopping_list([board_layout("2x6_PT", 96)], [])
    assert [i.key for i in build_shopping_list([board_layout("2x6_PT", 96)], parts)] == ["2x6_PT_96"]
    only_posts = build_shopping_list([], [post()])
    assert [i.key for i in only_posts] == ["post_base"]
    assert all(i.qty > 0 for i in only_posts)


def test_deck_boards_without_supports_still_buy_the_minimum_box():
    assert hardware_quantities([deck()]) == {"deck_screws_box": 1}


# --- totals -------------------------------------------------------------------------------------


def item(subtotal: float) -> ShoppingItem:
    return ShoppingItem(key="k", description="d", unit="each", qty=1, unit_price=subtotal, subtotal=subtotal, source_url=None)


def test_totals_add_up_and_tax_is_13_percent():
    subtotal, tax, total, savings = price_totals([item(10.10), item(20.20), item(0.05)], None)
    assert subtotal == 30.35
    assert tax == round(30.35 * 0.13, 2) == 3.95
    assert total == round(subtotal + tax, 2) == 34.30
    assert savings is None


@pytest.mark.parametrize("amounts", [[], [0.01], [99.99, 0.01], [12.34, 56.78, 90.12]])
def test_tax_is_exactly_the_rounded_13_percent(amounts):
    subtotal, tax, total, _ = price_totals([item(a) for a in amounts], None)
    assert subtotal == round(sum(amounts), 2)
    assert tax == round(subtotal * 0.13, 2)
    assert total == round(subtotal + tax, 2)


def test_savings_only_with_a_quote():
    items = [item(100.0)]
    assert price_totals(items, None)[3] is None
    assert price_totals(items, 500.0)[3] == round(500.0 - 113.0, 2)
    assert price_totals(items, 50.0)[3] == -63.0  # a quote below the total is a negative saving, not hidden
    assert price_totals(items, 0.0)[3] == -113.0  # 0 is a real quote, not "no quote"


def test_totals_of_a_real_shopping_list_add_up():
    parts = [stringer(), stringer(), deck(), deck(), post()]
    items = build_shopping_list([board_layout("2x6_PT", 144), sheet_layout()], parts)
    subtotal, tax, total, savings = price_totals(items, 1000.0)
    assert subtotal == round(sum(i.subtotal for i in items), 2)
    assert total == round(subtotal + tax, 2)
    assert savings == round(1000.0 - total, 2)


# --- prices.json drives everything --------------------------------------------------------------


def test_changing_a_price_changes_the_total(monkeypatch):
    layouts = [board_layout("2x6_PT", 144)]
    before = price_totals(build_shopping_list(layouts, [post()]), None)
    patched = {k: v.model_copy() for k, v in data.prices().items()}
    patched["2x6_PT_144"] = patched["2x6_PT_144"].model_copy(update={"price_cad": 100.0})
    patched["post_base"] = patched["post_base"].model_copy(update={"price_cad": 50.0})
    monkeypatch.setattr(data, "prices", lambda: patched)
    items = build_shopping_list(layouts, [post()])
    assert by_key(items)["2x6_PT_144"].unit_price == 100.0
    after = price_totals(items, None)
    assert after[0] == 150.0 and after[0] != before[0]
    assert after[2] > before[2]


def test_placeholder_text_is_preserved():
    items = build_shopping_list([board_layout("2x6_PT", 144), sheet_layout()], [post(), deck(), stringer()])
    assert items
    for i in items:
        assert i.description == data.prices()[i.key].description
        assert "placeholder price" in i.description  # while the entry is still a placeholder


def test_deterministic_and_independent_of_layout_order():
    layouts = [board_layout("2x6_PT", 144, 1), board_layout("2x4_PT", 96), sheet_layout(), board_layout("2x6_PT", 96)]
    parts = [stringer(), deck(), joist(), post()]
    first = build_shopping_list(layouts, parts)
    assert build_shopping_list(layouts, parts) == first
    assert build_shopping_list(list(reversed(layouts)), list(reversed(parts))) == first


@pytest.mark.parametrize("name", SPEC_FILES)
def test_fixture_ramps_have_sensible_shopping_lists(name):
    parts = label_parts(load_fixture(name).spec.parts)
    rows = build_cut_list(parts)
    pieces = [BoardPiece(pid, r.label, r.material, r.length_in) for r in rows for pid in r.part_ids]
    items = build_shopping_list(nest_boards(pieces), parts)
    keys = [i.key for i in items]
    assert len(keys) == len(set(keys))
    assert {"deck_screws_box", "post_base"} <= set(keys)
    assert all(i.qty > 0 and i.subtotal == round(i.qty * i.unit_price, 2) for i in items)
