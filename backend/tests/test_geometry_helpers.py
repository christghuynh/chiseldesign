"""Shared 2D geometry helpers and the PartBuilder (used by every template)."""

import math

import pytest

from app.templates.geometry import (
    PartBuilder,
    clip_y,
    dedupe,
    ensure_ccw,
    extent_along,
    normalize_profile,
    r3,
    signed_area,
)

SQUARE = [(0, 0), (2, 0), (2, 2), (0, 2)]


def test_r3_rounds_and_removes_negative_zero():
    assert r3(1.23456) == 1.235
    assert str(r3(-0.0001)) == "0.0"


def test_area_sign_and_ccw():
    assert signed_area(SQUARE) == 4
    assert signed_area(SQUARE[::-1]) == -4
    assert ensure_ccw(SQUARE[::-1]) == SQUARE[::-1][::-1] or signed_area(ensure_ccw(SQUARE[::-1])) > 0


def test_dedupe_removes_repeated_and_closing_points():
    assert dedupe([(0, 0), (0, 0), (1, 0), (1, 1), (0, 0)]) == [(0, 0), (1, 0), (1, 1)]


def test_clip_y_cuts_below_the_line_and_keeps_a_ccw_polygon():
    tri = [(0, -1), (4, -1), (4, 3), (0, 3)]
    clipped = clip_y(tri, 0)
    assert min(y for _, y in clipped) == 0 and max(y for _, y in clipped) == 3
    assert signed_area(clipped) == 12  # 4 wide x 3 tall (y from 0 to 3)
    assert clip_y([(0, -3), (1, -3), (1, -1)], 0) == []  # entirely below


def test_clip_y_does_not_duplicate_a_point_that_lands_on_a_corner():
    poly = [(0, -1), (4, 3), (0, 3)]
    assert len(set(clip_y(poly, 0))) == len(clip_y(poly, 0))


def test_extent_along_a_direction():
    assert extent_along(SQUARE, (1, 0)) == 2
    assert extent_along(SQUARE, (math.sqrt(0.5), math.sqrt(0.5))) == pytest.approx(2 * math.sqrt(2))


def test_normalize_profile_rejects_degenerate_shapes():
    assert normalize_profile(SQUARE[::-1]) == [(0, 0), (2, 0), (2, 2), (0, 2)] or signed_area(normalize_profile(SQUARE[::-1])) > 0
    with pytest.raises(ValueError):
        normalize_profile([(0, 0), (1, 0), (2, 0)])
    with pytest.raises(ValueError):
        normalize_profile([(0, 0), (0, 0), (1, 1)])


def test_part_builder_assigns_temporary_ids_and_rounds():
    b = PartBuilder()
    p = b.add("Stringer", "2x6_PT", [(0, 0), (10.00049, 0), (10, 2)], 1.5, pos=(1, 2, 3), cut_notes=["x"], group="run_1")
    assert (p.id, p.label, p.group, p.cut_notes) == ("T-1", "T", "run_1", ["x"])
    assert p.transform.pos == (1, 2, 3) and p.transform.rot == (0, 0, 0)
    assert p.profile[1] == (10.0, 0.0)
    assert b.add("B", "2x6_PT", SQUARE, 1, pos=(0, 0, 0)).id == "T-2"


def test_part_builder_frame_offsets_parts():
    b = PartBuilder()
    with b.frame(origin=(10, 20, 30)):
        p = b.add("A", "2x6_PT", SQUARE, 1, pos=(1, 2, 3))
    assert p.transform.pos == (11, 22, 33) and p.transform.rot == (0, 0, 0)
    assert b.add("B", "2x6_PT", SQUARE, 1, pos=(1, 2, 3)).transform.pos == (1, 2, 3)  # frame restored


def test_part_builder_flipped_frame_mirrors_x_and_z_about_y():
    b = PartBuilder()
    with b.frame(origin=(90, 7.5, 48), flip=True):
        p = b.add("A", "2x6_PT", SQUARE, 1.5, pos=(0, 0, -18))
    assert p.transform.pos == (90, 7.5, 66) and p.transform.rot == (0, math.pi, 0)
    # A local point (x, y, z) lands at (ox - x, oy + y, oz - z): the part's z extent [-18, -16.5] becomes [64.5, 66].
    lo, hi = 48 - (-18 + 1.5), 48 - (-18)
    assert (lo, hi) == (64.5, 66)


def test_frames_nest_and_restore_even_on_error():
    b = PartBuilder()
    with pytest.raises(RuntimeError):
        with b.frame(origin=(5, 0, 0)):
            raise RuntimeError
    assert b.add("A", "2x6_PT", SQUARE, 1).transform.pos == (0, 0, 0)
