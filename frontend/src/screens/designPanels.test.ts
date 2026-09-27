// @vitest-environment jsdom
// FE-6: the Design workspace's side panels collapse to their header and expand again.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStore } from "../store";
import type { GenerateResponse, TemplateInfo } from "../types";
import { Design } from "./Design";

vi.mock("../three/Scene", () => ({ Scene: () => null })); // no WebGL in jsdom

const read = (path: string) => JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../fixtures", path), "utf8"));
const templates = read("templates.json") as TemplateInfo[];
const ramp = read("specs/ramp_straight.json") as GenerateResponse;

beforeEach(() => {
  useStore.setState(useStore.getInitialState(), true);
  useStore.getState().applyGenerateResult(ramp.spec, ramp.plan, "manual");
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(templates))));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Design side panels", () => {
  it.each([
    ["Parameters", "design-panel-parameters"],
    ["Details & checks", "design-panel-details"],
  ])("%s collapses and expands", async (label, contentId) => {
    render(h(Design));
    const toggle = await screen.findByRole("button", { name: label });
    const content = document.getElementById(contentId)!;
    expect(toggle.getAttribute("aria-controls")).toBe(contentId);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(content.hidden).toBe(false);

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(content.hidden).toBe(true);
    expect(toggle.closest("aside")!.classList.contains("is-collapsed")).toBe(true);

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(content.hidden).toBe(false);
  });

  it("collapsing one panel leaves the other open and the parameters keep their values", async () => {
    render(h(Design));
    await waitFor(() => expect(screen.getByLabelText("Ramp width", { selector: "input[type=text]" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Details & checks" }));
    expect(document.getElementById("design-panel-parameters")!.hidden).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Parameters" }));
    fireEvent.click(screen.getByRole("button", { name: "Parameters" }));
    expect((screen.getByLabelText("Ramp width", { selector: "input[type=text]" }) as HTMLInputElement).value).toBe(String(ramp.spec.params.clear_width_in.value));
  });
});
