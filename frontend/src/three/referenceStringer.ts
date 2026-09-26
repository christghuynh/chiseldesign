// The hardcoded stringer for task F-7: the first case in fixtures/frames/reference_parts.json.
// A real 1:12 stringer (level cut at the bottom where it meets grade, plumb cut at the top),
// 1.5" thick, 18" to the left of the ramp centerline. frame.test.ts checks this stays identical
// to the fixture, so edit both together.
import type { Part } from "../types";

export const REFERENCE_STRINGER: Part = {
  id: "REF-1",
  label: "R",
  name: "Stringer",
  material: "2x6_PT",
  profile: [
    [78.27, 0],
    [180, 8.477],
    [180, 13.997],
    [12.042, 0],
  ],
  thickness: 1.5,
  transform: { pos: [0, 0, -18], rot: [0, 0, 0] },
  cut_notes: [],
  group: null,
};
