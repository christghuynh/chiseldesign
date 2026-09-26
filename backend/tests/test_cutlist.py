"""GEO-10: part extents, labelling and cut-list rows."""

import pytest

from app.cutlist import (
    actual_dims,
    build_cut_list,
    label_for_index,
    label_parts,
    part_extents,
    part_length,
    shape_signature,
    sheet_piece_dims,
)
from tests.geo_helpers import SPEC_FILES, load_fixture, make_part, rect_profile, rotate_profile


@pytest.fixture(params=SPEC_FILES)
def fixture_parts(request):
    return load_fixture(request.param).spec.parts


# --- extents / length ---------------------------------------------------------------------------


def test_length_of_a_board_part_is_its_extrusion_depth():
    part = make_part(thickness=64.5)
    assert part_extents(part) == (5.5, 1.5, 64.5)
    assert part_length(part) == 64.5


def test_length_of_a_profile_lengthed_part_is_the_profile_extent():
    rim = make_part(name="Rim", profile=rect_profile(120.0, 5.5), thickness=1.5)
    assert part_length(rim) == 120.0


def test_length_of_a_parallelogram_follows_its_long_edges():
    # sheared 100" x 5" parallelogram: its bounding rectangle along the long edge is 101" (the shear adds 1")
    profile = [(0.0, 0.0), (100.0, 0.0), (101.0, 5.0), (1.0, 5.0)]
    part = make_part(name="Curb", material="2x4_PT", profile=profile, thickness=1.5)
    along, across, depth = part_extents(part)
    assert along == pytest.approx(101.0, abs=0.01)
    assert across == pytest.approx(5.0, abs=0.01)
    assert depth == 1.5
    assert part_length(part) == along


def test_length_of_a_sloped_parallelogram_is_the_edge_length_not_the_bounding_box():
    # A 90" long, 3.5" tall curb rising 7.5": its length along the slope is ~90.3", not 90 or 93.5
    profile = [(0.0, 0.0), (90.0, 7.5), (89.709, 10.988), (-0.291, 3.488)]
    part = make_part(name="Edge curb", material="2x4_PT", profile=profile, thickness=1.5)
    assert part_length(part) == pytest.approx((90.0**2 + 7.5**2) ** 0.5, abs=0.01)


def test_length_of_the_level_cut_stringer_quadrilateral():
    profile = [(78.27, 0.0), (180.0, 8.477), (180.0, 13.997), (12.042, 0.0)]
    part = make_part(name="Stringer", profile=profile, thickness=1.5)
    length = part_length(part)
    # the longest edge is (12.042,0)->(180,13.997), 168.5" long; the board must be at least that long
    assert 168.5 <= length <= 172.0
    assert length > 1.5


def test_extents_are_invariant_to_start_vertex_and_placement():
    base = make_part(profile=[(0.0, 0.0), (100.0, 0.0), (101.0, 5.0), (1.0, 5.0)], thickness=1.5)
    shifted = make_part(profile=[(1.0, 5.0), (0.0, 0.0), (100.0, 0.0), (101.0, 5.0)], thickness=1.5)
    assert part_extents(base) == part_extents(shifted)


def test_extents_of_a_rectangle_do_not_depend_on_rotation_in_plane():
    a = make_part(profile=rect_profile(30.0, 3.5), thickness=1.5)
    b = make_part(profile=rotate_profile(rect_profile(30.0, 3.5), 37.0, 12.0, 5.0), thickness=1.5)
    assert part_extents(a)[:2] == pytest.approx(part_extents(b)[:2], abs=1e-3)


# --- shape signature ----------------------------------------------------------------------------


def test_shape_signature_ignores_translation_rotation_and_start_vertex():
    base = [(0.0, 0.0), (100.0, 0.0), (101.0, 5.0), (1.0, 5.0)]
    sig = shape_signature(base)
    assert shape_signature([(x + 40.0, y - 3.0) for x, y in base]) == sig
    assert shape_signature(base[2:] + base[:2]) == sig
    assert shape_signature(rotate_profile(base, 33.0, 5.0, 9.0)) == sig
    assert shape_signature(list(reversed(base))) == sig  # clockwise input is normalised


