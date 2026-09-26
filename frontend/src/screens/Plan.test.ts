// @vitest-environment jsdom
// FE-7b: the Plan screen reads spec/plan from the store, highlights a row's parts, and navigates.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStore } from "../store";
import type { SceneProps } from "../three/Scene";
import type { GenerateResponse } from "../types";
import { Plan } from "./Plan";

// WebGL is not available in jsdom: stand in for the Scene and expose its props.
vi.mock("../three/Scene", () => ({
  Scene: ({ parts, highlightedIds = [], onSelect }: SceneProps) =>
    h("div", { "data-testid": "scene", "data-parts": parts.length, "data-highlighted": highlightedIds.join(",") }, [
      h("button", { key: "p", type: "button", onClick: () => onSelect?.(parts[0].id) }, "scene: click first part"),
      h("button", { key: "bg", type: "button", onClick: () => onSelect?.(null) }, "scene: click background"),
    ]),
}));

const { spec, plan } = JSON.parse(
  readFileSync(resolve(import.meta.dirname, "../../../fixtures/specs/ramp_switchback.json"), "utf8"),
) as GenerateResponse;

beforeEach(() => {
  useStore.setState(useStore.getInitialState(), true);
});
afterEach(cleanup);

const loaded = () => {
  useStore.getState().applyGenerateResult(spec, plan, "manual");
  useStore.getState().setScreen("plan");
  return render(h(Plan));
};

describe("Plan screen", () => {
  it("shows an empty state and a way back when there is no plan", () => {
    render(h(Plan));
    expect(screen.getByText(/no plan yet/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back to design" }));
    expect(useStore.getState().screen).toBe("design");
  });

  it("renders every section from the store's plan", () => {
    loaded();
    expect(screen.getByRole("heading", { name: "Cut list" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Cutting layouts" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Shopping list" })).toBeTruthy();
    expect(screen.getByText(/Guidelines, not code compliance/)).toBeTruthy();
    expect(screen.getByTestId("scene").dataset.parts).toBe(String(spec.parts.length));
    expect(screen.getAllByRole("img")).toHaveLength(plan.layouts.length);
  });

  it("says the total is an estimate when prices are placeholders", () => {
    expect(plan.has_placeholder_prices).toBe(true);
    loaded();
    expect(screen.getAllByText("Estimated total (with HST)")).toHaveLength(2); // summary card and shopping list
  });

  it("row click highlights that row's parts in the Scene, and a second click clears it", () => {
    const { container } = loaded();
    const row = plan.cut_list[1];
    const tr = container.querySelector(`tr[data-label="${row.label}"]`)!;

    fireEvent.click(tr);
    expect(useStore.getState().highlightedPartIds).toEqual(row.part_ids);
    expect(screen.getByTestId("scene").dataset.highlighted).toBe(row.part_ids.join(","));
    expect(tr.getAttribute("aria-current")).toBe("true");

    fireEvent.click(tr);
    expect(useStore.getState().highlightedPartIds).toEqual([]);
  });

  it("clicking a part in the Scene selects its cut-list row; the background clears it", () => {
    loaded();
    const partId = spec.parts[0].id;
    const row = plan.cut_list.find((r) => r.part_ids.includes(partId))!;
    fireEvent.click(screen.getByRole("button", { name: "scene: click first part" }));
    expect(useStore.getState().highlightedPartIds).toEqual(row.part_ids);
    fireEvent.click(screen.getByRole("button", { name: "scene: click background" }));
    expect(useStore.getState().highlightedPartIds).toEqual([]);
  });

  it("Start building goes to Build mode and clears the highlight", () => {
    const { container, unmount } = loaded();
    fireEvent.click(container.querySelector("tr[data-label]")!);
    fireEvent.click(screen.getAllByRole("button", { name: "Start building" })[0]);
    expect(useStore.getState().screen).toBe("build");
    unmount();
    expect(useStore.getState().highlightedPartIds).toEqual([]);
  });

  it("Back to design goes to Design", () => {
    loaded();
    fireEvent.click(screen.getAllByRole("button", { name: "Back to design" })[0]);
    expect(useStore.getState().screen).toBe("design");
  });
});
