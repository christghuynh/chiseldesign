"""GEO-12: 2D sheet nesting."""

import random

import pytest

from app.nesting import KERF_IN, PieceTooLongError, SheetPiece, nest_sheets

MATERIAL = "3/4_ext_ply"
SHEET_W, SHEET_L = 48.0, 96.0
TOL = 1e-6


def piece(n: int, w: float, h: float) -> SheetPiece:
    return SheetPiece(part_id=f"S-{n}", label="S", material=MATERIAL, w=w, h=h)


def assert_valid(layouts, pieces, kerf=KERF_IN, grain_locked=False):
    placed = [q.part_id for layout in layouts for q in layout.pieces]
    assert sorted(placed) == sorted(p.part_id for p in pieces)
    by_id = {p.part_id: p for p in pieces}
    ids = [layout.stock_id for layout in layouts]
    assert len(ids) == len(set(ids))
    for layout in layouts:
        assert layout.kind == "sheet" and (layout.length_in, layout.width_in) == (SHEET_L, SHEET_W)
        for q in layout.pieces:
            src = by_id[q.part_id]
            expected = (src.h, src.w) if q.rotated else (src.w, src.h)
            assert (q.w, q.h) == pytest.approx(expected)
            assert not (q.rotated and grain_locked)
            assert q.x >= -TOL and q.y >= -TOL
            assert q.x + q.w <= SHEET_L + TOL and q.y + q.h <= SHEET_W + TOL, f"{layout.stock_id}: {q.part_id} off the sheet"
        for i, a in enumerate(layout.pieces):
            for b in layout.pieces[i + 1 :]:
                # rectangles grown by the kerf on their far sides must not overlap
                separated = (
                    b.x >= a.x + a.w + kerf - TOL
                    or a.x >= b.x + b.w + kerf - TOL
                    or b.y >= a.y + a.h + kerf - TOL
                    or a.y >= b.y + b.h + kerf - TOL
                )
                assert separated, f"{layout.stock_id}: {a.part_id} overlaps {b.part_id}"
        area = sum(q.w * q.h for q in layout.pieces)
        assert layout.utilization == pytest.approx(area / (SHEET_W * SHEET_L))
        assert 0 < layout.utilization <= 1


def test_a_single_piece_goes_on_one_sheet():
    (layout,) = nest_sheets([piece(1, 30.0, 20.0)])
    assert layout.stock_id == "3/4_ext_ply_48x96-1"
    assert layout.utilization == pytest.approx(600 / (48 * 96))
    q = layout.pieces[0]
    assert (q.x, q.y, q.w, q.h, q.rotated) == (0.0, 0.0, 30.0, 20.0, False)


def test_piece_count_is_preserved_and_layouts_valid():
    pieces = [piece(i, 47.9, 23.9) for i in range(10)]
    layouts = nest_sheets(pieces)
    assert_valid(layouts, pieces)
    assert sum(len(layout.pieces) for layout in layouts) == 10
    assert len(layouts) == 3  # 2 across x 2 along = 4 per sheet with kerfs (47.9 + 0.125 + 47.9 <= 96)


def test_kerf_separates_neighbours_and_a_full_sheet_piece_still_fits():
    (layout,) = nest_sheets([piece(1, 96.0, 48.0)])
    assert layout.utilization == pytest.approx(1.0)
    pieces = [piece(1, 48.0, 48.0), piece(2, 47.9, 48.0)]  # 48 + kerf + 47.9 > 96 -> two sheets
    assert len(nest_sheets(pieces)) == 2
    assert len(nest_sheets(pieces, kerf_in=0.0)) == 1


def test_sheets_open_as_needed():
    pieces = [piece(i, 96.0, 48.0) for i in range(3)]
    layouts = nest_sheets(pieces)
    assert [layout.stock_id for layout in layouts] == ["3/4_ext_ply_48x96-1", "3/4_ext_ply_48x96-2", "3/4_ext_ply_48x96-3"]
    assert_valid(layouts, pieces)


def test_rotation_is_used_when_free_and_respected_when_grain_locked():
    tall = piece(1, 40.0, 90.0)  # 40 along the length, 90 across a 48" wide sheet: only fits rotated
    (layout,) = nest_sheets([tall])
    assert layout.pieces[0].rotated is True
    assert (layout.pieces[0].w, layout.pieces[0].h) == (90.0, 40.0)
    with pytest.raises(PieceTooLongError):
        nest_sheets([tall], grain_locked=True)


def test_grain_locked_never_rotates_and_uses_more_sheets_when_needed():
    pieces = [piece(i, 30.0, 40.0) for i in range(6)]
    locked = nest_sheets(pieces, grain_locked=True)
    assert_valid(locked, pieces, grain_locked=True)
    assert not any(q.rotated for layout in locked for q in layout.pieces)
    free = nest_sheets(pieces)
    assert_valid(free, pieces)
    assert len(free) <= len(locked)


def test_oversize_piece_raises():
    with pytest.raises(PieceTooLongError) as info:
        nest_sheets([piece(1, 10.0, 10.0), piece(2, 100.0, 50.0)])
    assert "S-2" in str(info.value) and "48" in str(info.value) and "96" in str(info.value)
    assert info.value.part_ids == ["S-2"]
    with pytest.raises(PieceTooLongError):
        nest_sheets([piece(1, 96.5, 10.0)])
    with pytest.raises(PieceTooLongError):
        nest_sheets([piece(1, 10.0, 96.5)])  # too long even rotated


def test_deterministic_and_independent_of_input_order():
    rng = random.Random(3)
    pieces = [piece(i, round(rng.uniform(5, 47), 3), round(rng.uniform(5, 90), 3)) for i in range(25)]
    first = nest_sheets(pieces)
    assert nest_sheets(pieces) == first
    shuffled = pieces[:]
    rng.shuffle(shuffled)
    assert nest_sheets(shuffled) == first


def test_empty_input_and_wrong_material():
    assert nest_sheets([]) == []
    with pytest.raises(ValueError, match="not a sheet"):
        nest_sheets([SheetPiece("S-1", "S", "2x6_PT", 10.0, 10.0)])


@pytest.mark.parametrize("seed", range(20))
def test_randomized_layouts_are_always_valid(seed):
    rng = random.Random(100 + seed)
    pieces = [piece(i, round(rng.uniform(1, 96), 3), round(rng.uniform(1, 48), 3)) for i in range(rng.randint(1, 40))]
    kerf = rng.choice([0.0, 0.125, 0.25])
    locked = rng.random() < 0.5
    layouts = nest_sheets(pieces, kerf_in=kerf, grain_locked=locked)
    assert_valid(layouts, pieces, kerf=kerf, grain_locked=locked)
