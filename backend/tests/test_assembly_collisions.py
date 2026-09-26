"""No two parts of a design may occupy the same space.

Parts are extruded polygons (profile in local XY, extruded along local +Z, mirrored about Y when rot is (0, pi, 0)),
so the overlap volume of two parts is the area of their profile intersection (in world XY) times the overlap of
their Z ranges. Touching faces have zero overlap; the tolerance below absorbs 3-decimal rounding.
"""

import math
import random

import pytest

from app import engine
from app.models import ParamValue, Part
from app.engine_errors import ParamValidationError

Point = tuple[float, float]
# Slop for rounding and one known, harmless wedge: a sloped plywood panel's square-cut end pokes about 0.06 in past the
# vertical edge of the landing it meets (0.7 in^3 over a 36 in width), which a builder simply trims. A real collision
# (two boards sharing space) is hundreds of times larger.
TOLERANCE_IN3 = 1.0


def user(value):
    return ParamValue(value=value, source="user")


def world_polygon(part: Part) -> tuple[list[Point], float, float]:
    """(polygon in world XY, z_min, z_max). Only rotations of 0 or pi about Y are used by the templates."""
    px, py, pz = part.transform.pos
    flipped = part.transform.rot[1] != 0
    if flipped:
        poly = [(px - x, py + y) for x, y in part.profile]
        z0, z1 = pz - part.thickness, pz
    else:
        poly = [(px + x, py + y) for x, y in part.profile]
        z0, z1 = pz, pz + part.thickness
    if flipped:
        poly.reverse()  # the mirror flips winding; keep it counter-clockwise for the clipper
    return poly, z0, z1


def area(poly: list[Point]) -> float:
    n = len(poly)
    return abs(sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))) / 2


def clip_convex(subject: list[Point], clip: list[Point]) -> list[Point]:
    """Sutherland-Hodgman: subject clipped by a convex counter-clockwise polygon."""
    out = subject
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        inside = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9
        cur, out = out, []
        for j in range(len(cur)):
            p, q = cur[j], cur[(j + 1) % len(cur)]
            if inside(p):
                out.append(p)
            if inside(p) != inside(q):
                dx, dy = q[0] - p[0], q[1] - p[1]
                denom = (b[0] - a[0]) * dy - (b[1] - a[1]) * dx
                t = ((b[0] - a[0]) * (a[1] - p[1]) - (b[1] - a[1]) * (a[0] - p[0])) / denom if denom else 0
                out.append((p[0] + t * dx, p[1] + t * dy))
        if not out:
            return []
    return out


def is_convex(poly: list[Point]) -> bool:
    n = len(poly)
    signs = {math.copysign(1, (poly[(i + 1) % n][0] - poly[i][0]) * (poly[(i + 2) % n][1] - poly[(i + 1) % n][1]) - (poly[(i + 1) % n][1] - poly[i][1]) * (poly[(i + 2) % n][0] - poly[(i + 1) % n][0])) for i in range(n)}
    return len(signs) == 1


def overlaps(parts: list[Part]) -> list[tuple[float, str, str]]:
    shapes = [(p, *world_polygon(p)) for p in parts]
    boxes = [(min(x for x, _ in poly), max(x for x, _ in poly), min(y for _, y in poly), max(y for _, y in poly), z0, z1) for _, poly, z0, z1 in shapes]
    found = []
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            a, b = boxes[i], boxes[j]
            if a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2] or a[5] <= b[4] or b[5] <= a[4]:
                continue  # bounding boxes do not overlap
            z = min(a[5], b[5]) - max(a[4], b[4])
            pa, pb = shapes[i][1], shapes[j][1]
            assert is_convex(pb), f"{shapes[j][0].name} is not convex; extend the test"
            inter = clip_convex(pa, pb)
            if len(inter) >= 3 and area(inter) * z > TOLERANCE_IN3:
                found.append((round(area(inter) * z, 2), f"{shapes[i][0].id} {shapes[i][0].name}", f"{shapes[j][0].id} {shapes[j][0].name}"))
    return sorted(found, reverse=True)


RAMP_CASES = [
    {"total_rise_in": 15, "layout": "straight"},
    {"total_rise_in": 15, "layout": "switchback"},
    {"total_rise_in": 21},
    {"total_rise_in": 12},
    {"total_rise_in": 31, "layout": "straight"},
    {"total_rise_in": 45, "layout": "switchback", "clear_width_in": 48},
    {"total_rise_in": 21, "layout": "switchback", "decking": "3/4_ext_ply", "framing": "2x8_PT"},
    {"total_rise_in": 21, "layout": "switchback", "handrails": "no", "edge_curb": False, "stringer_spacing_in": 24},
    {"total_rise_in": 9, "layout": "straight", "slope_ratio": 14},
    {"total_rise_in": 30, "layout": "switchback", "clear_width_in": 60},
]


