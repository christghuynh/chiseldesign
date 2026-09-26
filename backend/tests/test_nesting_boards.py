"""GEO-11: 1D board nesting."""

import random

import pytest

from app.data import lumber_spec
from app.nesting import KERF_IN, BoardPiece, PieceTooLongError, nest_boards

TOL = 1e-6


def piece(n: int, length: float, material: str = "2x6_PT") -> BoardPiece:
    return BoardPiece(part_id=f"P-{n}", label="P", material=material, length_in=length)


def assert_valid(layouts, pieces, kerf=KERF_IN):
    """Every piece placed exactly once, no overlap (kerf included), nothing past the end, utilization right."""
    placed = [q.part_id for layout in layouts for q in layout.pieces]
    assert sorted(placed) == sorted(p.part_id for p in pieces)
    length_of = {p.part_id: p.length_in for p in pieces}
    ids = [layout.stock_id for layout in layouts]
    assert len(ids) == len(set(ids))
    for layout in layouts:
        assert layout.kind == "board"
        spec = lumber_spec(layout.material)
        assert layout.length_in in spec.stock_lengths_in
        assert layout.width_in == spec.width_in
        ordered = sorted(layout.pieces, key=lambda q: q.x)
        assert ordered[0].x >= -TOL
        for a, b in zip(ordered, ordered[1:], strict=False):
            assert b.x >= a.x + a.w + kerf - TOL, f"{layout.stock_id}: {a.part_id} too close to {b.part_id}"
        assert ordered[-1].x + ordered[-1].w <= layout.length_in + TOL, layout.stock_id
        for q in layout.pieces:
            assert q.w == pytest.approx(length_of[q.part_id]) and q.y == 0 and q.h == spec.width_in and not q.rotated
        assert 0 < layout.utilization <= 1
        assert layout.utilization == pytest.approx(sum(q.w for q in layout.pieces) / layout.length_in)


def test_single_piece_shrinks_to_the_shortest_board_that_fits():
    (layout,) = nest_boards([piece(1, 100.0)])
    assert layout.length_in == 120  # not the 192" that the bin started as
    assert layout.stock_id == "2x6_PT_120-1"
    assert layout.utilization == pytest.approx(100 / 120)
    assert layout.width_in == 5.5


def test_exact_fit_uses_that_length_and_one_more_inch_needs_the_next():
    assert nest_boards([piece(1, 96.0)])[0].length_in == 96
    assert nest_boards([piece(1, 96.001)])[0].length_in == 120


def test_kerf_counts_between_pieces_but_not_at_the_ends():
    # 47.9375 * 2 + 0.125 = 96.0 exactly: fits an 8 ft board
    (layout,) = nest_boards([piece(1, 47.9375), piece(2, 47.9375)])
    assert layout.length_in == 96
    assert [q.x for q in sorted(layout.pieces, key=lambda q: q.x)] == [0.0, 48.0625]
    # a hair longer needs the next size
    (layout,) = nest_boards([piece(1, 47.94), piece(2, 47.9375)])
    assert layout.length_in == 120


def test_kerf_is_configurable():
    pieces = [piece(1, 47.5), piece(2, 47.5)]
    assert nest_boards(pieces, kerf_in=0.0)[0].length_in == 96
    (layout,) = nest_boards(pieces, kerf_in=2.0)
    assert layout.length_in == 120
    assert_valid([layout], pieces, kerf=2.0)


def test_offsets_start_at_zero_and_advance_by_length_plus_kerf():
    (layout,) = nest_boards([piece(1, 30.0), piece(2, 20.0), piece(3, 10.0)])
    assert [(q.part_id, q.x) for q in layout.pieces] == [("P-1", 0.0), ("P-2", 30.125), ("P-3", 50.25)]


def test_utilization_math():
    pieces = [piece(1, 60.0), piece(2, 60.0)]
    (layout,) = nest_boards(pieces)  # 120.125 needs a 144
    assert layout.length_in == 144
    assert layout.utilization == pytest.approx(120 / 144)  # kerf is not counted as used


def test_oversize_piece_raises_naming_part_length_and_maximum():
    with pytest.raises(PieceTooLongError) as info:
        nest_boards([piece(1, 50.0), piece(2, 200.0)])
    message = str(info.value)
    assert "P-2" in message and "16' 8\"" in message and "16' 0\"" in message and "2x6_PT" in message
    assert info.value.part_ids == ["P-2"]
    assert isinstance(info.value, ValueError)


def test_oversize_error_lists_every_offending_piece():
    with pytest.raises(PieceTooLongError) as info:
        nest_boards([piece(1, 300.0), piece(2, 250.0), piece(3, 10.0)])
    assert info.value.part_ids == ["P-1", "P-2"]


def test_a_piece_exactly_as_long_as_the_longest_board_is_fine():
    (layout,) = nest_boards([piece(1, 192.0)])
    assert layout.length_in == 192 and layout.utilization == 1.0


