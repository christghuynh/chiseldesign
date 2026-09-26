"""F-7: prove the world-frame / part-transform convention on the CadQuery side.

The three.js side is frontend/src/three/frame.test.ts. Both read the same hand-derived
vertices from fixtures/frames/reference_parts.json, so if the two renderers ever disagree
about where a part sits, one of the two tests fails.

`part_to_solid_zup` is the reference implementation of the CAD export pipeline (profile ->
extrude -> transform -> Y-up to Z-up). GEO-17 (the real STEP/STL exporter) should start from it.

It is easy to write the Y-up -> Z-up conversion as "rotate -90 degrees about X". As an active rotation
of the geometry that turns the ramp upside down; the correct rotation is +90 degrees about X.
See foundation.md.
"""

import json
import math
from pathlib import Path

import cadquery as cq
import pytest

from app.models import Part

REFERENCE = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "frames" / "reference_parts.json").read_text("utf-8")
)
CASES = REFERENCE["cases"]
ORIGIN = (0, 0, 0)
X_AXIS, Y_AXIS, Z_AXIS = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def part_to_solid_zup(part: Part) -> cq.Shape:
    """Build a part as a CadQuery solid in the Z-up CAD frame."""
    solid = cq.Workplane("XY").polyline(part.profile).close().extrude(part.thickness).val()  # +Z extrusion
    rx, ry, rz = part.transform.rot
    # Euler XYZ (three.js) is the matrix Rx*Ry*Rz: Rz is applied first, then Ry, then Rx.
    solid = solid.rotate(ORIGIN, Z_AXIS, math.degrees(rz))
    solid = solid.rotate(ORIGIN, Y_AXIS, math.degrees(ry))
    solid = solid.rotate(ORIGIN, X_AXIS, math.degrees(rx))
    solid = solid.translate(cq.Vector(*part.transform.pos))
    # Y-up world -> Z-up CAD: (x, y, z) -> (x, -z, y), which is +90 degrees about X.
    return solid.rotate(ORIGIN, X_AXIS, 90)


def zup_to_yup(x: float, y: float, z: float) -> tuple[float, float, float]:
    return (x, z, -y)


def solid_vertices_yup(solid: cq.Shape) -> list[list[float]]:
    unique = {(round(v.X, 6), round(v.Y, 6), round(v.Z, 6)) for v in solid.Vertices()}
    return sorted([round(c, 6) + 0.0 for c in zup_to_yup(*v)] for v in unique)


def shoelace_area(profile: list[tuple[float, float]]) -> float:
    n = len(profile)
    return abs(sum(profile[i][0] * profile[(i + 1) % n][1] - profile[(i + 1) % n][0] * profile[i][1] for i in range(n))) / 2


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_cadquery_matches_hand_derived_vertices(case):
    part = Part.model_validate(case["part"])  # also checks the fixture obeys the contract
    actual = solid_vertices_yup(part_to_solid_zup(part))
    expected = sorted([round(c, 6) + 0.0 for c in v] for v in case["expected_vertices"])
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected, strict=True):
        assert got == pytest.approx(want, abs=1e-5), f"{case['name']}: {got} != {want}"


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_solid_is_valid_and_not_mirrored(case):
    part = Part.model_validate(case["part"])
    solid = part_to_solid_zup(part)
    assert solid.isValid()
    # Proper rotations keep the volume positive and equal to area x thickness; a mirror would not.
    assert solid.Volume() == pytest.approx(shoelace_area(part.profile) * part.thickness, rel=1e-6)


def _rotated_about_x(direction: tuple[float, float, float], degrees: float) -> tuple[float, float, float]:
    v = cq.Vertex.makeVertex(*direction).rotate(ORIGIN, X_AXIS, degrees)
    return (round(v.X, 9) + 0.0, round(v.Y, 9) + 0.0, round(v.Z, 9) + 0.0)


def test_y_up_axes_map_to_cad_axes():
    """Ramp travel (+X) stays +X, up (+Y) becomes CAD +Z, the walker's right (+Z) becomes CAD -Y."""
    assert _rotated_about_x((1, 0, 0), 90) == (1, 0, 0)
    assert _rotated_about_x((0, 1, 0), 90) == (0, 0, 1)
    assert _rotated_about_x((0, 0, 1), 90) == (0, -1, 0)


def test_prd_literal_minus_90_would_flip_the_model_upside_down():
    """Documents why the conversion is +90, not -90: -90 degrees about X sends Y-up to CAD -Z."""
    assert _rotated_about_x((0, 1, 0), -90) == (0, 0, -1)


def test_step_export_works(tmp_path):
    part = Part.model_validate(CASES[0]["part"])
    out = tmp_path / "stringer.step"
    cq.exporters.export(cq.Workplane("XY").add(part_to_solid_zup(part)), str(out))
    assert out.stat().st_size > 0
    assert out.read_text("utf-8", errors="ignore").startswith("ISO-10303-21")
