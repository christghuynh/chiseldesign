"""B5: build a Plan (cut list, cutting layouts, shopping list, totals) from labelled parts.

    parts -> cut list -> nesting (boards 1D, sheets 2D) -> shopping list -> totals

Pieces that cannot be bought in one piece (longer than the longest board sold, or bigger than a sheet)
do NOT make the plan fail: they are left out of nesting and lumber pricing, stay in the cut list, and get
an explanatory note on their row. The rule engine flags such a design separately; the plan still has to
build so the 3D preview and rule badges keep working. Hardware (screws, hangers, post bases) is still
counted from ALL parts, since the design needs the fasteners however the board is sourced.
"""

from typing import Any

from app import data
from app.cutlist import build_cut_list, label_lengths, label_sheet_dims
from app.data import lumber_spec
from app.models import CutListRow, Part, Plan, StockLayout
from app.nesting import BoardPiece, PieceTooLongError, SheetPiece, nest_boards, nest_sheets
from app.pricing import build_shopping_list, price_totals
from app.util.units import format_ft_in


def _quote(meta: dict[str, Any] | None) -> float | None:
    value = (meta or {}).get("contractor_quote_cad")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _nest_dropping_oversize(nest, pieces: list, oversize: set[str]) -> list[StockLayout]:
    """Run a nesting function; on PieceTooLongError record the offending ids and nest the remainder."""
    try:
        return nest(pieces)
    except PieceTooLongError as error:
        oversize.update(error.part_ids)
        return nest([p for p in pieces if p.part_id not in oversize])


def _oversize_note(material: str) -> str:
    spec = lumber_spec(material)
    if spec.kind == "sheet":
        width, length = spec.sheet_size_in or (0, 0)
        return f"Larger than a full sheet ({format_ft_in(width)} x {format_ft_in(length)}); cannot be bought as one piece"
    return f"Longer than the longest board sold ({format_ft_in(spec.max_stock_length_in)}); cannot be bought as one piece"


def build_plan(parts: list[Part], meta: dict[str, Any] | None = None) -> Plan:
    """Cut list, layouts, shopping list and totals for `parts` (which must already be labelled).

    `meta["contractor_quote_cad"]`, when a number, sets `contractor_quote` and `savings`.
    `has_placeholder_prices` is True when any priced line comes from a placeholder prices.json entry.
    """
    cut_list = build_cut_list(parts)

    board_pieces: list[BoardPiece] = []
    sheet_pieces: list[SheetPiece] = []
    # Sizes are per label (the longest member), so layouts always agree with the cut list rows.
    lengths = label_lengths(parts)
    sheet_dims = label_sheet_dims(parts)
    for part in parts:
        if lumber_spec(part.material).kind == "sheet":
            w, h = sheet_dims[part.label]
            sheet_pieces.append(SheetPiece(part.id, part.label, part.material, w, h))
        else:
            board_pieces.append(BoardPiece(part.id, part.label, part.material, lengths[part.label]))

    oversize: set[str] = set()
    layouts = _nest_dropping_oversize(nest_boards, board_pieces, oversize)
    layouts += _nest_dropping_oversize(nest_sheets, sheet_pieces, oversize)

    if oversize:
        material_of = {p.id: p.material for p in parts}
        flagged = {pid: _oversize_note(material_of[pid]) for pid in oversize}
        rows: list[CutListRow] = []
        for row in cut_list:
            notes = [flagged[pid] for pid in row.part_ids if pid in flagged][:1]
            rows.append(row.model_copy(update={"cut_notes": row.cut_notes + notes}) if notes else row)
        cut_list = rows

    shopping = build_shopping_list(layouts, parts)
    contractor_quote = _quote(meta)
    subtotal, tax, total, savings = price_totals(shopping, contractor_quote)
    prices = data.prices()
    return Plan(
        cut_list=cut_list,
        layouts=layouts,
        shopping=shopping,
        subtotal=subtotal,
        tax=tax,
        total=total,
        contractor_quote=contractor_quote,
        savings=savings,
        has_placeholder_prices=any(prices[item.key].placeholder for item in shopping),
    )
