"""GEO-4: stringers, ledger, decking and curbs of each run (plus determinism, speed and a broad sweep)."""

import json
import math
import random
import time

import pytest

from app.data import lumber_spec
from app.engine_errors import ParamValidationError
from app.templates.ramp import Params, derive
from app.templates.ramp_boards import equal_pieces, layout_boards
from app.templates.ramp_geometry import stringer_profile
from app.templates.ramp_parts import build_parts
from tests.test_ramp_support import assert_invariants, bbox, make, named, world_points


def test_known_case_part_counts():
    params, derived, parts = make(total_rise_in=12, clear_width_in=36)
    run = derived.runs[0]
    assert len(named(parts, "Stringer")) == 4 == derived.stringer_count
    assert len(named(parts, "Ledger")) == 1
    # 5.5 in boards, 1/8 in gap: 25 full boards fit into the sloped length, the remainder is a ripped board
    g, w = params.deck_gap_in, 5.5
    n = math.floor((run.sloped_in + g) / (w + g))
    remainder = run.sloped_in - (n * w + (n - 1) * g)
    assert remainder >= 2 + g
    assert len(named(parts, "Deck board")) == n + 1 == 26
    assert len(named(parts, "Edge curb")) == 4  # sloped length 144.5 in needs 2 segments per side
    assert {p.group for p in parts} == {"run_1", "handrail"}  # a 12 in rise needs handrails
    assert named(parts, "Stringer")[0].material == "2x6_PT"


def test_names_and_order_are_stable_for_one_run():
    _, _, parts = make()
    names = [p.name for p in parts]
    assert names[:5] == ["Stringer"] * 4 + ["Ledger"]
    assert names.index("Deck board") > names.index("Ledger") and names.index("Edge curb") > names.index("Deck board")


@pytest.mark.parametrize("overrides", [{}, {"decking": "3/4_ext_ply"}, {"framing": "2x8_PT", "total_rise_in": 25}, {"total_rise_in": 31, "layout": "straight"}])
def test_invariants(overrides):
    _, _, parts = make(**overrides)
    assert_invariants(parts)


def test_stringers_span_the_run_and_sit_inside_the_clear_width():
    params, derived, parts = make(total_rise_in=20, clear_width_in=40, layout="straight")
    run = derived.runs[0]
    stringers = named(parts, "Stringer")
    assert len(stringers) == derived.stringer_count
    for s in stringers:
        xs = [x for x, _ in s.profile]
        assert min(xs) >= -1e-6 and max(xs) == pytest.approx(run.run_in, abs=1e-3)
        z0, z1 = s.transform.pos[2], s.transform.pos[2] + s.thickness
        assert z0 >= -20 - 1e-6 and z1 <= 20 + 1e-6
    assert stringers[0].transform.pos[2] == pytest.approx(-20)
    assert stringers[-1].transform.pos[2] + stringers[-1].thickness == pytest.approx(20)
    spacing = [b.transform.pos[2] - a.transform.pos[2] for a, b in zip(stringers, stringers[1:], strict=False)]
    assert max(spacing) - min(spacing) < 1e-2
    assert stringers[0].profile == [(x, y) for x, y in stringer_profile(run.run_in, 12, 1.0, 5.5, 0.0)]


def test_stringer_cut_notes():
    _, _, parts = make(total_rise_in=12)
    assert named(parts, "Stringer")[0].cut_notes == ["85.2° level cut at bottom end (sits on grade)", "4.8° plumb cut at top end"]
    # the second run of a straight ramp starts 15 in up, above the clipped zone: plumb cuts at both ends
    _, _, parts = make(total_rise_in=31, layout="straight")
    assert named(parts, "Stringer", "run_2")[0].cut_notes == ["4.8° plumb cut at both ends"]


def test_ledger_is_one_on_the_last_run_and_spans_the_width():
    params, derived, parts = make(total_rise_in=31, layout="straight")
    ledgers = named(parts, "Ledger")
    assert len(ledgers) == 1 and ledgers[0].group == "run_2"
    ledger = ledgers[0]
    assert ledger.thickness == pytest.approx(36) and ledger.cut_notes == ["Square cut both ends"]
    (x0, _, z0), (x1, y1, z1) = bbox([ledger])
    assert z0 == pytest.approx(-18) and z1 == pytest.approx(18)
    assert x0 == pytest.approx(derived.runs[-1].x_end) and x1 == pytest.approx(derived.runs[-1].x_end + 1.5)
    assert y1 == pytest.approx(31 - 1.0 / math.cos(derived.slope_angle_rad), abs=1e-3)


