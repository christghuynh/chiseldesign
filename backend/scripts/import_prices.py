"""Import retailer prices into data/prices.json (task NC-4).

    uv run python scripts/import_prices.py --template prices_to_fill.csv    # writes a CSV listing every key
    # ...fill in price_cad, source_url (the product page) and optionally retrieved_at, then:
    uv run python scripts/import_prices.py prices_to_fill.csv               # validates and updates prices.json

Blank rows are skipped and stay placeholders. Nothing is written if any row is invalid.
"""

import sys
from pathlib import Path

from app.pricing.importer import PriceImportError, import_csv, write_template


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--template":
        count = write_template(Path(argv[1]))
        print(f"wrote {argv[1]} with {count} rows: fill in price_cad and source_url, then import it")
        return 0
    if len(argv) != 1:
        print(__doc__)
        return 2
    try:
        summary = import_csv(Path(argv[0]))
    except PriceImportError as exc:
        print(f"nothing changed. {exc}")
        return 1
    print(f"updated {len(summary['updated'])} price(s): {', '.join(summary['updated']) or 'none'}")
    left = summary["still_placeholder"]
    print(f"still placeholders ({len(left)}): {', '.join(left) or 'none, the Estimate label will disappear'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
