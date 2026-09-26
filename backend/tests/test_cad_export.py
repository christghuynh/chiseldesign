"""GEO-17: CAD export (STEP/STL) from the ramp_straight fixture.

Geometry checks after the Y-up -> Z-up conversion (+90° about X):
  * one solid per part;
  * nothing below grade: overall min Z ≈ 0;
  * the walking surface (the deck boards) at the top of the run sits at ≈ total_rise_in.
    We check the deck top, not the overall height, because handrails and their posts
    extend well above the walking surface, so overall height ≠ rise by design.
"""

import json
import time
from pathlib import Path

import cadquery as cq
import pytest
from fastapi.testclient import TestClient

from app.cad.exporter import export_parts, part_to_solid_zup
from app.main import app
from app.models import Spec

client = TestClient(app)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "specs" / "ramp_straight.json"
SPEC = Spec.model_validate(json.loads(FIXTURE.read_text("utf-8"))["spec"])


def test_step_has_one_solid_per_part_and_is_non_empty(tmp_path):
    data = export_parts(SPEC.parts, "step")
    assert len(data) > 0

    # Read the STEP back and count solids across the imported assembly.
    out = tmp_path / "ramp.step"
    out.write_bytes(data)
    imported = cq.importers.importStep(str(out))
    solids = imported.solids().vals()
    assert len(solids) == len(SPEC.parts)


def test_nothing_is_below_grade_and_deck_top_is_the_rise():
    total_rise = SPEC.params["total_rise_in"].value

    min_z = min(part_to_solid_zup(p).BoundingBox().zmin for p in SPEC.parts)
    assert min_z == pytest.approx(0.0, abs=1e-3)

    deck_top = max(
        part_to_solid_zup(p).BoundingBox().zmax for p in SPEC.parts if p.name == "Deck board"
    )
    # Walking surface at the top of the run is the total rise (handrails extend above this).
    assert deck_top == pytest.approx(total_rise, abs=0.5)

    # Sanity: something (the handrails) does extend above the deck.
    overall_top = max(part_to_solid_zup(p).BoundingBox().zmax for p in SPEC.parts)
    assert overall_top > deck_top


def test_step_export_is_under_five_seconds():
    from app.cad import exporter

    exporter._cached_export.cache_clear()  # measure a cold export, not a cache hit
    start = time.perf_counter()
    data = export_parts(SPEC.parts, "step")
    elapsed = time.perf_counter() - start
    assert data and elapsed < 5.0, f"STEP export took {elapsed:.2f}s"


def test_stl_export_is_non_empty():
    data = export_parts(SPEC.parts, "stl")
    assert len(data) > 0


def test_export_route_returns_a_file_with_the_expected_filename():
    r = client.post("/api/export/step", json={"spec": json.loads(FIXTURE.read_text("utf-8"))["spec"]})
    assert r.status_code == 200
    assert r.content
    # layout is "straight" in the fixture, so it appears in the filename.
    assert r.headers["content-disposition"] == 'attachment; filename="sketchbuild-ramp-straight.step"'
