// @vitest-environment jsdom
// FE-6: the parameter panel keeps a draft while you type or drag and sends one finished, in-range value;
// the ramp's key dimensions come first and the rest fold under "Advanced settings".
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { GenerateResponse, ParamValue, TemplateInfo } from "../types";
import { keyFacts, KeyFacts } from "./KeyFacts";
import { ParamPanel } from "./ParamPanel";

const read = (path: string) => JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../fixtures", path), "utf8"));
const ramp = (read("templates.json") as TemplateInfo[]).find((t) => t.key === "ramp")!;
const { spec } = read("specs/ramp_switchback.json") as GenerateResponse;

afterEach(cleanup);

function setup(params: Record<string, ParamValue> = spec.params, busy = false) {
  const onChange = vi.fn();
  const view = render(h(ParamPanel, { template: ramp, params, onChange, busy }));
  const rerender = (next: Record<string, ParamValue>, nextBusy = busy) => view.rerender(h(ParamPanel, { template: ramp, params: next, onChange, busy: nextBusy }));
  return { onChange, rerender };
}

const box = (label: string) => screen.getByLabelText(label, { selector: "input[type=text]" }) as HTMLInputElement;
const slider = (label: string) => screen.getByLabelText(`${label} slider`) as HTMLInputElement;
const type = (input: HTMLInputElement, text: string) => {
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: text } });
};

describe("typing", () => {
  it("keeps what you type and sends nothing until you finish", () => {
    const { onChange } = setup();
    const landing = box("Landing length");
    type(landing, "6"); // deleting the 0 from 60
    expect(landing.value).toBe("6");
    type(landing, ""); // deleting the 6
    expect(landing.value).toBe("");
    type(landing, "72");
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.keyDown(landing, { key: "Enter" });
    expect(onChange).toHaveBeenCalledExactlyOnceWith("landing_length_in", 72);
  });

  it("explains an out-of-range value instead of snapping, and sends nothing", () => {
    const { onChange } = setup();
    const landing = box("Landing length");
    type(landing, "6");
    fireEvent.blur(landing);
    expect(screen.getByRole("alert").textContent).toBe("Must be between 12 and 240 in.");
    expect(landing.value).toBe("6");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("asks for a value when a required field is left empty", () => {
    const { onChange } = setup();
    const width = box("Ramp width");
    type(width, "");
    fireEvent.blur(width);
    expect(screen.getByRole("alert").textContent).toBe("Enter a value.");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("reads feet and inches", () => {
    const { onChange } = setup();
    const space = box("Space in front (optional)");
    type(space, "16'");
    fireEvent.blur(space);
    expect(onChange).toHaveBeenCalledExactlyOnceWith("available_length_in", 192);
  });

  it("clears an optional value, and shows it even when it isn't set", () => {
    const { onChange, rerender } = setup();
    const space = box("Space in front (optional)");
    type(space, "");
    fireEvent.blur(space);
    expect(onChange).toHaveBeenCalledExactlyOnceWith("available_length_in", null);
    const { available_length_in: _, ...unset } = spec.params;
    rerender(unset);
    expect(box("Space in front (optional)").placeholder).toBe("No limit");
  });

  it("Escape puts the current value back", () => {
    setup();
    const width = box("Ramp width");
    type(width, "4");
    fireEvent.keyDown(width, { key: "Escape" });
    expect(width.value).toBe(String(spec.params.clear_width_in.value));
  });

  it("takes a new value from the model unless you're typing in the field", () => {
    const { rerender } = setup();
    const width = box("Ramp width");
    rerender({ ...spec.params, clear_width_in: { value: 42, source: "user", confidence: null } });
    expect(width.value).toBe("42");
    type(width, "4");
    rerender({ ...spec.params, clear_width_in: { value: 48, source: "user", confidence: null } });
    expect(width.value).toBe("4");
  });
});

describe("slider", () => {
  it("follows the drag and sends one value when released", () => {
    const { onChange } = setup();
    const width = slider("Ramp width");
    for (const v of ["40", "44", "48"]) fireEvent.change(width, { target: { value: v } });
    expect(onChange).not.toHaveBeenCalled();
    expect(box("Ramp width").value).toBe("48");
    fireEvent.pointerUp(width);
    expect(onChange).toHaveBeenCalledExactlyOnceWith("clear_width_in", 48);
  });

  it("stays where you let go while the model updates, instead of jumping back", () => {
    const { rerender } = setup();
    const width = slider("Ramp width");
    fireEvent.change(width, { target: { value: "48" } });
    fireEvent.pointerUp(width);
    rerender(spec.params, true); // request in flight, old value still in the spec
    expect(width.value).toBe("48");
    expect(width.disabled).toBe(false);
    rerender({ ...spec.params, clear_width_in: { value: 48, source: "user", confidence: null } }, false);
    expect(width.value).toBe("48");
  });
});

describe("layout", () => {
  it("shows the key dimensions first and folds the rest under Advanced settings", () => {
    setup();
    const advanced = screen.getByText(/Advanced settings \(9\)/).closest("details")!;
    expect(within(advanced).getByText("1 changed")).toBeTruthy(); // the switchback layout came from a fix
    expect(advanced.open).toBe(false);
    expect(within(advanced).queryByLabelText("Ramp width", { selector: "input[type=text]" })).toBeNull();
    expect(within(advanced).getByLabelText("Landing length", { selector: "input[type=text]" })).toBeTruthy();
    expect(screen.getByText("Key dimensions")).toBeTruthy();
    expect(within(advanced).getAllByRole("button", { name: "Automatic" })).toHaveLength(2); // layout and handrails
    expect(within(advanced).getByRole("button", { name: "2x6 pressure-treated" })).toBeTruthy();
  });

  it("shows lengths in feet and inches too", () => {
    setup();
    expect(screen.getByText(`= 5' 0"`)).toBeTruthy(); // the 60 in landing
  });
});

describe("KeyFacts", () => {
  it("shows the engine's summary", () => {
    render(h(KeyFacts, { spec }));
    expect(screen.getByText("At a glance")).toBeTruthy();
    expect(screen.getByText("Switchback, 2 runs")).toBeTruthy();
    expect(screen.getByText("Landings")).toBeTruthy();
  });

  it("ignores a missing or malformed summary", () => {
    expect(keyFacts({ ...spec, meta: {} })).toEqual([]);
    expect(keyFacts({ ...spec, meta: { summary: [{ label: 1 }, { label: "Slope", value: "1:12" }] } })).toEqual([{ label: "Slope", value: "1:12" }]);
  });
});
