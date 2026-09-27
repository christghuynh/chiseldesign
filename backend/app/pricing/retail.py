"""Find real Home Depot Canada boards that a cut list can be cut from (task NC-4).

Given the boards a design needs, this reads the retailer's category pages for each board size, lists the
lengths that are really sold, and lays the cut list out on those boards. Reading pages goes through the
Tavily API (`TAVILY_API_KEY`); nothing here talks to the retailer directly.

Prices found this way are the LISTED price for a store Tavily cannot choose, and they can be a cached
copy, so they can differ from the price at your local store. They are reported as such and are never written
to prices.json (that file holds prices read at one named store by hand, see `importer`). The useful output
is which products exist, in which lengths, and how to cut the design out of them.

Pages are cached on disk for `CACHE_TTL_S` so repeated lookups do not spend credits.
"""

import hashlib
import json
import os
import re
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.data import lumber_spec
from app.models import CutListRow
from app.nesting import BoardPiece, PieceTooLongError, nest_boards

API = "https://api.tavily.com"
SITE = "homedepot.ca"
CACHE_TTL_S = 12 * 3600
HTTP_TIMEOUT_S = 150.0
RETRY_DELAYS_S = (1.5, 4.0)  # Tavily sometimes fails one page and reads it fine a moment later
CACHE_DIR = Path(tempfile.gettempdir()) / "chisel-retail-cache"


class RetailLookupError(RuntimeError):
    """The retailer's pages could not be read or understood. The message says why."""


@dataclass(frozen=True)
class Listing:
    title: str
    sku: str
    url: str
    length_in: float
    price_cad: float | None  # None when the page showed no parsable price
    out_of_stock_online: bool
    sold: bool = True  # False when the page says it is neither deliverable nor sold in stores


@dataclass(frozen=True)
class Purchase:
    """One kind of board to buy, and the cut layout of each board."""

    listing: Listing
    qty: int
    boards: list[list[str]]  # per board: "label length" strings, in cutting order


@dataclass(frozen=True)
class WoodPlan:
    material: str
    purchases: list[Purchase]
    problems: list[str]  # the lookup or the layout failed for this material
    notes: list[str] = field(default_factory=list)  # things to double-check, the plan still stands

    @property
    def total_cad(self) -> float | None:
        prices = [p.listing.price_cad for p in self.purchases]
        if not prices or any(price is None for price in prices):
            return None
        return round(sum(p.qty * p.listing.price_cad for p in self.purchases), 2)  # type: ignore[operator]


# --- reading listings ---------------------------------------------------------------------------------

_SIZE = re.compile(
    r"(?P<a>\d+(?:/\d+)?)\s*(?:in\.?|inch)?\s*[xX]\s*(?P<b>\d+)\s*(?:in\.?|inch)?\s*[xX]\s*(?P<len>\d+(?:\.\d+)?)\s*(?P<unit>'|ft\.?|feet|foot)",
)
_PRICE_WORDS = re.compile(r"\$(\d[\d,]*)\s+And\s+(\d{1,2})\s+Cents", re.IGNORECASE)
_PRICE_PLAIN = re.compile(r"\$(\d[\d,]*\.\d{2})\b")


def _price(block: str) -> float | None:
    words = _PRICE_WORDS.search(block)
    if words:
        return round(int(words.group(1).replace(",", "")) + int(words.group(2)) / 100, 2)
    plain = _PRICE_PLAIN.search(block)
    return float(plain.group(1).replace(",", "")) if plain else None


