"""NC-4: finding real Home Depot boards a cut list can be cut from.

The page text below is a trimmed copy of what Tavily really returned for the 2x6 pressure treated category
page on 2026-09-26. The network is faked only here, in automated tests.
"""

import json

import httpx
import pytest

from app.models import CutListRow
from app.nesting import BoardPiece, PieceTooLongError, nest_boards
from app.pricing import retail
from app.pricing.retail import Listing, RetailLookupError, best_by_length, find_boards, find_wood, nominal_of, parse_listing, plan_wood

P = "https://www.homedepot.ca/product/"
PAGE = f"""# 2 x 6 Pressure Treated Lumber

## [Pressure Treated 2 x 6 x 8' Premium Wood (Above Ground Use Only)]({P}pressure-treated-2-x-6-x-8-premium-wood-above-ground-use-only/1000790084 "x")

[Model # 10010036|SKU # 1000790084]({P}x/1000790084)

$17 And

21 Cents / each

1.    Out of Stock Online
2.    0 at [Check Nearby Stores](https://www.homedepot.ca/)

## [Pressure Treated 2 x 6 x 16' Premium Wood (Above Ground Use Only)]({P}pressure-treated-2-x-6-x-16-premium-wood-above-ground-use-only/1000790085 "x")

[Model # 10010049|SKU # 1000790085]({P}x/1000790085)

$32 And

96 Cents / each

## [MicroPro Sienna 2 x 6 x 14' Pressure Treated Wood (Above Ground Use Only)]({P}micropro-sienna-2-x-6-x-14-pressure-treated-wood-above-ground-use-only/1000790081 "x")

[Model # 10010046|SKU # 1000790081]({P}x/1000790081)

-

1.    Not Available for Delivery
2.     Not Sold in Stores

## [Cedartone Classic PT Lumber 2 inch x 6 inch x 10 ft.]({P}cedartone-classic-pt-lumber-2-inch-x-6-inch-x-10-ft/1000143669 "x")

[Model # 12345|SKU # 1000143669]({P}x/1000143669)

$21.50 / each

## [Pressure Treated 4 x 4 x 8' Premium Wood Post (Suitable for Ground Contact)]({P}pressure-treated-4-x-4-x-8-premium-wood-post/1000790178 "x")

[Model # 10010079|SKU # 1000790178]({P}x/1000790178)

$15 And

98 Cents / each

## [Pressure Treated 2 x 6 x 16' Premium Wood (Above Ground Use Only)]({P}pressure-treated-2-x-6-x-16-premium-wood-above-ground-use-only/1000790085 "x")

[Model # 10010049|SKU # 1000790085]({P}x/1000790085)

$99 And

99 Cents / each
"""


def listings():
    return parse_listing(PAGE, ("2", "6"))


def test_parse_reads_length_price_url_and_flags_from_real_page_text():
    by_sku = {item.sku: item for item in listings()}
    assert set(by_sku) == {"1000790084", "1000790085", "1000790081", "1000143669"}  # the 4x4 is another size
    eight = by_sku["1000790084"]
    assert (eight.length_in, eight.price_cad, eight.out_of_stock_online, eight.sold) == (96.0, 17.21, True, True)
    assert eight.url == P + "pressure-treated-2-x-6-x-8-premium-wood-above-ground-use-only/1000790084"
    assert by_sku["1000790085"].price_cad == 32.96  # the first block for a SKU wins; a repeat is ignored
    assert by_sku["1000143669"].length_in == 120.0 and by_sku["1000143669"].price_cad == 21.5  # "2 inch x 6 inch x 10 ft." and "$21.50"


def test_a_product_that_is_not_sold_has_no_price_and_is_flagged():
    item = next(i for i in listings() if i.sku == "1000790081")
    assert item.sold is False and item.price_cad is None and item.length_in == 168.0


def test_listings_come_back_shortest_first_and_other_sizes_are_left_out():
    assert [i.length_in for i in listings()] == [96.0, 120.0, 168.0, 192.0]
    assert [i.sku for i in parse_listing(PAGE, ("4", "4"))] == ["1000790178"]