def test_the_limit_is_per_material():
    nest_boards([piece(1, 190.0, "2x6_PT")])
    with pytest.raises(PieceTooLongError):
        nest_boards([piece(1, 190.0, "4x4_PT")])  # 4x4 stops at 120"


def test_many_small_pieces_pack_into_few_boards():
    pieces = [piece(i, 20.0) for i in range(30)]  # 600" of wood + kerf
    layouts = nest_boards(pieces)
    assert_valid(layouts, pieces)
    assert len(layouts) <= 4  # 9 pieces per 192" board (9*20 + 8*0.125 = 181) -> 4 boards
    assert [layout.length_in for layout in layouts].count(192) >= 3


def test_first_fit_decreasing_and_shrinking_on_a_known_case():
    pieces = [piece(1, 10.0), piece(2, 150.0), piece(3, 40.0)]  # all three would need 200.25" > 192"
    layouts = nest_boards(pieces)
    assert_valid(layouts, pieces)
    by_id = {q.part_id: layout for layout in layouts for q in layout.pieces}
    assert by_id["P-3"] is by_id["P-2"]  # 150 first, 40 is the next longest and still fits: 190.125"
    assert by_id["P-2"].length_in == 192
    assert by_id["P-1"].length_in == 96  # the 10" left over goes on its own 8 ft board
    assert [layout.stock_id for layout in layouts] == ["2x6_PT_96-1", "2x6_PT_192-1"]


def test_stock_ids_count_per_material_and_length():
    # FFD: 110 | 92+91 (183.125") | 90 -> boards of 120, 192 and 96 inches
    pieces = [piece(1, 90.0), piece(2, 91.0), piece(3, 92.0), piece(4, 110.0), piece(5, 100.0, "2x4_PT")]
    layouts = nest_boards(pieces)
    assert_valid(layouts, pieces)
    assert [layout.stock_id for layout in layouts] == ["2x4_PT_120-1", "2x6_PT_96-1", "2x6_PT_120-1", "2x6_PT_192-1"]
    # two boards of the same length are numbered 1, 2
    twins = nest_boards([piece(1, 100.0), piece(2, 100.0)])  # 200.125" does not fit one board
    assert [layout.stock_id for layout in twins] == ["2x6_PT_120-1", "2x6_PT_120-2"]


def test_multiple_materials_are_nested_separately():
    pieces = [
        piece(1, 50.0, "2x6_PT"),
        piece(2, 50.0, "2x4_PT"),
        piece(3, 30.0, "4x4_PT"),
        piece(4, 30.0, "5/4x6_PT_deck"),
    ]
    layouts = nest_boards(pieces)
    assert_valid(layouts, pieces)
    assert [(layout.material, len(layout.pieces)) for layout in layouts] == [
        ("2x4_PT", 1),
        ("2x6_PT", 1),
        ("4x4_PT", 1),
        ("5/4x6_PT_deck", 1),
    ]
    assert [layout.width_in for layout in layouts] == [3.5, 5.5, 3.5, 5.5]


def test_result_does_not_depend_on_input_order_and_is_deterministic():
    rng = random.Random(7)
    pieces = [piece(i, round(rng.uniform(5, 150), 3)) for i in range(40)]
    first = nest_boards(pieces)
    assert nest_boards(pieces) == first
    shuffled = pieces[:]
    rng.shuffle(shuffled)
    assert nest_boards(shuffled) == first


def test_empty_input_gives_no_layouts():
    assert nest_boards([]) == []


def test_non_board_material_is_rejected():
    with pytest.raises(ValueError, match="not a board"):
        nest_boards([piece(1, 10.0, "3/4_ext_ply")])


@pytest.mark.parametrize("seed", range(25))
def test_randomized_layouts_are_always_valid(seed):
    rng = random.Random(seed)
    materials = ["2x4_PT", "2x6_PT", "2x8_PT", "2x10_PT", "4x4_PT", "5/4x6_PT_deck"]
    pieces = []
    for i in range(rng.randint(1, 60)):
        material = rng.choice(materials)
        longest = lumber_spec(material).stock_lengths_in[-1]
        pieces.append(piece(i, round(rng.uniform(1.0, longest), 3), material))
    kerf = rng.choice([0.0, 0.125, 0.25])
    layouts = nest_boards(pieces, kerf_in=kerf)
    assert_valid(layouts, pieces, kerf=kerf)
    # shrink-to-fit: no board could have been a shorter stock length
    for layout in layouts:
        shorter = [s for s in lumber_spec(layout.material).stock_lengths_in if s < layout.length_in]
        needed = sum(q.w for q in layout.pieces) + kerf * (len(layout.pieces) - 1)
        assert not shorter or needed > shorter[-1] - 1e-9


def test_oversize_error_covers_every_material_not_just_the_first():
    with pytest.raises(PieceTooLongError) as info:
        nest_boards([piece(1, 250.0, "2x6_PT"), piece(2, 130.0, "4x4_PT"), piece(3, 10.0, "2x4_PT")])
    assert info.value.part_ids == ["P-1", "P-2"]