def parse_listing(markdown: str, nominal: tuple[str, str]) -> list[Listing]:
    """Products on a category page whose title says `a x b x length` for this nominal size."""
    listings: dict[str, Listing] = {}
    for block in re.split(r"\n## \[", markdown)[1:]:
        head = re.match(r"([^\]]+)\]\((https://www\.homedepot\.ca/product/[^\s)\"]+)", block)
        sku = re.search(r"SKU # (\d+)", block)
        if not (head and sku):
            continue
        title = head.group(1)
        size = _SIZE.search(title)
        if not size or (size.group("a"), size.group("b")) != nominal:
            continue
        listings.setdefault(
            sku.group(1),
            Listing(
                title=title,
                sku=sku.group(1),
                url=head.group(2),
                length_in=round(float(size.group("len")) * 12, 3),
                price_cad=_price(block),
                out_of_stock_online="Out of Stock Online" in block,
                sold=not ("Not Sold in Stores" in block and "Not Available for Delivery" in block),
            ),
        )
    return sorted(listings.values(), key=lambda item: (item.length_in, item.price_cad is None, item.price_cad or 0.0, item.sku))


def nominal_of(material: str) -> tuple[str, str]:
    """('2', '6') for 2x6_PT, ('5/4', '6') for 5/4x6_PT_deck."""
    spec = lumber_spec(material)
    nominal = spec.nominal or ""
    match = re.fullmatch(r"(\d+(?:/\d+)?)x(\d+)", nominal)
    if not match:
        raise RetailLookupError(f"{material} has no board size to look up (nominal {nominal!r})")
    return match.group(1), match.group(2)


# --- Tavily -------------------------------------------------------------------------------------------


def _key() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise RetailLookupError("TAVILY_API_KEY is not set; add it to the repo-root .env")
    return key


def _cache_path(name: str) -> Path:
    return CACHE_DIR / (hashlib.sha256(name.encode()).hexdigest()[:24] + ".json")


def _cached(name: str, fetch, ttl_s: float = CACHE_TTL_S):
    path = _cache_path(name)
    try:
        doc = json.loads(path.read_text("utf-8"))
        if time.time() - doc["at"] < ttl_s:
            return doc["value"]
    except (OSError, ValueError, KeyError):
        pass
    value = fetch()
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"at": time.time(), "value": value}), "utf-8")
    except OSError:
        pass  # a cache that cannot be written only costs credits, never correctness
    return value


def _post(client: httpx.Client, path: str, body: dict) -> dict:
    """POST to Tavily, retrying transient failures (network errors and HTTP 5xx). Other errors are final."""
    error = "no attempt made"
    for delay in (0.0, *RETRY_DELAYS_S):
        time.sleep(delay)
        try:
            response = client.post(f"{API}{path}", json=body, headers={"Authorization": f"Bearer {_key()}"}, timeout=HTTP_TIMEOUT_S)
        except httpx.HTTPError as exc:
            error = f"could not reach Tavily: {type(exc).__name__}"
            continue
        if response.status_code == 200:
            return response.json()
        error = f"Tavily returned HTTP {response.status_code}: {response.text[:200].replace(_key(), '[key]')}"
        if response.status_code < 500:
            break
    raise RetailLookupError(error)


def category_url(client: httpx.Client, nominal: tuple[str, str], deck: bool) -> str:
    a, b = nominal
    pattern = re.compile(rf"/pressure-treated-lumber/f/{a.replace('/', '-')}-x-{b}/")
    kind = "decking" if deck else "lumber"
    queries = [f"pressure treated {a} x {b} {kind}", f"{a} x {b} pressure treated {'deck boards' if deck else 'posts'}"]

    def fetch() -> str:
        for query in queries:  # the category page does not always come back for the first wording
            found = _post(client, "/search", {"query": query, "include_domains": [SITE], "max_results": 10, "search_depth": "basic"})
            for item in found.get("results", []):
                if pattern.search(item["url"]):
                    return item["url"]
        raise RetailLookupError(f"no {a} x {b} pressure treated category page found at {SITE}")

    return _cached(f"category:{a}x{b}:{deck}", fetch)