@pytest.mark.parametrize("values", RAMP_CASES, ids=lambda v: "-".join(f"{k}={v[k]}" for k in v))
def test_no_two_parts_of_a_ramp_occupy_the_same_space(values):
    spec, _ = engine.generate("ramp", {k: user(v) for k, v in values.items()})
    found = overlaps(spec.parts)
    assert not found, f"{len(found)} overlapping pairs, worst: {found[:5]}"


def test_no_overlaps_across_a_seeded_sweep_of_ramps():
    rng = random.Random(7)
    checked = 0
    while checked < 25:
        values = {
            "total_rise_in": round(rng.uniform(4, 60), 1),
            "clear_width_in": rng.choice([30, 36, 48, 60]),
            "layout": rng.choice(["auto", "straight", "switchback"]),
            "decking": rng.choice(["5/4x6_PT_deck", "3/4_ext_ply"]),
            "stringer_spacing_in": rng.choice([12, 16, 24]),
        }
        try:
            spec, _ = engine.generate("ramp", {k: user(v) for k, v in values.items()})
        except ParamValidationError:
            continue
        found = overlaps(spec.parts)
        assert not found, (values, found[:5])
        checked += 1


@pytest.mark.parametrize(("template", "values"), [("garden_bed", {}), ("workbench", {}), ("workbench", {"lower_shelf": False}), ("garden_bed", {"cap_rail": False, "height_in": 40})])
def test_no_two_parts_of_the_other_templates_occupy_the_same_space(template, values):
    spec, _ = engine.generate(template, {k: user(v) for k, v in values.items()})
    found = overlaps(spec.parts)
    assert not found, f"{len(found)} overlapping pairs, worst: {found[:5]}"


def test_the_collision_checker_itself_detects_an_overlap():
    """Guard against a checker that can never fail: two identical stringers at the same place must collide."""
    spec, _ = engine.generate("ramp", {"total_rise_in": user(12)})
    stringer = next(p for p in spec.parts if p.name == "Stringer")
    twin = stringer.model_copy(update={"id": "X-1"})
    assert overlaps([stringer, twin]) and overlaps([stringer, twin])[0][0] > 10
    shifted = stringer.model_copy(update={"id": "X-2", "transform": stringer.transform.model_copy(update={"pos": (0.0, 0.0, stringer.transform.pos[2] + 10.0)})})
    assert not overlaps([stringer, shifted])


def _boxes(parts: list[Part]) -> list[tuple[float, float, float, float, float, float]]:
    boxes = []
    for part in parts:
        poly, z0, z1 = world_polygon(part)
        boxes.append((min(x for x, _ in poly), max(x for x, _ in poly), min(y for _, y in poly), max(y for _, y in poly), z0, z1))
    return boxes


def disconnected_groups(parts: list[Part], gap: float = 0.1) -> list[list[str]]:
    """Parts grouped into touching clusters (bounding boxes within `gap` of each other). One cluster = one assembly."""
    boxes = _boxes(parts)
    parent = list(range(len(parts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            a, b = boxes[i], boxes[j]
            if a[0] - gap <= b[1] and b[0] - gap <= a[1] and a[2] - gap <= b[3] and b[2] - gap <= a[3] and a[4] - gap <= b[5] and b[4] - gap <= a[5]:
                parent[find(i)] = find(j)
    groups: dict[int, list[str]] = {}
    for i, part in enumerate(parts):
        groups.setdefault(find(i), []).append(f"{part.id} {part.name}")
    return sorted(groups.values(), key=len, reverse=True)


ASSEMBLIES = [("ramp", v) for v in RAMP_CASES] + [("garden_bed", {}), ("garden_bed", {"cap_rail": False}), ("workbench", {}), ("workbench", {"lower_shelf": False}), ("step_platform", {"total_rise_in": 14}), ("step_platform", {"total_rise_in": 30})]


@pytest.mark.parametrize(("template", "values"), ASSEMBLIES, ids=lambda x: str(x)[:60])
def test_every_design_is_one_connected_assembly_with_no_floating_parts(template, values):
    params = {**({"total_rise_in": 14} if template == "step_platform" else {}), **values}
    spec, _ = engine.generate(template, {k: user(v) for k, v in params.items()})
    groups = disconnected_groups(spec.parts)
    assert len(groups) == 1, f"{len(groups)} separate clusters; smaller ones: {groups[1:4]}"


def test_the_connectivity_checker_itself_detects_a_floating_part():
    spec, _ = engine.generate("workbench", {})
    far = spec.parts[0].model_copy(update={"id": "X-9", "transform": spec.parts[0].transform.model_copy(update={"pos": (500.0, 0.0, 0.0)})})
    assert len(disconnected_groups([*spec.parts, far])) == 2
