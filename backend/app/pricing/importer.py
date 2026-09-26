"""Import real retailer prices into data/prices.json (task NC-4).

Prices are collected by hand or with any tool into a CSV, then applied here so every entry is validated
and marked real. A row needs a known key, a positive price and a source URL. Rows you leave blank stay as
placeholders, so the file can be filled in stages: `Plan.has_placeholder_prices` is true only while a
placeholder entry is actually used by the plan.

CSV columns: key, price_cad, source_url, retrieved_at (YYYY-MM-DD, blank means today), description (optional).
The template (`write_template`) lists every key with its current description and unit to make lookup easy.
"""

import csv
import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from app.data import DATA_DIR, prices

PRICES_PATH = DATA_DIR / "prices.json"
COLUMNS = ["key", "description", "unit", "price_cad", "source_url", "retrieved_at"]
PLACEHOLDER_SUFFIX = " (placeholder price)"
REAL_COMMENT = "Retailer prices in CAD. Every entry keeps its source_url and retrieved_at; prices vary by store and change, so re-check before the demo (task NC-4)."


class PriceImportError(ValueError):
    """A row in the CSV is not usable. The message names the row."""


def write_template(path: Path) -> int:
    """Write a CSV listing every price key, ready to fill in. Returns the number of rows."""
    entries = prices()
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for key, entry in entries.items():
            writer.writerow({"key": key, "description": entry.description.removesuffix(PLACEHOLDER_SUFFIX), "unit": entry.unit,
                             "price_cad": "", "source_url": "", "retrieved_at": ""})
    return len(entries)


def _parse_row(number: int, row: dict[str, str], known: set[str], today: date) -> dict | None:
    key = (row.get("key") or "").strip()
    price_text = (row.get("price_cad") or "").strip().lstrip("$").replace(",", "")
    if not key and not price_text:
        return None
    where = f"row {number} ({key or 'no key'})"
    if key not in known:
        raise PriceImportError(f"{where}: unknown key; known keys: {sorted(known)}")
    if not price_text:
        return None  # left blank on purpose: stays a placeholder
    try:
        price = float(price_text)
    except ValueError:
        raise PriceImportError(f"{where}: price {price_text!r} is not a number") from None
    if not price > 0:
        raise PriceImportError(f"{where}: price must be greater than 0")
    url = (row.get("source_url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise PriceImportError(f"{where}: source_url must be the product page (http or https), got {url!r}")
    when = (row.get("retrieved_at") or "").strip() or today.isoformat()
    try:
        date.fromisoformat(when)
    except ValueError:
        raise PriceImportError(f"{where}: retrieved_at {when!r} must look like 2026-09-26") from None
    return {"key": key, "price": round(price, 2), "url": url, "when": when, "description": (row.get("description") or "").strip()}


def read_rows(lines: Iterable[str], today: date | None = None) -> list[dict]:
    known = set(prices())
    reader = csv.DictReader(lines)
    missing = {"key", "price_cad", "source_url"} - set(reader.fieldnames or [])
    if missing:
        raise PriceImportError(f"the CSV is missing columns: {sorted(missing)}")
    rows, seen = [], set()
    for number, row in enumerate(reader, start=2):
        parsed = _parse_row(number, row, known, today or date.today())
        if parsed is None:
            continue
        if parsed["key"] in seen:
            raise PriceImportError(f"row {number} ({parsed['key']}): this key appears twice")
        seen.add(parsed["key"])
        rows.append(parsed)
    return rows


def apply_rows(rows: list[dict], path: Path = PRICES_PATH) -> dict:
    """Update prices.json in place with the given rows. Returns a summary."""
    doc = json.loads(path.read_text("utf-8"))
    items = doc["items"]
    for row in rows:
        entry = items[row["key"]]
        description = (row["description"] or entry["description"]).removesuffix(PLACEHOLDER_SUFFIX)
        entry.update({"description": description, "price_cad": row["price"], "source_url": row["url"],
                      "retrieved_at": row["when"], "placeholder": False})
    remaining = [k for k, v in items.items() if v["placeholder"]]
    if not remaining:
        doc["_comment"] = REAL_COMMENT
    path.write_bytes((json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))  # bytes: keep LF on Windows
    prices.cache_clear()  # the loader caches; the next call must see the new file
    return {"updated": [r["key"] for r in rows], "still_placeholder": remaining}


def import_csv(csv_path: Path, path: Path = PRICES_PATH, today: date | None = None) -> dict:
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:  # utf-8-sig: spreadsheets often add a byte-order mark
        rows = read_rows(fh, today)
    return apply_rows(rows, path)
