"""Find real Home Depot Canada boards a design can be cut from (task NC-4).

    uv run python scripts/find_wood.py ramp total_rise_in=14 available_length_in=144
    uv run python scripts/find_wood.py workbench width_in=48 height_in=34 depth_in=24
    uv run python scripts/find_wood.py step_platform total_rise_in=21

Builds the design with the real engine, then for each board material reads the retailer's category page
(through Tavily, needs TAVILY_API_KEY in the repo-root .env), lists the lengths really sold and lays the cut
list out on them. Prices shown are LISTED prices for a store Tavily cannot choose, so they can differ from
your local store: treat them as a guide. Sheets (plywood), screws and hardware are not looked up.
"""

import sys

import app.config  # noqa: F401  (importing it loads the repo-root .env)
from app import engine
from app.models import ParamValue
from app.pricing.retail import find_wood
from app.util.units import format_ft_in


def parse_value(text: str) -> float | bool | str:
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return float(text)
    except ValueError:
        return text


def main(argv: list[str]) -> int:
    if len(argv) < 1 or "=" in argv[0]:
        print(__doc__)
        return 2
    template, pairs = argv[0], argv[1:]
    params = {}
    for pair in pairs:
        name, _, text = pair.partition("=")
        params[name] = ParamValue(value=parse_value(text), source="user")
    spec, plan = engine.generate(template, params, {})
    plans = find_wood(plan.cut_list)
    print(f"{template} {' '.join(pairs)}: {len(spec.parts)} parts, {len(plan.cut_list)} cut list rows")
    failed = False
    for wood in plans:
        print(f"\n{wood.material}")
        for purchase in wood.purchases:
            item = purchase.listing
            price = f"${item.price_cad:.2f}" if item.price_cad is not None else "no price"
            print(f"  buy {purchase.qty} x {item.title} ({format_ft_in(item.length_in)}), {price} each, SKU {item.sku}")
            print(f"      {item.url}")
            for number, board in enumerate(purchase.boards, start=1):
                print(f"      board {number}: cut {', '.join(board)}")
        if wood.total_cad is not None:
            print(f"  listed total for {wood.material}: ${wood.total_cad:.2f}")
        for note in wood.notes:
            print(f"  note: {note}")
        for problem in wood.problems:
            failed = True
            print(f"  ! {problem}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