def test_pages_with_no_products_parse_to_nothing():
    assert parse_listing("no products here", ("2", "6")) == []


def test_material_to_nominal_size():
    assert nominal_of("2x6_PT") == ("2", "6")
    assert nominal_of("5/4x6_PT_deck") == ("5/4", "6")


def test_sheets_have_no_board_size():
    with pytest.raises(RetailLookupError, match="no board size"):
        nominal_of("3/4_ext_ply")


def test_best_by_length_skips_unsold_and_unpriced_and_takes_the_cheapest_of_a_length():
    make = lambda sku, length, price, sold=True: Listing("t", sku, "u", length, price, False, sold)  # noqa: E731
    best = best_by_length([make("a", 96, 20.0), make("b", 96, 15.0), make("c", 120, None), make("d", 144, 30.0, sold=False), make("e", 192, 40.0)])
    assert {length: item.sku for length, item in best.items()} == {96: "b", 192: "e"}


def row(label, length_in, qty, material="2x6_PT"):
    return CutListRow(
        label=label, name=label, material=material, actual_dims="1-1/2 × 5-1/2", length_in=length_in,
        length_display=f"{length_in:g} in", qty=qty, part_ids=[f"{label}{i}" for i in range(qty)], cut_notes=[],
    )


def test_plan_wood_cuts_every_piece_from_boards_that_are_really_sold():
    plan = plan_wood("2x6_PT", [row("A", 90, 2), row("B", 60, 3), row("C", 30, 1)], listings())
    assert plan.problems == []
    assert {p.listing.length_in for p in plan.purchases} <= {96.0, 120.0, 192.0}  # never the unsold 14 ft board
    assert sum(len(board) for p in plan.purchases for board in p.boards) == 6  # every piece is placed once
    assert sum(p.qty for p in plan.purchases) == sum(len(p.boards) for p in plan.purchases)
    assert plan.total_cad == pytest.approx(sum(p.qty * p.listing.price_cad for p in plan.purchases), abs=0.005)
    assert any("out of stock online" in note for note in plan.notes) == any(p.listing.out_of_stock_online for p in plan.purchases)


def test_plan_wood_reports_a_piece_longer_than_any_listed_board():
    plan = plan_wood("2x6_PT", [row("A", 300, 1)], listings())
    assert plan.purchases == [] and "longest listed board: 16 ft" in plan.problems[0]


def test_plan_wood_with_nothing_buyable_says_so():
    unsold = [Listing("t", "1", "u", 96.0, None, False, False)]
    assert "currently sold" in plan_wood("2x6_PT", [row("A", 50, 1)], unsold).problems[0]


def test_nest_boards_uses_given_stock_lengths_and_defaults_are_unchanged():
    piece = [BoardPiece("p1", "A", "2x6_PT", 100.0)]
    assert nest_boards(piece)[0].length_in == 120.0  # the lumber data's lengths: 96, 120, 144, 168, 192
    assert nest_boards(piece, stock_lengths_in={"2x6_PT": [150.0, 300.0]})[0].length_in == 150.0
    assert nest_boards(piece, stock_lengths_in={"2x4_PT": [96.0]})[0].length_in == 120.0  # other materials keep the data
    with pytest.raises(PieceTooLongError, match="15 ft|180"):
        nest_boards([BoardPiece("p2", "B", "2x6_PT", 200.0)], stock_lengths_in={"2x6_PT": [96.0, 180.0]})


# --- the Tavily client, with a fake transport --------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(retail, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(retail, "RETRY_DELAYS_S", (0.0, 0.0))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def tavily(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        assert request.headers["authorization"] == "Bearer tvly-test-key"
        if request.url.path == "/search":
            # the category page only comes back for the second wording
            urls = [] if len(calls) == 1 else ["https://www.homedepot.ca/en/home/categories/x/pressure-treated-lumber/f/2-x-6/r88-rta"]
            return httpx.Response(200, json={"results": [{"url": u} for u in ["https://www.homedepot.ca/other", *urls]]})
        return httpx.Response(200, json={"results": [{"raw_content": PAGE}], "failed_results": []})

    return handler