def test_ledger_never_goes_below_grade_on_a_low_ramp():
    _, _, parts = make(total_rise_in=4)
    (ledger,) = named(parts, "Ledger")
    assert bbox([ledger])[0][1] >= -1e-3
    assert any(n.startswith("Rip to") for n in ledger.cut_notes)


def test_top_of_the_decking_meets_the_porch():
    for overrides in ({"total_rise_in": 12}, {"total_rise_in": 31, "layout": "straight"}, {"total_rise_in": 30, "decking": "3/4_ext_ply"}, {"total_rise_in": 2.5}):
        params, derived, parts = make(**overrides)
        decking = [p for p in parts if p.name in ("Deck board", "Deck panel") and p.group == f"run_{derived.run_count}"]
        assert bbox(decking)[1][1] == pytest.approx(params.total_rise_in, abs=1 / 16), overrides


def test_deck_boards_are_full_stock_size_unless_ripped_or_bevelled():
    spec = lumber_spec("5/4x6_PT_deck")
    _, _, parts = make(total_rise_in=31, layout="straight")
    plain = [p for p in named(parts, "Deck board") if not p.cut_notes]
    assert len(plain) > 40
    for p in plain:
        (a, b, c, d) = p.profile
        long_edge = math.dist(a, b)
        assert long_edge == pytest.approx(spec.width_in, abs=2e-3)
        assert math.dist(b, c) == pytest.approx(spec.thickness_in, abs=2e-3)
        assert p.thickness == pytest.approx(36)


def test_ground_level_boards_taper_to_grade_and_say_so():
    _, _, parts = make(total_rise_in=12)
    boards = named(parts, "Deck board")
    assert "Bevel bottom edge to sit on grade" in boards[0].cut_notes
    assert min(y for _, y in boards[0].profile) == pytest.approx(0)
    assert boards[-1].cut_notes[0].startswith("Rip to ")
    assert not any("Bevel" in n for p in boards[5:] for n in p.cut_notes)


@pytest.mark.parametrize("gap", [0.0, 0.125, 0.25, 0.5])
def test_layout_never_yields_a_sliver_board(gap):
    w = 5.5
    for hundredths in range(300, 20000, 7):
        length = hundredths / 100
        spans = layout_boards(length, w, gap)
        assert spans[0].start == 0 and spans[-1].end == pytest.approx(length, abs=1e-9)
        for a, b in zip(spans, spans[1:], strict=False):
            assert b.start - a.end >= gap - 1e-9
        for s in spans:
            if s.ripped:
                assert s.width >= 2.0 - 1e-9
            else:
                assert s.width == pytest.approx(w)
            assert s.width <= w + 1e-9


def test_layout_short_lengths_never_exceed_stock_width():
    for length in (1.0, 3.0, 5.4, 5.5, 6.0, 7.4, 7.6, 8.0):
        spans = layout_boards(length, 5.5, 0.125)
        assert all(s.width <= 5.5 + 1e-9 for s in spans) and spans[-1].end == pytest.approx(length)


def test_equal_pieces():
    assert equal_pieces(100, 96) == [(0, 50), (50, 100)]
    assert equal_pieces(96, 96) == [(0, 96)]
    pieces = equal_pieces(300, 96, 0.125)
    assert len(pieces) == 4 and pieces[-1][1] == 300 and pieces[1][0] - pieces[0][1] == pytest.approx(0.125)


@pytest.mark.parametrize("width", [30, 36, 48, 49, 60])
def test_plywood_panels_never_exceed_a_sheet(width):
    _, derived, parts = make(total_rise_in=30, clear_width_in=width, decking="3/4_ext_ply")
    panels = named(parts, "Deck panel")
    assert panels and not named(parts, "Deck board")
    per_run = len(panels) // derived.run_count
    assert per_run == (2 if width > 48 else 1) * math.ceil(derived.runs[0].sloped_in / 96)
    for p in panels:
        assert p.material == "3/4_ext_ply"
        xs = [x for x, _ in p.profile]
        ys = [y for _, y in p.profile]
        long_edge = max(math.dist(p.profile[i], p.profile[(i + 1) % len(p.profile)]) for i in range(len(p.profile)))
        assert long_edge <= 96 + 1e-3 and p.thickness <= 48 + 1e-9
        assert max(xs) - min(xs) <= 96 and max(ys) - min(ys) <= 96
    covered = sorted((p.transform.pos[2], p.transform.pos[2] + p.thickness) for p in panels if p.group == "run_1")
    assert covered[0][0] == pytest.approx(-width / 2) and covered[-1][1] == pytest.approx(width / 2)


