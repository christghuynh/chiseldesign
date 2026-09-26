"""1D board nesting (GEO-11): cut pieces from stock lengths with first-fit decreasing.

Per material: pieces are sorted longest first (ties by part id) and put into the first bin they fit,
where every bin is as long as the LONGEST stock length sold. Each bin is then shrunk to the SHORTEST
stock length that still holds its contents, so a single 100" piece is bought as a 120" board, not a 192".
A saw kerf is lost between neighbouring pieces (not at the ends of the board).
"""

from dataclasses import dataclass

from app.data import lumber_spec
from app.models import PlacedPiece, StockLayout
from app.nesting.errors import PieceTooLongError
from app.util.units import format_ft_in

KERF_IN = 0.125  # width of a saw cut, inches
_EPS = 1e-9


@dataclass(frozen=True)
class BoardPiece:
    part_id: str
    label: str
    material: str
    length_in: float


@dataclass
class _Bin:
    pieces: list[BoardPiece]
    used: float  # sum of piece lengths + kerfs between them


def _first_fit_decreasing(pieces: list[BoardPiece], capacity: float, kerf_in: float) -> list[_Bin]:
    bins: list[_Bin] = []
    for piece in sorted(pieces, key=lambda p: (-p.length_in, p.part_id)):
        for candidate in bins:
            if candidate.used + kerf_in + piece.length_in <= capacity + _EPS:
                candidate.pieces.append(piece)
                candidate.used += kerf_in + piece.length_in
                break
        else:
            bins.append(_Bin([piece], piece.length_in))
    return bins


def nest_boards(pieces: list[BoardPiece], kerf_in: float = KERF_IN) -> list[StockLayout]:
    """Lay board pieces out on stock lengths; returns one StockLayout (kind "board") per board to buy.

    Layouts are ordered by material, then stock length, then their number in `stock_id`
    ("<material>_<stock length>-<n>", n counting from 1 per material and stock length). Piece x offsets
    start at 0 and advance by length + kerf; y is 0, h is the board's actual width. `utilization` is
    the sum of piece lengths over the stock length (kerf not counted). Raises PieceTooLongError, naming
    the piece, its length and the maximum, if any piece is longer than the longest stock sold.
    """
    by_material: dict[str, list[BoardPiece]] = {}
    for piece in pieces:
        by_material.setdefault(piece.material, []).append(piece)

    layouts: list[StockLayout] = []
    for material in sorted(by_material):
        spec = lumber_spec(material)
        if spec.kind != "board" or spec.width_in is None:
            raise ValueError(f"{material!r} is not a board material; use nest_sheets for sheets")
        longest = spec.stock_lengths_in[-1]
        too_long = sorted((p for p in by_material[material] if p.length_in > longest + _EPS), key=lambda p: p.part_id)
        if too_long:
            first = too_long[0]
            raise PieceTooLongError(
                f"Part {first.part_id} ({first.label}, {material}) is {format_ft_in(first.length_in)} "
                f"({first.length_in:g} in) long, but the longest {material} board sold is {format_ft_in(longest)} "
                f"({longest:g} in)" + (f"; {len(too_long) - 1} more piece(s) are also too long" if len(too_long) > 1 else ""),
                [p.part_id for p in too_long],
            )
        bins = _first_fit_decreasing(by_material[material], longest, kerf_in)
        sized: list[tuple[float, int, _Bin]] = []
        for index, b in enumerate(bins):
            stock = next(length for length in spec.stock_lengths_in if b.used <= length + _EPS)
            sized.append((stock, index, b))
        sized.sort(key=lambda t: (t[0], t[1]))
        counters: dict[float, int] = {}
        for stock, _, b in sized:
            counters[stock] = counters.get(stock, 0) + 1
            placed: list[PlacedPiece] = []
            x = 0.0
            for piece in b.pieces:
                placed.append(
                    PlacedPiece(label=piece.label, part_id=piece.part_id, x=round(x, 6), y=0.0, w=piece.length_in, h=spec.width_in, rotated=False)
                )
                x += piece.length_in + kerf_in
            layouts.append(
                StockLayout(
                    stock_id=f"{material}_{int(stock)}-{counters[stock]}",
                    material=material,
                    kind="board",
                    length_in=stock,
                    width_in=spec.width_in,
                    pieces=placed,
                    utilization=sum(p.length_in for p in b.pieces) / stock,
                )
            )
    return layouts
