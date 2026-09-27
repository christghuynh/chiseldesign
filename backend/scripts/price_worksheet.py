"""Write a worksheet of the real Home Depot Canada products to read prices from (task NC-4).

    uv run python scripts/price_worksheet.py prices_worksheet.csv

For every board price key the engine can use (2x6_PT_192, ...), finds the product that is really sold in that
length (through Tavily, needs TAVILY_API_KEY in the repo-root .env) and writes a CSV in the price importer's
format with `source_url` filled in and `price_cad` blank. Read each price on its product page with the store
you want the prices for (the site shows the price for the store selected in the browser), fill in `price_cad`,
and import it with scripts/import_prices.py. Keys with no sold product are left with a note: the engine offers
a length the retailer does not sell. Tavily's own prices are not used because they are for an unknown store.
"""

import csv
import sys
from pathlib import Path

import app.config  # noqa: F401  (importing it loads the repo-root .env)
from app.data import lumber, prices
from app.pricing.importer import COLUMNS, PLACEHOLDER_SUFFIX
from app.pricing.retail import price_worksheet

EXTRA = ["product", "note"]


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    boards = [name for name, spec in lumber().items() if spec.kind == "board"]
    entries = prices()
    rows = price_worksheet(boards)
    with Path(argv[0]).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[*COLUMNS, *EXTRA], lineterminator="\n")
        writer.writeheader()
        for row in rows:
            entry = entries.get(row.key)
            writer.writerow(
                {
                    "key": row.key,
                    "description": entry.description.removesuffix(PLACEHOLDER_SUFFIX) if entry else "",
                    "unit": entry.unit if entry else "each",
                    "price_cad": "",
                    "source_url": row.listing.url if row.listing else "",
                    "retrieved_at": "",
                    "product": row.listing.title if row.listing else "",
                    "note": "" if row.listing else "no product sold in this length: the engine should not offer it",
                }
            )
    found = [r for r in rows if r.listing]
    print(f"wrote {argv[0]}: {len(found)} products to price, {len(rows) - len(found)} lengths with no sold product")
    for r in rows:
        if not r.listing:
            print(f"  not sold: {r.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
