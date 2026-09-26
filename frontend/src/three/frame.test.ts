// F-7 (three.js side): each reference part must land exactly on the hand-derived world vertices.
// The CadQuery side is backend/tests/test_frame_convention.py; both read the same fixture, so if the
// two renderers ever disagree about where a part sits, one of the two tests fails.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import type { GenerateResponse, Part } from "../types";
import { partGeometry, partWorldVertices } from "./geometry";
import { REFERENCE_STRINGER } from "./referenceStringer";

interface FrameCase {
  name: string;
  description: string;
  part: Part;
  expected_vertices: [number, number, number][];
}

const fixtures = resolve(import.meta.dirname, "../../../fixtures");
const cases: FrameCase[] = JSON.parse(readFileSync(resolve(fixtures, "frames/reference_parts.json"), "utf8")).cases;

const byXyz = (a: number[], b: number[]) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2];

describe("part transform convention (Y-up, extrude +Z, Euler XYZ)", () => {
  it.each(cases.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const actual = partWorldVertices(c.part);
    const expected = [...c.expected_vertices].sort(byXyz);
    expect(actual).toHaveLength(expected.length);
    actual.forEach((point, i) => {
      point.forEach((value, axis) => expect(value).toBeCloseTo(expected[i][axis], 3));
    });
  });

  it("the hardcoded reference stringer is identical to the fixture's first case", () => {
    expect(REFERENCE_STRINGER).toEqual(cases[0].part);
  });
});

describe("every fixture part builds valid geometry", () => {
  it.each(["ramp_straight.json", "ramp_switchback.json"])("%s", (file) => {
    const { spec } = JSON.parse(readFileSync(resolve(fixtures, "specs", file), "utf8")) as GenerateResponse;
    expect(spec.parts.length).toBeGreaterThan(0);
    for (const part of spec.parts) {
      const geometry = partGeometry(part);
      expect(geometry.getAttribute("position").count, part.id).toBeGreaterThan(0);
      // Nothing may sit below the ground plane (Y-up, origin on the ground).
      const low = Math.min(...partWorldVertices(part).map((v) => v[1]));
      expect(low, `${part.id} goes below grade`).toBeGreaterThanOrEqual(-1e-3);
      geometry.dispose();
    }
  });
});
