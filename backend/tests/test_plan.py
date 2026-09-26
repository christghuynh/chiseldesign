"""B5: build_plan end to end, checked against the same consistency rules as tests/test_fixtures.py."""

import time
from collections import Counter

import pytest

from app import data
from app.cutlist import label_parts
from app.models import Part, Plan
from app.plan import build_plan
from app.util.units import format_ft_in
from tests.geo_helpers import SPEC_FILES, load_fixture, make_part, rect_profile


@pytest.fixture(params=SPEC_FILES)
def fixture(request):
    return load_fixture(request.param)


@pytest.fixture
def labelled(fixture):
    return label_parts(fixture.spec.parts)


def check_consistency(plan: Plan, parts: list[Part], excluded: frozenset[str] = frozenset()) -> None:
    """The cut list covers every part once; layouts place every (non-excluded) part once without overlap or
    overflow; the shopping list matches the layouts; the totals add up."""
    part_ids = sorted(p.id for p in parts)
    listed = [pid for row in plan.cut_list for pid in row.part_ids]
    assert sorted(listed) == part_ids
    by_id = {p.id: p for p in parts}
    for row in plan.cut_list:
        assert row.qty == len(row.part_ids)
        assert row.length_display == format_ft_in(row.length_in)
        assert {by_id[pid].label for pid in row.part_ids} == {row.label}
    assert len({row.label for row in plan.cut_list}) == len(plan.cut_list)

    placed = [q.part_id for layout in plan.layouts for q in layout.pieces]
    assert sorted(placed) == sorted(pid for pid in part_ids if pid not in excluded)
    row_of = {pid: row for row in plan.cut_list for pid in row.part_ids}
    for layout in plan.layouts:
        pieces = sorted(layout.pieces, key=lambda q: (q.x, q.y))
        if layout.kind == "board":
            assert pieces[0].x >= 0
            for a, b in zip(pieces, pieces[1:], strict=False):
                assert b.x >= a.x + a.w - 1e-6, f"{layout.stock_id}: {a.part_id} overlaps {b.part_id}"
            assert pieces[-1].x + pieces[-1].w <= layout.length_in + 1e-6, layout.stock_id
            for q in pieces:
                assert q.w == pytest.approx(row_of[q.part_id].length_in, abs=1e-3)
            assert layout.utilization == pytest.approx(sum(q.w for q in pieces) / layout.length_in, abs=1e-3)
        else:
            for i, a in enumerate(pieces):
                assert a.x >= 0 and a.y >= 0
                assert a.x + a.w <= layout.length_in + 1e-6 and a.y + a.h <= layout.width_in + 1e-6, layout.stock_id
                for b in pieces[i + 1 :]:
                    assert (
                        b.x >= a.x + a.w - 1e-6 or a.x >= b.x + b.w - 1e-6 or b.y >= a.y + a.h - 1e-6 or a.y >= b.y + b.h - 1e-6
                    ), f"{layout.stock_id}: {a.part_id} overlaps {b.part_id}"
            assert layout.utilization == pytest.approx(sum(q.w * q.h for q in pieces) / (layout.length_in * layout.width_in), abs=1e-3)
    ids = [layout.stock_id for layout in plan.layouts]
    assert len(ids) == len(set(ids))

    for item in plan.shopping:
        assert item.qty > 0
        assert item.subtotal == pytest.approx(item.qty * item.unit_price, abs=0.005)
    assert plan.subtotal == pytest.approx(sum(i.subtotal for i in plan.shopping), abs=0.005)
    assert plan.tax == pytest.approx(round(plan.subtotal * 0.13, 2), abs=0.005)
    assert plan.total == pytest.approx(plan.subtotal + plan.tax, abs=0.005)
    bought = {i.key: i.qty for i in plan.shopping}
    needed = Counter(
        f"{layout.material}_{int(layout.width_in)}x{int(layout.length_in)}" if layout.kind == "sheet" else f"{layout.material}_{int(layout.length_in)}"
        for layout in plan.layouts
    )
    for key, qty in needed.items():
        assert bought[key] == qty