def test_edge_curbs():
    params, derived, parts = make(total_rise_in=12)
    curbs = named(parts, "Edge curb")
    assert all(c.material == "2x4_PT" and c.thickness == 1.5 for c in curbs)
    assert sorted({c.transform.pos[2] for c in curbs}) == [-18.0, 16.5]
    assert all(c.cut_notes == ["Splice: butt joint over a stringer"] for c in curbs)
    for c in curbs:
        (a, b, _, d) = c.profile
        assert math.dist(a, b) <= 144 + 1e-6 and math.dist(a, d) == pytest.approx(3.5, abs=1e-2)
    _, _, short = make(total_rise_in=6)
    assert all(c.cut_notes == ["Square cut both ends"] for c in named(short, "Edge curb")) and len(named(short, "Edge curb")) == 2
    _, _, none = make(edge_curb=False)
    assert not named(none, "Edge curb")


def test_very_low_ramp_has_decking_but_no_stringers_or_ledger():
    _, derived, parts = make(total_rise_in=2)
    assert not derived.runs[0].has_stringers
    assert not named(parts, "Stringer") and not named(parts, "Ledger")
    assert named(parts, "Deck board")
    assert_invariants(parts)
    assert bbox(named(parts, "Deck board"))[1][1] == pytest.approx(2, abs=1 / 16)


def test_deterministic():
    params = Params(total_rise_in=31, layout="straight", handrails="yes")
    a, b = build_parts(params, derive(params)), build_parts(params, derive(params))
    assert a == b
    dump = lambda parts: json.dumps([p.model_dump(mode="json") for p in parts], sort_keys=True)  # noqa: E731
    assert dump(a) == dump(b)


def test_build_parts_is_fast():
    params = Params(total_rise_in=30, handrails="yes")
    derived = derive(params)
    build_parts(params, derived)  # warm caches
    start = time.perf_counter()
    for _ in range(5):
        build_parts(params, derived)
    assert (time.perf_counter() - start) / 5 < 0.15  # spec: < 150 ms (about 3 ms in practice)


def test_random_sweep_builds_and_holds_all_invariants():
    rng = random.Random(20240607)
    built = skipped = 0
    for _ in range(400):
        params = Params(
            total_rise_in=round(rng.uniform(1, 60), 1),
            clear_width_in=rng.choice([30, 36, 42, 48, 55, 60, round(rng.uniform(30, 60), 1)]),
            layout=rng.choice(["auto", "straight", "switchback"]),
            slope_ratio=round(rng.uniform(8, 16), 1),
            landing_length_in=rng.choice([36, 60, 72, 120, 240]),
            framing=rng.choice(["2x6_PT", "2x8_PT"]),
            stringer_spacing_in=rng.choice([12, 16, 19.2, 24]),
            decking=rng.choice(["5/4x6_PT_deck", "3/4_ext_ply"]),
            deck_gap_in=rng.choice([0, 0.125, 0.25, 0.5]),
            handrails=rng.choice(["auto", "yes", "no"]),
            edge_curb=rng.choice([True, False]),
        )
        derived = derive(params)
        try:
            parts = build_parts(params, derived)
        except ParamValidationError as exc:
            assert "switchback" in str(exc)
            skipped += 1
            continue
        built += 1
        assert_invariants(parts)
        assert named(parts, "Deck board") or named(parts, "Deck panel")
        assert len(named(parts, "Ledger")) == (1 if derived.runs[-1].has_stringers else 0)
        last = f"run_{derived.run_count}"
        top = bbox([p for p in parts if p.name in ("Deck board", "Deck panel") and p.group == last])[1][1]
        assert top == pytest.approx(params.total_rise_in, abs=1 / 16)
        for run in derived.runs:
            group = f"run_{run.index + 1}"
            count = len(named(parts, "Stringer", group))
            assert count == (derived.stringer_count if run.has_stringers else 0)
            for s in named(parts, "Stringer", group):
                xs = [x for pt in world_points(s) for x in (pt[0],)]
                assert min(xs) >= min(run.x_start, run.x_end) - 1e-3 and max(xs) <= max(run.x_start, run.x_end) + 1e-3
    assert built > 300 and skipped < 100
