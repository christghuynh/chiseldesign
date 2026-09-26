"""CAD export (GEO-17): parts -> CadQuery solids -> STEP / STL bytes.

Pipeline per part (matches tests/test_frame_convention.py's reference `part_to_solid_zup`,
copied here so we don't import from tests):
  polyline(profile) -> close -> extrude(thickness) -> apply the Euler-XYZ rotation and
  translation -> convert the Y-up world frame to the Z-up CAD frame with +90° about X.

The +90° (not -90°) is the correct conversion: -90° turns the model upside down
(foundation.md 'PRD issues' #1, proven by F-7).

Results are cached in a small in-memory LRU keyed by sha256(canonical parts JSON + format),
because the container's code directory is read-only (no on-disk cache). Temp files used for
the CadQuery exporters are written under the system temp dir and removed immediately.
"""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from functools import lru_cache
from pathlib import Path

import cadquery as cq

from app.models import Part, Spec

ORIGIN = (0, 0, 0)
X_AXIS, Y_AXIS, Z_AXIS = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def part_to_solid_zup(part: Part) -> cq.Shape:
    """Build a part as a CadQuery solid in the Z-up CAD frame."""
    solid = cq.Workplane("XY").polyline(part.profile).close().extrude(part.thickness).val()  # +Z extrusion
    rx, ry, rz = part.transform.rot
    # Euler XYZ (three.js) is the matrix Rx*Ry*Rz: Rz first, then Ry, then Rx (fixed axes).
    solid = solid.rotate(ORIGIN, Z_AXIS, math.degrees(rz))
    solid = solid.rotate(ORIGIN, Y_AXIS, math.degrees(ry))
    solid = solid.rotate(ORIGIN, X_AXIS, math.degrees(rx))
    solid = solid.translate(cq.Vector(*part.transform.pos))
    # Y-up world -> Z-up CAD: (x, y, z) -> (x, -z, y), i.e. +90° about X.
    return solid.rotate(ORIGIN, X_AXIS, 90)


def build_assembly(parts: list[Part]) -> cq.Assembly:
    """A named assembly with one solid per part; the assembly name of each is the part id."""
    assembly = cq.Assembly(name="sketchbuild")
    for part in parts:
        assembly.add(part_to_solid_zup(part), name=part.id)
    return assembly


def _canonical_parts_json(parts: list[Part]) -> str:
    """Stable JSON of the parts (sorted keys) so the same geometry hashes the same."""
    return json.dumps([p.model_dump(mode="json") for p in parts], sort_keys=True, separators=(",", ":"))


def _cache_key(parts: list[Part], fmt: str) -> str:
    payload = _canonical_parts_json(parts) + "|" + fmt
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@lru_cache(maxsize=32)
def _cached_export(cache_key: str, canonical_json: str, fmt: str) -> bytes:
    """Export STEP/STL bytes for the given canonical parts JSON. Keyed by cache_key."""
    parts = [Part.model_validate(p) for p in json.loads(canonical_json)]
    assembly = build_assembly(parts)
    suffix = ".step" if fmt == "step" else ".stl"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        if fmt == "step":
            assembly.export(str(tmp_path), exportType="STEP")
            data = tmp_path.read_bytes()
        else:
            # STL has no assembly concept; fuse the solids into one compound and export.
            compound = cq.Compound.makeCompound([part_to_solid_zup(p) for p in parts])
            cq.exporters.export(cq.Workplane("XY").add(compound), str(tmp_path), exportType="STL")
            data = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
    return data


def export_parts(parts: list[Part], fmt: str) -> bytes:
    """Return STEP or STL bytes for the parts, using the in-memory LRU cache."""
    if fmt not in {"step", "stl"}:
        raise ValueError(f"Unknown export format: {fmt!r}")
    key = _cache_key(parts, fmt)
    return _cached_export(key, _canonical_parts_json(parts), fmt)


def export_spec(spec: Spec, fmt: str) -> bytes:
    return export_parts(spec.parts, fmt)