def test_build_plan_on_the_fixture_ramps(fixture, labelled):
    plan = build_plan(labelled, fixture.spec.meta)
    assert isinstance(plan, Plan)
    assert Plan.model_validate(plan.model_dump()) == plan
    check_consistency(plan, labelled)
    assert all(layout.kind == "board" for layout in plan.layouts)
    keys = {i.key for i in plan.shopping}
    assert {"deck_screws_box", "post_base"} <= keys


def test_plan_totals_are_consistent_with_the_shopping_list(fixture, labelled):
    plan = build_plan(labelled, fixture.spec.meta)
    assert plan.subtotal == round(sum(i.subtotal for i in plan.shopping), 2)
    assert plan.total == round(plan.subtotal + plan.tax, 2)


def test_contractor_quote_and_savings(fixture, labelled):
    plan = build_plan(labelled, {"contractor_quote_cad": 4000.0})
    assert plan.contractor_quote == 4000.0
    assert plan.savings == round(4000.0 - plan.total, 2)
    assert plan.savings > 0
    # fixture meta carries the same quote
    assert build_plan(labelled, fixture.spec.meta).contractor_quote == fixture.spec.meta["contractor_quote_cad"]


def test_no_quote_means_no_savings(labelled):
    for meta in (None, {}, {"notes": "x"}, {"contractor_quote_cad": None}):
        plan = build_plan(labelled, meta)
        assert plan.contractor_quote is None and plan.savings is None
    assert build_plan(labelled, {"contractor_quote_cad": 3500}).contractor_quote == 3500.0  # ints are fine


def test_placeholder_flag_follows_the_price_entries(labelled, monkeypatch):
    assert build_plan(labelled).has_placeholder_prices is True
    real = {k: v.model_copy(update={"placeholder": False}) for k, v in data.prices().items()}
    monkeypatch.setattr(data, "prices", lambda: real)
    assert build_plan(labelled).has_placeholder_prices is False
    # one placeholder hardware entry is enough to flag the plan
    real["post_base"] = real["post_base"].model_copy(update={"placeholder": True})
    assert build_plan(labelled).has_placeholder_prices is True


def test_placeholder_flag_from_a_lumber_line_alone(monkeypatch):
    parts = label_parts([make_part(thickness=60.0)])
    real = {k: v.model_copy(update={"placeholder": False}) for k, v in data.prices().items()}
    monkeypatch.setattr(data, "prices", lambda: real)
    assert build_plan(parts).has_placeholder_prices is False
    real["2x6_PT_96"] = real["2x6_PT_96"].model_copy(update={"placeholder": True})
    assert build_plan(parts).has_placeholder_prices is True


def test_changing_a_price_changes_the_plan_total(labelled, monkeypatch):
    before = build_plan(labelled).total
    patched = {k: v.model_copy() for k, v in data.prices().items()}
    patched["deck_screws_box"] = patched["deck_screws_box"].model_copy(update={"price_cad": 1000.0})
    monkeypatch.setattr(data, "prices", lambda: patched)
    assert build_plan(labelled).total > before + 900


def test_build_plan_is_deterministic(labelled, fixture):
    assert build_plan(labelled, fixture.spec.meta) == build_plan(labelled, fixture.spec.meta)


def test_oversize_boards_stay_in_the_cut_list_with_a_note_and_the_plan_still_builds():
    parts = label_parts(
        [
            make_part(name="Long stringer", thickness=250.0),  # longer than the 16' (192") 2x6 maximum
            make_part(name="Joist", thickness=60.0),
            make_part(name="Joist", thickness=60.0, pos=(0, 0, 10)),
            make_part(name="Landing post", material="4x4_PT", profile=rect_profile(3.5, 3.5), thickness=130.0),  # 4x4 stops at 10'
        ]
    )
    plan = build_plan(parts)
    note_2x6 = "Longer than the longest board sold (16' 0\"); cannot be bought as one piece"
    note_4x4 = "Longer than the longest board sold (10' 0\"); cannot be bought as one piece"
    rows = {row.name: row for row in plan.cut_list}
    assert rows["Long stringer"].cut_notes == [note_2x6]
    assert rows["Landing post"].cut_notes == [note_4x4]
    assert rows["Joist"].cut_notes == []  # only the oversize rows are annotated
    long_id, post_id = rows["Long stringer"].part_ids[0], rows["Landing post"].part_ids[0]
    check_consistency(plan, parts, excluded=frozenset({long_id, post_id}))
    assert {q.part_id for layout in plan.layouts for q in layout.pieces} == set(rows["Joist"].part_ids)
    # no lumber for the oversize pieces: the two 60" joists share one 144" board (120.125"); the post base is
    # still counted because hardware comes from all parts
    assert [i.key for i in plan.shopping] == ["2x6_PT_144", "post_base"]
    assert rows["Long stringer"].length_in == 250.0