def page_text(client: httpx.Client, url: str) -> str:
    def fetch() -> str:
        found: dict = {}
        for delay in (0.0, *RETRY_DELAYS_S):
            time.sleep(delay)
            found = _post(client, "/extract", {"urls": [url], "extract_depth": "basic", "format": "markdown"})
            if found.get("results"):
                return found["results"][0]["raw_content"]
        raise RetailLookupError(f"Tavily could not read {url}: {found.get('failed_results')}")

    return _cached(f"page:{url}", fetch)


def find_boards(material: str, client: httpx.Client | None = None) -> list[Listing]:
    """Every board of this material's nominal size that the retailer lists, shortest first."""
    nominal = nominal_of(material)
    own = client is None
    client = client or httpx.Client()
    try:
        url = category_url(client, nominal, deck=material.endswith("_deck"))
        listings = parse_listing(page_text(client, url), nominal)
    finally:
        if own:
            client.close()
    if not listings:
        raise RetailLookupError(f"{url} lists no {nominal[0]} x {nominal[1]} boards that could be read")
    return listings


# --- choosing boards ----------------------------------------------------------------------------------


def _rank(item: Listing) -> tuple[bool, float, str]:
    return (item.price_cad is None, item.price_cad or 0.0, item.sku)


def best_by_length(listings: list[Listing], min_length_in: float = 0.0) -> dict[float, Listing]:
    """For each length, the listing to buy: one that is sold and has a price, then the cheapest.

    Stock is not part of the choice: the page is read for a store we cannot identify, so it is only reported.
    """
    best: dict[float, Listing] = {}
    for item in listings:
        if item.length_in < min_length_in or not item.sold or item.price_cad is None:
            continue
        current = best.get(item.length_in)
        if current is None or _rank(item) < _rank(current):
            best[item.length_in] = item
    return best


def plan_wood(material: str, rows: list[CutListRow], listings: list[Listing]) -> WoodPlan:
    """Lay the cut list rows for one board material out on the boards `listings` says are sold."""
    problems: list[str] = []
    notes: list[str] = []
    by_length = best_by_length(listings)
    if not by_length:
        return WoodPlan(material, [], [f"none of the listed {material} boards is currently sold with a price"])
    pieces = [
        BoardPiece(part_id=f"{row.label}{i}", label=f"{row.label} {row.length_display}", material=material, length_in=row.length_in)
        for row in rows
        for i in range(row.qty)
    ]
    if not pieces:
        return WoodPlan(material, [], problems)
    try:
        layouts = nest_boards(pieces, stock_lengths_in={material: list(by_length)})
    except PieceTooLongError as exc:
        return WoodPlan(material, [], [f"{exc} (longest listed board: {max(by_length) / 12:g} ft)"])
    grouped: dict[float, list[list[str]]] = defaultdict(list)
    for layout in layouts:
        grouped[layout.length_in].append([p.label for p in layout.pieces])
    purchases = []
    for length in sorted(grouped):
        listing = by_length[length]
        if listing.out_of_stock_online:
            notes.append(f"{listing.title} was listed out of stock online for the store Tavily read: check your store")
        if listing.price_cad is None:
            notes.append(f"{listing.title} shows no readable price")
        purchases.append(Purchase(listing=listing, qty=len(grouped[length]), boards=grouped[length]))
    return WoodPlan(material, purchases, problems, notes)


def find_wood(rows: list[CutListRow], client: httpx.Client | None = None) -> list[WoodPlan]:
    """The board materials in a cut list, each matched to real listings and laid out on them.

    Only boards are covered: sheets (plywood), screws and hardware are not looked up.
    """
    by_material: dict[str, list[CutListRow]] = defaultdict(list)
    for row in rows:
        if lumber_spec(row.material).kind == "board":
            by_material[row.material].append(row)
    plans = []
    for material in sorted(by_material):
        try:
            listings = find_boards(material, client)
        except RetailLookupError as exc:
            plans.append(WoodPlan(material, [], [str(exc)]))
            continue
        plans.append(plan_wood(material, by_material[material], listings))
    return plans
