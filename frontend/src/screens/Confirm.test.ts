// @vitest-environment jsdom
// FE-4: Confirm lists every template, shows required values the parse couldn't read as fields, lets the
// parse's questions be answered, and only generates when nothing required is missing.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStore } from "../store";
import type { GenerateResponse, Spec, TemplateInfo } from "../types";
import { Confirm } from "./Confirm";
import { setCaptureSession, ungeneratedSpec } from "./flowState";

const read = (path: string) => JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../fixtures", path), "utf8"));
const templates = read("templates.json") as TemplateInfo[];
const generated = read("specs/ramp_switchback.json") as GenerateResponse;
const QUESTION = "How tall is the porch?";

// The parse couldn't read the rise: it is left out, and a question asks for it.
const { total_rise_in: _rise, ...withoutRise } = generated.spec.params;
const parsed: Spec = { ...ungeneratedSpec(generated.spec), params: withoutRise };

let calls: { url: string; body: any }[] = [];
function mockApi(routes: Record<string, (body: any) => [number, unknown]>) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const body = typeof init.body === "string" ? JSON.parse(init.body) : null;
      calls.push({ url, body });
      const route = routes[`${init.method ?? "GET"} ${url}`];
      const [status, payload] = route ? route(body) : [599, { error: { code: "NO_ROUTE", message: url } }];
      return new Response(JSON.stringify(payload), { status });
    }),
  );
}

const templatesRoute = { "GET /api/templates": () => [200, templates] as [number, unknown] };
const generateButton = () => screen.getByRole("button", { name: /Looks right/ }) as HTMLButtonElement;
const riseBox = () => screen.getByLabelText("Rise (height to climb)", { selector: "input[type=text]" }) as HTMLInputElement;

beforeEach(() => {
  useStore.setState(useStore.getInitialState(), true);
  setCaptureSession({ parse: { spec: parsed, template_confidence: 0.8, questions: [QUESTION], raw_notes: "" }, imageUrl: null });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Confirm", () => {
  it("offers every template in the type dropdown", async () => {
    mockApi(templatesRoute);
    render(h(Confirm));
    const select = (await screen.findByLabelText(/Wrong type/)) as HTMLSelectElement;
    await waitFor(() => expect(select.options).toHaveLength(templates.length));
    expect([...select.options].map((o) => o.textContent)).toEqual(templates.map((t) => t.name));
  });

  it("switching type starts from that template's defaults and drops the old questions", async () => {
    mockApi(templatesRoute);
    render(h(Confirm));
    const select = (await screen.findByLabelText(/Wrong type/)) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBeGreaterThan(1));
    fireEvent.change(select, { target: { value: "workbench" } });
    expect(await screen.findByLabelText(/Width/, { selector: "input[type=text]" })).toBeTruthy();
    expect(screen.queryByText(QUESTION)).toBeNull();
    expect(generateButton().disabled).toBe(false);
  });

  it("shows a missing required value as a field and won't generate until it's filled", async () => {
    mockApi({ ...templatesRoute, "POST /api/generate": () => [200, generated] });
    render(h(Confirm));
    expect((await screen.findByLabelText("Rise (height to climb)", { selector: "input[type=text]" })) as HTMLInputElement).toBeTruthy();
    expect(riseBox().placeholder).toBe("Required");
    expect(generateButton().disabled).toBe(true);
    expect(screen.getByText("Fill in Rise (height to climb) to generate the design.")).toBeTruthy();

    fireEvent.focus(riseBox());
    fireEvent.change(riseBox(), { target: { value: "21" } });
    fireEvent.keyDown(riseBox(), { key: "Enter" });
    expect(generateButton().disabled).toBe(false);
    fireEvent.click(generateButton());
    await waitFor(() => expect(useStore.getState().screen).toBe("design"));
    expect(calls.find((c) => c.url === "/api/generate")!.body.params.total_rise_in).toEqual({ value: 21, source: "user", confidence: null });
  });

  it("answers a question in words through /edit and fills in the value", async () => {
    mockApi({
      ...templatesRoute,
      "POST /api/edit": () => [
        200,
        { spec: { ...generated.spec, params: { ...generated.spec.params, total_rise_in: { value: 21, source: "user", confidence: null } } }, plan: generated.plan, patch: { total_rise_in: 21 }, message: "Set the rise to twenty-one inches.", needs_clarification: false },
      ],
    });
    render(h(Confirm));
    const answer = await screen.findByLabelText(QUESTION);
    fireEvent.change(answer, { target: { value: "three steps, about 21 inches" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply answers" }));
    expect(await screen.findByText(/Set the rise to twenty-one inches/)).toBeTruthy();
    expect(calls.find((c) => c.url === "/api/edit")!.body.utterance).toBe(`${QUESTION} three steps, about 21 inches`);
    await waitFor(() => expect(riseBox().value).toBe("21")); // the field picks up the new value in an effect
    expect(screen.queryByLabelText(QUESTION)).toBeNull();
    expect(generateButton().disabled).toBe(false);
  });

  it("points at the field when an answer doesn't supply a required value", async () => {
    mockApi({ ...templatesRoute, "POST /api/edit": () => [422, { error: { code: "INVALID_PARAMS", message: "total_rise_in is required" } }] });
    render(h(Confirm));
    fireEvent.change(await screen.findByLabelText(QUESTION), { target: { value: "not sure" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply answers" }));
    expect(await screen.findByText("Chisel still needs Rise (height to climb). Type it into the field above.")).toBeTruthy();
  });
});