def test_existing_notes_are_kept_before_the_oversize_note():
    parts = label_parts([make_part(thickness=300.0, cut_notes=["Square cut both ends"])])
    plan = build_plan(parts)
    assert plan.cut_list[0].cut_notes == ["Square cut both ends", "Longer than the longest board sold (16' 0\"); cannot be bought as one piece"]
    assert plan.layouts == [] and plan.shopping == [] and plan.total == 0.0


def test_all_parts_oversize_still_returns_a_valid_plan():
    plan = build_plan(label_parts([make_part(thickness=500.0)]))
    assert Plan.model_validate(plan.model_dump()) == plan
    assert plan.subtotal == plan.tax == plan.total == 0.0
    assert plan.has_placeholder_prices is False


def test_plywood_decking_exercises_the_sheet_path():
    def panel(w: float, h: float, name: str = "Deck panel", **kw):
        return make_part(name=name, material="3/4_ext_ply", profile=rect_profile(w, h), thickness=0.703, **kw)

    parts = label_parts(
        [panel(96.0, 48.0, "Full panel")] * 2  # two full sheets
        + [panel(40.0, 30.0, pos=(0, 0, float(i))) for i in range(5)]
        + [make_part(name="Joist", thickness=60.0), make_part(name="Joist", thickness=60.0)]
        + [panel(100.0, 20.0, "Oversize panel")]
    )
    plan = build_plan(parts, {"contractor_quote_cad": 900.0})
    oversize_id = next(p.id for p in parts if p.name == "Oversize panel")
    check_consistency(plan, parts, excluded=frozenset({oversize_id}))
    sheets = [layout for layout in plan.layouts if layout.kind == "sheet"]
    assert sheets and all(layout.stock_id.startswith("3/4_ext_ply_48x96-") for layout in sheets)
    assert sum(len(layout.pieces) for layout in sheets) == 7
    line = next(i for i in plan.shopping if i.key == "3/4_ext_ply_48x96")
    assert line.qty == len(sheets) and line.unit == "sheet"
    rows = {row.name: row for row in plan.cut_list}
    assert rows["Full panel"].actual_dims == "11/16 × 96 × 48" and rows["Full panel"].qty == 2
    assert rows["Deck panel"].actual_dims == "11/16 × 40 × 30" and rows["Deck panel"].qty == 5
    assert rows["Oversize panel"].cut_notes == [
        "Larger than a full sheet (4' 0\" x 8' 0\"); cannot be bought as one piece"
    ]
    assert plan.savings == round(900.0 - plan.total, 2)
    assert any(layout.kind == "board" for layout in plan.layouts)  # boards and sheets side by side


def test_unlabelled_or_unknown_material_parts_fail_clearly():
    with pytest.raises(KeyError, match="Unknown material"):
        build_plan([make_part(material="unobtainium", label="A", id="A-1")])


def test_build_plan_is_fast_on_the_fixture_ramps(fixture, labelled, capsys):
    build_plan(labelled, fixture.spec.meta)  # warm caches
    start = time.perf_counter()
    for _ in range(5):
        build_plan(labelled, fixture.spec.meta)
    elapsed_ms = (time.perf_counter() - start) / 5 * 1000
    with capsys.disabled():
        print(f"\nbuild_plan: {elapsed_ms:.1f} ms per call ({len(labelled)} parts)")
    assert elapsed_ms < 1000  # target is < 200 ms; generous margin against a noisy CI machine
