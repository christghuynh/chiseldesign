"""Shopping list and totals (GEO-13).

Lumber lines come from the nesting layouts (one board or sheet per layout); hardware lines are counted
from the parts. Prices come from prices.json via `app.data.prices()`, looked up at call time.
"""

import math
from collections import Counter

from app import data
from app.models import Part, ShoppingItem, StockLayout
from app.pricing import constants as c


def lumber_price_key(layout: StockLayout) -> str:
    """`2x6_PT_144` for a board, `3/4_ext_ply_48x96` (width x length) for a sheet."""
    if layout.kind == "sheet":
        return f"{layout.material}_{int(layout.width_in)}x{int(layout.length_in)}"
    return f"{layout.material}_{int(layout.length_in)}"


def _crossings(parts: list[Part]) -> int:
    """Deck-board-to-support crossings: each deck board crosses every support in its `group`."""
    supports = Counter(p.group for p in parts if p.name in c.SUPPORT_NAMES)
    return sum(supports[p.group] for p in parts if c.DECK_BOARD_TEXT in p.name.lower())


def _boxes(count: int, key: str, used: bool) -> int:
    """Packs to buy for `count` pieces (ceil), at least the minimum when the fastener is used at all."""
    if not used:
        return 0
    per_pack = data.prices()[key].units_per_pack or 1
    return max(math.ceil(count / per_pack), c.MIN_BOXES_PER_FASTENER)


def hardware_quantities(parts: list[Part]) -> dict[str, int]:
    """Quantity to buy per hardware price key (only keys with qty > 0), from the parts alone.

    Deck screws: crossings x DECK_SCREWS_PER_CROSSING, in boxes; a build with any deck board buys at
    least one box even when no support is found. Joist hangers: 2 per "Landing joist". Post bases: one
    per 4x4 part named like a post. Structural screws: per joist hanger, in boxes.
    """
    has_deck = any(c.DECK_BOARD_TEXT in p.name.lower() for p in parts)
    screws = _crossings(parts) * c.DECK_SCREWS_PER_CROSSING
    joists = sum(1 for p in parts if p.name == c.JOIST_NAME)
    hangers = joists * c.JOIST_ENDS * c.JOIST_HANGERS_PER_JOIST_END
    posts = sum(1 for p in parts if p.material == c.POST_MATERIAL and c.POST_TEXT in p.name.lower())
    quantities = {
        c.DECK_SCREWS_KEY: _boxes(screws, c.DECK_SCREWS_KEY, has_deck),
        c.JOIST_HANGER_KEY: hangers,
        c.POST_BASE_KEY: posts * c.POST_BASES_PER_POST,
        c.STRUCTURAL_SCREWS_KEY: _boxes(hangers * c.STRUCTURAL_SCREWS_PER_HANGER, c.STRUCTURAL_SCREWS_KEY, hangers > 0),
    }
    return {key: quantities[key] for key in c.HARDWARE_ORDER if quantities[key] > 0}


def _item(key: str, qty: int) -> ShoppingItem:
    try:
        entry = data.prices()[key]
    except KeyError:
        raise KeyError(f"No price for {key!r} in prices.json") from None
    return ShoppingItem(
        key=key,
        description=entry.description,
        unit=entry.unit,
        qty=qty,
        unit_price=entry.price_cad,
        subtotal=round(qty * entry.price_cad, 2),
        source_url=entry.source_url,
    )


def build_shopping_list(layouts: list[StockLayout], parts: list[Part]) -> list[ShoppingItem]:
    """Lumber (one line per material and stock length) then hardware; lines with qty 0 are left out.

    Lumber is ordered by material key then length (sheets by width x length), hardware in the fixed
    order deck screws, joist hangers, post bases, structural screws. Raises KeyError naming the price
    key if prices.json has no entry for something that must be bought.
    """
    lumber: Counter[tuple[str, float, str]] = Counter()
    for layout in layouts:
        lumber[(layout.material, layout.length_in, lumber_price_key(layout))] += 1
    items = [_item(key, qty) for (_, _, key), qty in sorted(lumber.items()) if qty > 0]
    items += [_item(key, qty) for key, qty in hardware_quantities(parts).items() if qty > 0]
    return items


def price_totals(items: list[ShoppingItem], contractor_quote: float | None) -> tuple[float, float, float, float | None]:
    """(subtotal, tax, total, savings), all rounded to 2 decimals.

    tax is HST_RATE of the subtotal; savings is the contractor quote minus the total, or None without a quote.
    """
    subtotal = round(sum(item.subtotal for item in items), 2)
    tax = round(subtotal * c.HST_RATE, 2)
    total = round(subtotal + tax, 2)
    savings = None if contractor_quote is None else round(contractor_quote - total, 2)
    return subtotal, tax, total, savings
