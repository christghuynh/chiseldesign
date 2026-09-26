import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import type { GenerateResponse, InstructionsResponse } from "../../types";
import { type BuildPosition, keyToAction, navigate, partIdsForStep } from "./navigation";

const fixtures = resolve(import.meta.dirname, "../../../../fixtures");
const { steps } = JSON.parse(
  readFileSync(resolve(fixtures, "instructions/ramp_switchback.json"), "utf8"),
) as InstructionsResponse;
const { spec } = JSON.parse(readFileSync(resolve(fixtures, "specs/ramp_switchback.json"), "utf8")) as GenerateResponse;

const at = (index: number, done = false): BuildPosition => ({ index, done });

describe("navigate: bounds", () => {
  it("moves forward and back one step", () => {
    expect(navigate(at(0), "next", 5)).toEqual(at(1));
    expect(navigate(at(3), "back", 5)).toEqual(at(2));
  });

  it("stays on the first step when going back", () => {
    expect(navigate(at(0), "back", 5)).toEqual(at(0));
  });

  it("goes to Done after the last step, and stays there on next", () => {
    expect(navigate(at(4), "next", 5)).toEqual(at(4, true));
    expect(navigate(at(4, true), "next", 5)).toEqual(at(4, true));
  });

  it("returns from Done to the last step", () => {
    expect(navigate(at(4, true), "back", 5)).toEqual(at(4));
  });

  it("does not move on repeat or stop", () => {
    expect(navigate(at(2), "repeat", 5)).toEqual(at(2));
    expect(navigate(at(2), "stop", 5)).toEqual(at(2));
  });

  it("clamps an out-of-range index and handles no steps", () => {
    expect(navigate(at(9), "back", 5)).toEqual(at(3));
    expect(navigate(at(-2), "next", 5)).toEqual(at(1));
    expect(navigate(at(3), "next", 0)).toEqual(at(0));
  });

  it("walks the whole fixture to Done and back to the start", () => {
    let pos = at(0);
    for (let i = 0; i < steps.length + 3; i++) pos = navigate(pos, "next", steps.length);
    expect(pos).toEqual(at(steps.length - 1, true));
    for (let i = 0; i < steps.length + 3; i++) pos = navigate(pos, "back", steps.length);
    expect(pos).toEqual(at(0));
  });
});

describe("keyToAction: keyboard shortcuts", () => {
  it("maps arrows and R", () => {
    expect(keyToAction({ key: "ArrowRight" })).toBe("next");
    expect(keyToAction({ key: "ArrowLeft" })).toBe("back");
    expect(keyToAction({ key: "r" })).toBe("repeat");
    expect(keyToAction({ key: "R" })).toBe("repeat");
  });

  it("ignores other keys", () => {
    for (const key of ["ArrowUp", "ArrowDown", " ", "Enter", "n", "Escape"]) expect(keyToAction({ key })).toBeNull();
  });

  it("ignores shortcuts with modifiers (browser back, reload)", () => {
    expect(keyToAction({ key: "ArrowLeft", altKey: true })).toBeNull();
    expect(keyToAction({ key: "r", ctrlKey: true })).toBeNull();
    expect(keyToAction({ key: "r", metaKey: true })).toBeNull();
  });

  it("ignores keys typed into a text field", () => {
    const input = { tagName: "INPUT" } as unknown as EventTarget;
    const textarea = { tagName: "textarea" } as unknown as EventTarget;
    const editable = { tagName: "DIV", isContentEditable: true } as unknown as EventTarget;
    expect(keyToAction({ key: "r", target: input })).toBeNull();
    expect(keyToAction({ key: "ArrowRight", target: textarea })).toBeNull();
    expect(keyToAction({ key: "r", target: editable })).toBeNull();
    expect(keyToAction({ key: "r", target: { tagName: "BUTTON" } as unknown as EventTarget })).toBe("repeat");
  });
});

describe("partIdsForStep", () => {
  it("returns every part with one of the step's labels", () => {
    const step = steps.find((s) => s.part_labels.length > 0)!;
    const ids = partIdsForStep(step, spec.parts);
    expect(ids.length).toBeGreaterThan(0);
    const labels = new Set(step.part_labels);
    expect(ids).toEqual(spec.parts.filter((p) => labels.has(p.label)).map((p) => p.id));
  });

  it("returns nothing for a step without parts or no step", () => {
    expect(partIdsForStep(steps[0], spec.parts)).toEqual([]);
    expect(partIdsForStep(undefined, spec.parts)).toEqual([]);
  });

  it("every fixture step label exists in the switchback spec", () => {
    const labels = new Set(spec.parts.map((p) => p.label));
    for (const s of steps) for (const l of s.part_labels) expect(labels).toContain(l);
  });
});
