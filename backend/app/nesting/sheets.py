"""2D sheet nesting (GEO-12): cut rectangles from plywood sheets with a guillotine packer (rectpack).

Coordinates follow the boards: x runs along the sheet's length (96"), y along its width (48"). A piece's
`w` is its extent along x and `h` along y. Sheets are unlimited; a new one is opened when a piece does
not fit on the earlier ones.

Kerf: every piece is packed as (w + kerf) x (h + kerf), so neighbours are one saw cut apart. The bin is
made one kerf larger than the sheet, so a piece that is exactly as long or wide as the sheet still fits
(its trailing kerf hangs off the edge, where no cut is needed). Output pieces carry their REAL size and
always lie inside the real sheet.
"""

import math
from dataclasses import dataclass

from rectpack import SORT_AREA, GuillotineBssfSas, PackingBin, PackingMode, newPacker

from app.data import lumber_spec
from app.models import PlacedPiece, StockLayout
from app.nesting.boards import KERF_IN
from app.nesting.errors import PieceTooLongError

_SCALE = 1000  # rectpack works best on integers: pack in thousandths of an inch


@dataclass(frozen=True)
class SheetPiece:
    part_id: str
    label: str
    material: str
    w: float  # along the sheet's length (x) unless the piece is rotated
    h: float  # along the sheet's width (y)


def _units(value: float, kerf_in: float) -> int:
    """value + kerf in thousandths of an inch, rounded UP so scaling never makes a piece smaller."""
    return math.ceil(round((value + kerf_in) * _SCALE, 6))


def _fits(piece: SheetPiece, length: float, width: float, rotate: bool) -> bool:
    eps = 1e-9
    if piece.w <= length + eps and piece.h <= width + eps:
        return True
    return rotate and piece.h <= length + eps and piece.w <= width + eps


def _pack(
    ordered: list[SheetPiece], sheet_length: float, sheet_width: float, kerf_in: float, rotation: bool
) -> dict[int, list[PlacedPiece]] | None:
    """One rectpack run; {bin index: placed pieces}, or None if some piece could not be placed."""
    packer = newPacker(
        mode=PackingMode.Offline,
        bin_algo=PackingBin.BBF,
        pack_algo=GuillotineBssfSas,
        sort_algo=SORT_AREA,
        rotation=rotation,
    )
    packer.add_bin(_units(sheet_length, kerf_in), _units(sheet_width, kerf_in), count=float("inf"))
    for index, piece in enumerate(ordered):
        packer.add_rect(_units(piece.w, kerf_in), _units(piece.h, kerf_in), rid=index)
    packer.pack()
    placements: dict[int, list[PlacedPiece]] = {}
    for bin_index, x, y, packed_w, packed_h, rid in packer.rect_list():
        piece = ordered[rid]
        rotated = (packed_w, packed_h) != (_units(piece.w, kerf_in), _units(piece.h, kerf_in))
        placements.setdefault(bin_index, []).append(
            PlacedPiece(
                label=piece.label,
                part_id=piece.part_id,
                x=x / _SCALE,
                y=y / _SCALE,
                w=piece.h if rotated else piece.w,
                h=piece.w if rotated else piece.h,
                rotated=rotated,
            )
        )
    if sum(len(placed) for placed in placements.values()) != len(ordered):
        return None
    return placements


def nest_sheets(pieces: list[SheetPiece], kerf_in: float = KERF_IN, grain_locked: bool = False) -> list[StockLayout]:
    """Lay rectangular pieces out on sheets; one StockLayout (kind "sheet") per sheet to buy.

    Rotation by 90 degrees is allowed unless `grain_locked`. `rotated=True` on a placed piece means w and
    h are the swapped, on-sheet dimensions. `stock_id` is "<material>_<width>x<length>-<n>" (n from 1 per
    material, in packing order), matching the price key, e.g. "3/4_ext_ply_48x96-1". `utilization` is the
    sum of piece areas over the sheet area. Unless grain locked, the packing is tried both without and with
    rotation and the one with fewer sheets wins (ties: fewer rotated pieces, so pieces stay unrotated
    whenever rotating gains nothing). Raises PieceTooLongError if a piece cannot fit on one sheet.
    """
    by_material: dict[str, list[SheetPiece]] = {}
    for piece in pieces:
        by_material.setdefault(piece.material, []).append(piece)

    layouts: list[StockLayout] = []
    for material in sorted(by_material):
        spec = lumber_spec(material)
        if spec.kind != "sheet" or spec.sheet_size_in is None:
            raise ValueError(f"{material!r} is not a sheet material; use nest_boards for boards")
        sheet_width, sheet_length = spec.sheet_size_in
        rotate = not grain_locked
        too_big = sorted((p for p in by_material[material] if not _fits(p, sheet_length, sheet_width, rotate)), key=lambda p: p.part_id)
        if too_big:
            first = too_big[0]
            raise PieceTooLongError(
                f"Part {first.part_id} ({first.label}, {material}) is {first.w:g} x {first.h:g} in, which does not fit on a "
                f"{sheet_width:g} x {sheet_length:g} in sheet" + (" (grain locked, no rotation)" if grain_locked else "")
                + (f"; {len(too_big) - 1} more piece(s) are also too big" if len(too_big) > 1 else ""),
                [p.part_id for p in too_big],
            )

        ordered = sorted(by_material[material], key=lambda p: (-p.w * p.h, -max(p.w, p.h), p.part_id))
        rotation_options = [False] if grain_locked else [False, True]
        best: dict[int, list[PlacedPiece]] | None = None
        best_key: tuple[int, int] | None = None
        for allow_rotation in rotation_options:
            placements = _pack(ordered, sheet_length, sheet_width, kerf_in, allow_rotation)
            if placements is None:
                continue  # some piece only fits rotated
            rotated_count = sum(q.rotated for placed in placements.values() for q in placed)
            key = (len(placements), rotated_count)  # fewest sheets, then fewest rotated pieces
            if best_key is None or key < best_key:
                best, best_key = placements, key
        assert best is not None  # the fit check above guarantees at least one option works
        placements = best
        sheet_area = sheet_length * sheet_width
        for n, bin_index in enumerate(sorted(placements), start=1):
            placed = sorted(placements[bin_index], key=lambda p: (p.x, p.y, p.part_id))
            layouts.append(
                StockLayout(
                    stock_id=f"{material}_{sheet_width:g}x{sheet_length:g}-{n}",
                    material=material,
                    kind="sheet",
                    length_in=sheet_length,
                    width_in=sheet_width,
                    pieces=placed,
                    utilization=sum(p.w * p.h for p in placed) / sheet_area,
                )
            )
    return layouts