def test_shape_signature_tells_different_shapes_apart():
    assert shape_signature(rect_profile(1.5, 5.5)) != shape_signature(rect_profile(1.5, 5.75))
    assert shape_signature(rect_profile(2, 2)) != shape_signature([(0.0, 0.0), (2.0, 0.0), (3.0, 2.0), (1.0, 2.0)])


# --- labelling ----------------------------------------------------------------------------------


def test_label_for_index():
    assert [label_for_index(i) for i in (0, 1, 25, 26, 27, 51, 52, 701, 702)] == ["A", "B", "Z", "AA", "AB", "AZ", "BA", "ZZ", "AAA"]


def test_identical_parts_share_a_label_and_ids_count_up():
    parts = [make_part(pos=(0, 0, float(i))) for i in range(3)]
    out = label_parts(parts)
    assert {p.label for p in out} == {"A"}
    assert [p.id for p in out] == ["A-1", "A-2", "A-3"]


def test_parts_at_different_positions_but_the_same_shape_group_together():
    strip = rect_profile(5.5, 1.0)
    parts = [
        make_part(name="Deck board", material="5/4x6_PT_deck", profile=[(x + dx, y + dy) for x, y in strip], thickness=36.0, pos=(dx, 0, dz))
        for dx, dy, dz in [(0.0, 0.0, 0.0), (6.0, 0.4, 0.0), (12.0, 0.8, -3.0), (99.0, 4.0, 10.0)]
    ]
    assert len({p.label for p in label_parts(parts)}) == 1


def test_a_part_rotated_within_its_plane_still_groups():
    a = make_part(profile=rect_profile(1.5, 5.5), thickness=60.0)
    b = make_part(profile=rotate_profile(rect_profile(1.5, 5.5), 90.0, 10.0, 0.0), thickness=60.0)
    assert len({p.label for p in label_parts([a, b])}) == 1


def test_parts_that_differ_get_different_labels():
    parts = [
        make_part(),
        make_part(thickness=61.0),
        make_part(name="Ledger"),
        make_part(material="2x8_PT", profile=rect_profile(1.5, 7.25)),
        make_part(cut_notes=["15.0° plumb cut at top end"]),
    ]
    assert len({p.label for p in label_parts(parts)}) == 5


def test_labels_order_by_material_then_descending_length():
    parts = [
        make_part(name="Short 2x6", material="2x6_PT", thickness=40.0),
        make_part(name="Post", material="4x4_PT", profile=rect_profile(3.5, 3.5), thickness=36.0),
        make_part(name="Long 2x6", material="2x6_PT", thickness=100.0),
        make_part(name="Brace", material="2x4_PT", profile=rect_profile(1.5, 3.5), thickness=20.0),
        make_part(name="Deck board", material="5/4x6_PT_deck", profile=rect_profile(5.5, 1.0), thickness=36.0),
        make_part(name="Mid 2x6", material="2x6_PT", thickness=70.0),
    ]
    out = label_parts(parts)
    by_label = {p.label: p for p in out}
    ordered = [by_label[k] for k in sorted(by_label)]
    assert [p.name for p in ordered] == ["Brace", "Long 2x6", "Mid 2x6", "Short 2x6", "Post", "Deck board"]
    assert [p.label for p in ordered] == ["A", "B", "C", "D", "E", "F"]


def test_equal_length_ties_break_by_name_then_notes():
    parts = [make_part(name="Zed"), make_part(name="Ape", cut_notes=["b"]), make_part(name="Ape", cut_notes=["a"])]
    out = label_parts(parts)
    assert [(p.label, p.name, p.cut_notes) for p in out] == [("C", "Zed", []), ("B", "Ape", ["b"]), ("A", "Ape", ["a"])]


def test_labelling_does_not_touch_the_inputs():
    parts = [make_part(id="X-9", label="X")]
    out = label_parts(parts)
    assert parts[0].id == "X-9" and parts[0].label == "X"
    assert out[0] is not parts[0] and out[0].id == "A-1"
    out[0].profile.append((9.0, 9.0))
    assert len(parts[0].profile) == 4  # deep copy


def test_labelling_is_deterministic(fixture_parts):
    first = label_parts(fixture_parts)
    second = label_parts(fixture_parts)
    assert first == second
    assert build_cut_list(first) == build_cut_list(second)


