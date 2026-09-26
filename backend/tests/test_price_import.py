"""NC-4: the price importer validates rows and never half-updates prices.json."""

import csv
import json
from datetime import date

import pytest

from app import data
from app.pricing import importer
from app.pricing.importer import PriceImportError, apply_rows, import_csv, read_rows, write_template

TODAY = date(2026, 9, 26)
HEADER = "key,description,unit,price_cad,source_url,retrieved_at\n"


@pytest.fixture
def prices_file(tmp_path):
    """A copy of the price file with EVERY entry a placeholder, whatever real prices the shipped file has by now."""
    doc = json.loads((data.DATA_DIR / "prices.json").read_text("utf-8"))
    for entry in doc["items"].values():
        entry["placeholder"] = True
        entry["source_url"] = None
        entry["retrieved_at"] = None
        if not entry["description"].endswith(importer.PLACEHOLDER_SUFFIX):
            entry["description"] += importer.PLACEHOLDER_SUFFIX
    copy = tmp_path / "prices.json"
    copy.write_bytes((json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return copy


def write_csv(tmp_path, body, encoding="utf-8"):
    path = tmp_path / "in.csv"
    path.write_text(HEADER + body, encoding=encoding, newline="")
    return path


def load(path):
    return json.loads(path.read_text("utf-8"))


def test_the_template_lists_every_key_with_blank_prices(tmp_path):
    out = tmp_path / "t.csv"
    count = write_template(out)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert count == len(rows) == len(data.prices())
    assert {r["key"] for r in rows} == set(data.prices())
    assert all(r["price_cad"] == "" and "placeholder" not in r["description"] for r in rows)


def test_a_valid_row_makes_that_entry_real(tmp_path, prices_file):
    csv_path = write_csv(tmp_path, "2x6_PT_144,,each,$14.98,https://example.com/2x6x12,2026-09-25\n")
    summary = import_csv(csv_path, prices_file, TODAY)
    entry = load(prices_file)["items"]["2x6_PT_144"]
    assert summary["updated"] == ["2x6_PT_144"]
    assert entry["price_cad"] == 14.98 and entry["placeholder"] is False
    assert entry["source_url"] == "https://example.com/2x6x12" and entry["retrieved_at"] == "2026-09-25"
    assert "placeholder" not in entry["description"] and entry["description"].startswith("2x6 pressure-treated, 12 ft")


def test_untouched_entries_stay_placeholders_and_are_reported(tmp_path, prices_file):
    summary = import_csv(write_csv(tmp_path, "4x4_PT_96,,each,21.5,https://example.com/4x4,\n"), prices_file, TODAY)
    items = load(prices_file)["items"]
    assert items["4x4_PT_96"]["retrieved_at"] == "2026-09-26"  # blank date means today
    assert "4x4_PT_96" not in summary["still_placeholder"] and len(summary["still_placeholder"]) == len(items) - 1
    assert all(v["placeholder"] for k, v in items.items() if k != "4x4_PT_96")


def test_blank_price_rows_are_skipped_not_errors(tmp_path, prices_file):
    summary = import_csv(write_csv(tmp_path, "2x4_PT_96,,each,,,\n,,,,,\n"), prices_file, TODAY)
    assert summary["updated"] == []


def test_thousands_separators_and_a_spreadsheet_byte_order_mark_are_tolerated(tmp_path, prices_file):
    path = write_csv(tmp_path, "3/4_ext_ply_48x96,,sheet,\"$1,062.50\",https://example.com/ply,2026-09-26\n", encoding="utf-8-sig")
    import_csv(path, prices_file, TODAY)
    assert load(prices_file)["items"]["3/4_ext_ply_48x96"]["price_cad"] == 1062.5


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("nope_PT_96,,each,5,https://example.com/x,\n", "unknown key"),
        ("2x4_PT_96,,each,abc,https://example.com/x,\n", "not a number"),
        ("2x4_PT_96,,each,-3,https://example.com/x,\n", "greater than 0"),
        ("2x4_PT_96,,each,0,https://example.com/x,\n", "greater than 0"),
        ("2x4_PT_96,,each,5,,\n", "source_url"),
        ("2x4_PT_96,,each,5,example.com/no-scheme,\n", "source_url"),
        ("2x4_PT_96,,each,5,https://example.com/x,26/09/2026\n", "retrieved_at"),
        ("2x4_PT_96,,each,5,https://example.com/x,\n2x4_PT_96,,each,6,https://example.com/y,\n", "twice"),
    ],
)
def test_a_bad_row_is_rejected_with_its_row_number_and_changes_nothing(tmp_path, prices_file, body, message):
    before = prices_file.read_bytes()
    good = "2x4_PT_120,,each,7.5,https://example.com/ok,2026-09-26\n"  # a valid row before the bad one
    with pytest.raises(PriceImportError, match=message) as info:
        import_csv(write_csv(tmp_path, good + body), prices_file, TODAY)
    assert "row" in str(info.value)
    assert prices_file.read_bytes() == before, "an invalid CSV must not partly update the file"


def test_a_csv_without_the_required_columns_is_rejected(tmp_path, prices_file):
    path = tmp_path / "bad.csv"
    path.write_text("name,cost\nx,1\n", encoding="utf-8")
    with pytest.raises(PriceImportError, match="missing columns"):
        import_csv(path, prices_file, TODAY)


def test_when_every_price_is_real_the_file_says_so(tmp_path, prices_file):
    rows = "".join(f"{k},,{v['unit']},9.99,https://example.com/{i},2026-09-26\n" for i, (k, v) in enumerate(load(prices_file)["items"].items()))
    summary = import_csv(write_csv(tmp_path, rows), prices_file, TODAY)
    doc = load(prices_file)
    assert summary["still_placeholder"] == [] and not any(v["placeholder"] for v in doc["items"].values())
    assert doc["_comment"] == importer.REAL_COMMENT


def test_the_written_file_keeps_lf_endings_and_loads_through_the_real_loader(tmp_path, prices_file, monkeypatch):
    import_csv(write_csv(tmp_path, "2x4_PT_96,,each,4.25,https://example.com/x,2026-09-26\n"), prices_file, TODAY)
    assert b"\r" not in prices_file.read_bytes()
    monkeypatch.setattr(data, "DATA_DIR", prices_file.parent)
    data.prices.cache_clear()
    try:
        assert data.prices()["2x4_PT_96"].placeholder is False and data.prices()["2x4_PT_96"].price_cad == 4.25
    finally:
        data.prices.cache_clear()


def test_real_prices_flow_into_the_plan_and_clear_the_estimate_flag(monkeypatch):
    """When every price a plan uses is real, has_placeholder_prices is false: the Plan screen drops its Estimate label."""
    from app import engine
    from app.models import ParamValue

    real = {k: v.model_copy(update={"placeholder": False, "source_url": "https://example.com", "retrieved_at": "2026-09-26"}) for k, v in data.prices().items()}
    monkeypatch.setattr(data, "prices", lambda: real)
    _, plan = engine.generate("workbench", {})
    assert plan.has_placeholder_prices is False
    _, plan_all = engine.generate("ramp", {"total_rise_in": ParamValue(value=15, source="user")})
    assert plan_all.has_placeholder_prices is False
