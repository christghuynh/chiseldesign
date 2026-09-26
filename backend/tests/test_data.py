"""GEO-1: the lumber and price reference data."""

import pytest

from app.data import lumber, lumber_spec, prices


def test_lumber_uses_actual_not_nominal_dimensions():
    assert (lumber_spec("2x6_PT").thickness_in, lumber_spec("2x6_PT").width_in) == (1.5, 5.5)
    assert (lumber_spec("4x4_PT").thickness_in, lumber_spec("4x4_PT").width_in) == (3.5, 3.5)
    assert lumber_spec("5/4x6_PT_deck").thickness_in == 1.0
    assert lumber_spec("2x8_PT").width_in == 7.25 and lumber_spec("2x10_PT").width_in == 9.25


def test_stock_lengths_match_the_agreed_table():
    assert lumber_spec("2x4_PT").stock_lengths_in == [96, 120, 144]
    assert lumber_spec("2x6_PT").stock_lengths_in == [96, 120, 144, 168, 192]
    assert lumber_spec("2x10_PT").stock_lengths_in == [96, 120, 144]
    assert lumber_spec("4x4_PT").stock_lengths_in == [96, 120]
    assert lumber_spec("2x6_PT").max_stock_length_in == 192


def test_plywood_is_a_sheet():
    ply = lumber_spec("3/4_ext_ply")
    assert ply.kind == "sheet" and ply.thickness_in == 0.703
    assert ply.sheet_size_in == (48, 96) and ply.max_stock_length_in == 96


def test_unknown_material_has_a_helpful_error():
    with pytest.raises(KeyError, match="Unknown material"):
        lumber_spec("2x99")


def test_every_purchasable_item_has_a_price():
    all_prices = prices()
    for key, spec in lumber().items():
        if spec.kind == "board":
            for length in spec.stock_lengths_in:
                assert f"{key}_{int(length)}" in all_prices, key
        else:
            width, length = spec.sheet_size_in
            assert f"{key}_{int(width)}x{int(length)}" in all_prices
    for key in ("deck_screws_box", "structural_screws_box", "joist_hanger", "post_base"):
        assert key in all_prices


def test_prices_are_placeholders_until_nc4():
    """Flip this when real retailer prices replace the placeholders (task NC-4)."""
    assert all(p.placeholder for p in prices().values())
    assert all("placeholder price" in p.description for p in prices().values())


def test_fastener_boxes_say_how_many_pieces_they_hold():
    assert prices()["deck_screws_box"].units_per_pack and prices()["structural_screws_box"].units_per_pack