def test_relabelling_labelled_parts_gives_the_same_labels(fixture_parts):
    once = label_parts(fixture_parts)
    twice = label_parts(once)
    assert [(p.label, p.id) for p in once] == [(p.label, p.id) for p in twice]


def test_labelling_ignores_input_order_for_label_assignment():
    parts = [make_part(name="Ledger", thickness=36.0), make_part(name="Joist", thickness=80.0), make_part(name="Post", thickness=30.0)]
    forward = {p.name: p.label for p in label_parts(parts)}
    backward = {p.name: p.label for p in label_parts(list(reversed(parts)))}
    assert forward == backward


def test_unknown_material_raises_a_clear_error():
    with pytest.raises(KeyError, match="Unknown material 'unobtainium'"):
        label_parts([make_part(material="unobtainium")])
    with pytest.raises(KeyError, match="Unknown material"):
        build_cut_list([make_part(material="unobtainium", label="A", id="A-1")])


# --- cut list rows ------------------------------------------------------------------------------


def test_row_for_a_board_uses_actual_dims_and_ft_in_display():
    rows = build_cut_list(label_parts([make_part(thickness=64.5, cut_notes=["Square cut both ends"])]))
    assert len(rows) == 1
    row = rows[0]
    assert row.actual_dims == "1-1/2 × 5-1/2"  # actual, not the nominal 2x6
    assert row.length_in == 64.5
    assert row.length_display == "5' 4-1/2\""
    assert (row.label, row.name, row.material, row.qty) == ("A", "Joist", "2x6_PT", 1)
    assert row.part_ids == ["A-1"]
    assert row.cut_notes == ["Square cut both ends"]


def test_actual_dims_for_other_materials():
    assert actual_dims(make_part(material="4x4_PT")) == "3-1/2 × 3-1/2"
    assert actual_dims(make_part(material="2x4_PT")) == "1-1/2 × 3-1/2"
    assert actual_dims(make_part(material="5/4x6_PT_deck")) == "1 × 5-1/2"


def test_sheet_pieces_use_three_part_dims():
    piece = make_part(name="Panel", material="3/4_ext_ply", profile=rect_profile(30.0, 20.0), thickness=0.703)
    assert sheet_piece_dims(piece) == (30.0, 20.0)
    assert actual_dims(piece) == "11/16 × 30 × 20"
    # extruded the other way round: thickness is the long side
    other = make_part(name="Panel", material="3/4_ext_ply", profile=rect_profile(0.703, 20.0), thickness=30.0)
    assert sheet_piece_dims(other) == (30.0, 20.0)
    assert build_cut_list(label_parts([piece]))[0].length_in == 30.0


def test_sum_of_qty_is_the_number_of_parts_and_every_part_listed_once(fixture_parts):
    labelled = label_parts(fixture_parts)
    rows = build_cut_list(labelled)
    assert sum(r.qty for r in rows) == len(fixture_parts)
    listed = [pid for r in rows for pid in r.part_ids]
    assert sorted(listed) == sorted(p.id for p in labelled)
    assert len({r.label for r in rows}) == len(rows)
    for r in rows:
        assert r.qty == len(r.part_ids)
        assert r.length_in > 0


def test_fixture_deck_boards_of_the_same_shape_land_in_one_row():
    parts = load_fixture("ramp_switchback.json").spec.parts
    rows = build_cut_list(label_parts(parts))
    deck = [r for r in rows if r.name == "Deck board"]
    # the fixture has many deck boards but only a handful of distinct shapes
    assert sum(r.qty for r in deck) == sum(1 for p in parts if p.name == "Deck board")
    assert len(deck) < sum(r.qty for r in deck)
    assert max(r.qty for r in deck) > 5


def test_rows_are_ordered_by_label_and_labels_by_material_then_length(fixture_parts):
    rows = build_cut_list(label_parts(fixture_parts))
    assert [r.label for r in rows] == [label_for_index(i) for i in range(len(rows))]
    keys = [(r.material, -r.length_in) for r in rows]
    assert keys == sorted(keys)


def test_build_cut_list_is_a_pure_function_of_labelled_parts():
    labelled = label_parts([make_part(), make_part(name="Ledger", thickness=90.0)])
    assert build_cut_list(labelled) == build_cut_list(labelled)
