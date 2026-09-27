// @vitest-environment jsdom
// Picking a template must show that template's preset dimensions everywhere: Capture's template
// picker -> Confirm -> Design (param panel), and when switching type on Confirm, including after
// another project was already designed.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStore } from "../store";
import type { GenerateResponse, ParamValue, Spec, TemplateInfo } from "../types";
import { Capture } from "./Capture";
import { Confirm } from "./Confirm";
import { Design } from "./Design";

vi.mock("../three/Scene", () => ({ Scene: () => null })); // no WebGL in jsdom

const read = (path: string) => JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../fixtures", path), "utf8"));
const templates = read("templates.json") as TemplateInfo[];
const rampPlan = read("specs/ramp_straight.json") as GenerateResponse;

let generateBodies: { template: string; params: Record<string, ParamValue> }[] = [];

/** /generate echoes the params it was sent, so what Design shows is exactly what Confirm sent. */
function mockApi() {
  generateBodies = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url === "/api/templates") return new Response(JSON.stringify(templates));
      if (url === "/api/generate") {
        const body = JSON.parse(String(init.body));
        generateBodies.push(body);
        const spec: Spec = { ...rampPlan.spec, template: body.template, params: body.params, parts: [], rule_checks: [], meta: body.meta };
        return new Response(JSON.stringify({ spec, plan: rampPlan.plan }));
      }
      return new Response(JSON.stringify({ error: { code: "NO_ROUTE", message: url } }), { status: 599 });
    }),
  );
}

const numericDefaults = (t: TemplateInfo) =>
  Object.entries(t.defaults).filter((entry): entry is [string, number] => typeof entry[1] === "number");

async function pickInCapture(name: string) {
  render(h(Capture));
  const browse = await screen.findByRole("button", { name: "Browse templates" });
  await waitFor(() => expect((browse as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(browse);
  const dialog = screen.getByRole("dialog");
  fireEvent.click(within(dialog).getByRole("button", { name: new RegExp(name) }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Start with this template" }));
}

/** Every number input on screen, by its value: preset numbers must appear as field values. */
const shownNumbers = () =>
  [...document.querySelectorAll("input")]
    .filter((input) => input.type !== "checkbox" && input.value !== "")
    .map((input) => Number(input.value.replace(/[^\d.-]/g, "")));

/** Every <label for> must point at an element that exists, and ids must be unique on the page. */
function expectValidLabels() {
  const ids = [...document.querySelectorAll("[id]")].map((el) => el.id);
  expect(ids.filter((id, i) => ids.indexOf(id) !== i), "duplicate ids").toEqual([]);
  const broken = [...document.querySelectorAll("label[for]")]
    .map((label) => label.getAttribute("for")!)
    .filter((id) => !document.getElementById(id));
  expect(broken, "labels whose for= matches no element").toEqual([]);
}

beforeEach(() => {
  useStore.setState(useStore.getInitialState(), true);
  mockApi();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("choosing a template fills in its preset dimensions", () => {
  for (const template of templates.filter((t) => !(t.params_schema.required as string[] | undefined)?.length)) {
    it(`${template.name}: Capture picker -> Confirm -> Design`, async () => {
      await pickInCapture(template.name);
      await waitFor(() => expect(useStore.getState().screen).toBe("confirm"));
      cleanup();

      render(h(Confirm));
      await screen.findByRole("button", { name: /Looks right/ });
      await waitFor(() => {
        for (const [, value] of numericDefaults(template)) expect(shownNumbers()).toContain(value);
      });
      expectValidLabels();
      fireEvent.click(screen.getByRole("button", { name: /Looks right/ }));
      await waitFor(() => expect(useStore.getState().screen).toBe("design"));

      const sent = generateBodies.at(-1)!;
      expect(sent.template).toBe(template.key);
      for (const [name, value] of Object.entries(template.defaults)) {
        if (value !== null) expect(sent.params[name]?.value, name).toEqual(value);
      }
      expect(Object.keys(sent.params).every((name) => name in template.defaults), "no params from another template").toBe(true);
      cleanup();

      render(h(Design));
      await waitFor(() => {
        for (const [, value] of numericDefaults(template)) expect(shownNumbers()).toContain(value);
      });
      expectValidLabels();
    });
  }

  it("a width typed on Capture lands in the garden bed's own width, the other presets stay", async () => {
    render(h(Capture));
    fireEvent.change(await screen.findByLabelText("Desired width (inches)"), { target: { value: "30" } });
    const browse = await screen.findByRole("button", { name: "Browse templates" });
    await waitFor(() => expect((browse as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(browse);
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Raised garden bed/ }));
    expect(within(dialog).getByText("Length: 72 in")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Start with this template" }));
    await waitFor(() => expect(useStore.getState().screen).toBe("confirm"));
    const { getCaptureSession } = await import("./flowState");
    const params = getCaptureSession()!.parse.spec!.params;
    expect(params.width_in).toEqual({ value: 30, source: "user", confidence: null });
    expect(params.length_in.value).toBe(72);
    expect(params.height_in.value).toBe(29.25); // the full-board default
    expect(params.clear_width_in).toBeUndefined();
  });

  it("a new template replaces a design that was already generated", async () => {
    useStore.getState().applyGenerateResult(rampPlan.spec, rampPlan.plan, "manual");
    const bed = templates.find((t) => t.key === "garden_bed")!;
    await pickInCapture(bed.name);
    await waitFor(() => expect(useStore.getState().screen).toBe("confirm"));
    cleanup();
    render(h(Confirm));
    const select = (await screen.findByLabelText(/Wrong type/)) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe("garden_bed"));
  });

  it("switching type on Confirm swaps in the new template's presets", async () => {
    const ramp = templates.find((t) => t.key === "ramp")!;
    const bed = templates.find((t) => t.key === "garden_bed")!;
    useStore.setState({ screen: "capture" });
    await pickInCapture(ramp.name);
    // Ramp needs a rise, so Capture asks for it instead of continuing.
    expect(await screen.findByText(/Enter total rise/)).toBeTruthy();
    cleanup();

    const { setCaptureSession } = await import("./flowState");
    const { specFromDefaults } = await import("./flowState");
    setCaptureSession({ parse: { spec: specFromDefaults(ramp, { total_rise_in: 14 }), template_confidence: null, questions: [], raw_notes: "" }, imageUrl: null });
    render(h(Confirm));
    const select = (await screen.findByLabelText(/Wrong type/)) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBeGreaterThan(1));
    fireEvent.change(select, { target: { value: "garden_bed" } });
    await waitFor(() => {
      for (const [, value] of numericDefaults(bed)) expect(shownNumbers()).toContain(value);
    });
    expectValidLabels();
    fireEvent.click(screen.getByRole("button", { name: /Looks right/ }));
    await waitFor(() => expect(generateBodies).toHaveLength(1));
    expect(generateBodies[0].template).toBe("garden_bed");
    expect(generateBodies[0].params.total_rise_in).toBeUndefined();
    expect(generateBodies[0].params.length_in.value).toBe(72);
  });
});
