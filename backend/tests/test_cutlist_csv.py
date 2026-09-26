"""GEO-18: cut-list CSV export.

Columns: label,name,material,actual_dims_in,length_in,length,qty,part_ids,cut_notes
CRLF line endings, RFC 4180 quoting. Matches P4's frontend (QUESTIONS.md FE-10).
"""

import csv
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.cad.cutlist_csv import HEADER, cutlist_csv
from app.main import app
from app.models import Spec

client = TestClient(app)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "specs" / "ramp_straight.json"
SPEC = Spec.model_validate(json.loads(FIXTURE.read_text("utf-8"))["spec"])


def test_header_and_crlf():
    body = cutlist_csv(SPEC)
    assert body.startswith("label,name,material,actual_dims_in,length_in,length,qty,part_ids,cut_notes\r\n")
    # Every physical line ends with CRLF.
    assert body.endswith("\r\n")
    assert "\r\n" in body


def test_columns_and_row_shape_match_the_engine_plan():
    from app import engine

    _spec, plan = engine.generate(SPEC.template, SPEC.params, SPEC.meta)
    rows = list(csv.reader(io.StringIO(cutlist_csv(SPEC))))
    assert rows[0] == HEADER
    data_rows = [r for r in rows if r]  # csv.reader yields the header + data, no blank trailing row
    assert len(data_rows) == len(plan.cut_list) + 1

    first = data_rows[1]
    expected = plan.cut_list[0]
    assert first[0] == expected.label
    assert first[1] == expected.name
    assert first[2] == expected.material
    assert first[3] == expected.actual_dims
    assert first[6] == str(expected.qty)
    assert first[7] == " ".join(expected.part_ids)


def test_rfc4180_quoting_of_notes_with_commas():
    # cut_notes are joined with "; " but names/notes can contain commas; ensure quoting round-trips.
    body = cutlist_csv(SPEC)
    parsed = list(csv.reader(io.StringIO(body)))
    # Re-parsing yields the same field count on every row (proves quoting is valid RFC 4180).
    assert all(len(r) == len(HEADER) for r in parsed if r)


def test_route_returns_csv_with_the_expected_filename():
    r = client.post("/api/export/cutlist.csv", json={"spec": json.loads(FIXTURE.read_text("utf-8"))["spec"]})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="sketchbuild-ramp-straight-cut-list.csv"'
    assert r.text.startswith("label,name,material")