def test_find_boards_retries_the_search_wording_and_caches_pages():
    calls = []
    http = client(tavily(calls))
    found = find_boards("2x6_PT", http)
    assert [i.sku for i in found] == ["1000790084", "1000143669", "1000790081", "1000790085"]
    assert [path for path, _ in calls] == ["/search", "/search", "/extract"]
    assert all(body["include_domains"] == ["homedepot.ca"] for path, body in calls if path == "/search")
    find_boards("2x6_PT", http)
    assert len(calls) == 3  # the second lookup is served from the cache


def test_missing_key_and_http_errors_are_reported_without_leaking_the_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY")
    with pytest.raises(RetailLookupError, match="TAVILY_API_KEY is not set"):
        find_boards("2x6_PT", client(lambda r: httpx.Response(200, json={})))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")
    with pytest.raises(RetailLookupError) as excinfo:
        find_boards("2x6_PT", client(lambda r: httpx.Response(432, text="usage limit tvly-test-key exceeded")))
    assert "432" in str(excinfo.value) and "tvly-test-key" not in str(excinfo.value)


def test_a_page_with_no_matching_products_is_an_error():
    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"url": "https://www.homedepot.ca/x/pressure-treated-lumber/f/2-x-6/r"}]})
        return httpx.Response(200, json={"results": [{"raw_content": "nothing"}]})

    with pytest.raises(RetailLookupError, match="lists no 2 x 6 boards"):
        find_boards("2x6_PT", client(handler))


def test_find_wood_reports_a_failed_material_and_skips_sheets():
    plans = find_wood([row("A", 60, 1), row("S", 48, 1, material="3/4_ext_ply")], client(lambda r: httpx.Response(500, text="down")))
    assert [p.material for p in plans] == ["2x6_PT"]  # the plywood sheet is not looked up
    assert plans[0].purchases == [] and "HTTP 500" in plans[0].problems[0]


def test_a_page_tavily_fails_to_read_once_is_retried():
    """Seen for real: one category page came back in failed_results, then read fine a moment later."""
    extracts = []

    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"url": "https://www.homedepot.ca/x/pressure-treated-lumber/f/2-x-6/r"}]})
        extracts.append(1)
        if len(extracts) == 1:
            return httpx.Response(200, json={"results": [], "failed_results": [{"url": "u", "error": "timeout"}]})
        return httpx.Response(200, json={"results": [{"raw_content": PAGE}], "failed_results": []})

    assert len(find_boards("2x6_PT", client(handler))) == 4 and len(extracts) == 2


def test_transient_server_errors_are_retried_but_client_errors_are_not():
    attempts = []

    def flaky(request):
        attempts.append(1)
        return httpx.Response(503, text="busy") if len(attempts) < 3 else httpx.Response(200, json={"results": []})

    retail._post(client(flaky), "/search", {})
    assert len(attempts) == 3
    attempts.clear()
    with pytest.raises(RetailLookupError, match="HTTP 401"):
        retail._post(client(lambda r: (attempts.append(1), httpx.Response(401, text="bad key"))[1]), "/search", {})
    assert len(attempts) == 1  # a bad key is not retried
    with pytest.raises(RetailLookupError, match="HTTP 503"):
        retail._post(client(lambda r: httpx.Response(503, text="down")), "/search", {})  # gives up after the last delay


def test_a_page_that_never_reads_gives_a_clear_error():
    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"url": "https://www.homedepot.ca/x/pressure-treated-lumber/f/2-x-6/r"}]})
        return httpx.Response(200, json={"results": [], "failed_results": [{"url": "u", "error": "timeout"}]})

    with pytest.raises(RetailLookupError, match="could not read"):
        find_boards("2x6_PT", client(handler))
