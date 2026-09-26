// @vitest-environment jsdom
// FE-7a acceptance: LayoutSvg, ShoppingList and CutListTable against the fixture plans.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { GenerateResponse, StockLayout } from "../../types";
import { CutListTable } from "./CutListTable";
import { formatCad } from "./format";
import { layoutGeometry } from "./layoutGeometry";
import { LayoutSvg } from "./LayoutSvg";
import { SafetyNotice } from "./SafetyNotice";
import { ShoppingList } from "./ShoppingList";
import { SummaryCard } from "./SummaryCard";

const load = (file: string): GenerateResponse =>
  JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../fixtures/specs", file), "utf8"));
const FIXTURES = { straight: load("ramp_straight.json"), switchback: load("ramp_switchback.json") };

afterEach(cleanup);

const num = (el: Element, attr: string) => Number(el.getAttribute(attr));

describe("LayoutSvg", () => {
  const layouts = Object.values(FIXTURES).flatMap((f) => f.plan.layouts);

  it.each(layouts.map((l) => [l.stock_id, l] as const))("%s: one rect per piece, all inside the stock", (_id, layout) => {
    const { container } = render(h(LayoutSvg, { layout }));
    const stock = container.querySelector("rect[data-stock]")!;
    const pieces = container.querySelectorAll("rect[data-piece]");
    expect(pieces).toHaveLength(layout.pieces.length);
    const [sw, sh] = [num(stock, "width"), num(stock, "height")];
    for (const piece of pieces) {
      expect(num(piece, "x")).toBeGreaterThanOrEqual(0);
      expect(num(piece, "y")).toBeGreaterThanOrEqual(0);
      expect(num(piece, "x") + num(piece, "width")).toBeLessThanOrEqual(sw + 1e-9);
      expect(num(piece, "y") + num(piece, "height")).toBeLessThanOrEqual(sh + 1e-9);
    }
  });

  it("clamps a piece that overflows the stock", () => {
    const layout: StockLayout = {
      stock_id: "bad-1",
      material: "2x6_PT",
      kind: "board",
      length_in: 96,
      width_in: 5.5,
      utilization: 1,
      pieces: [{ label: "A", part_id: "A-1", x: 50, y: -1, w: 60, h: 7, rotated: false }],
    };
    const g = layoutGeometry(layout);
    expect(g.pieces[0].x + g.pieces[0].w).toBeCloseTo(g.width);
    expect(g.pieces[0].y).toBe(0);
    expect(g.pieces[0].h).toBeCloseTo(g.height);
  });

  it("keeps a sheet's aspect ratio and stretches a board so it stays readable", () => {
    const sheet: StockLayout = { stock_id: "ply-1", material: "3/4_ext_ply", kind: "sheet", length_in: 96, width_in: 48, pieces: [], utilization: 0 };
    expect(layoutGeometry(sheet, { width: 600 }).height).toBeCloseTo(300);
    const board = FIXTURES.straight.plan.layouts[0];
    expect(layoutGeometry(board, { width: 600, minHeight: 44 }).height).toBeCloseTo(44);
  });

  it("shows utilization and labels the drawing", () => {
    const layout = FIXTURES.straight.plan.layouts[0];
    render(h(LayoutSvg, { layout }));
    expect(screen.getByText("94% used")).toBeTruthy();
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain("A");
  });
});

describe("ShoppingList", () => {
  it.each(Object.entries(FIXTURES))("%s: subtotal, tax and total match the fixture", (_name, { plan }) => {
    const itemsSum = plan.shopping.reduce((sum, item) => sum + item.subtotal, 0);
    expect(itemsSum).toBeCloseTo(plan.subtotal, 2);

    render(h(ShoppingList, { items: plan.shopping, subtotal: plan.subtotal, tax: plan.tax, total: plan.total }));
    expect(screen.getAllByRole("row")).toHaveLength(1 + plan.shopping.length + 3);
    expect(screen.getByTestId("shopping-subtotal").textContent).toBe(formatCad(plan.subtotal));
    expect(screen.getByTestId("shopping-tax").textContent).toBe(formatCad(plan.tax));
    expect(screen.getByTestId("shopping-total").textContent).toBe(formatCad(plan.total));
  });

  it("the HST toggle switches the total to the subtotal", () => {
    const { plan } = FIXTURES.straight;
    render(h(ShoppingList, { items: plan.shopping, subtotal: plan.subtotal, tax: plan.tax, total: plan.total }));
    fireEvent.click(screen.getByLabelText("Include 13% HST"));
    expect(screen.getByTestId("shopping-total").textContent).toBe(formatCad(plan.subtotal));
    expect(screen.queryByTestId("shopping-tax")).toBeNull();
    fireEvent.click(screen.getByLabelText("Include 13% HST"));
    expect(screen.getByTestId("shopping-total").textContent).toBe(formatCad(plan.total));
  });

  it("labels the total as an estimate when prices are placeholders", () => {
    const { plan } = FIXTURES.straight;
    const props = { items: plan.shopping, subtotal: plan.subtotal, tax: plan.tax, total: plan.total };
    render(h(ShoppingList, { ...props, estimate: true }));
    expect(screen.getByText(/Estimated total/)).toBeTruthy();
    expect(screen.getByText(/this total is an estimate/)).toBeTruthy();
    cleanup();
    render(h(ShoppingList, { ...props, estimate: false }));
    expect(screen.queryByText(/Estimated total/)).toBeNull();
  });
});

describe("CutListTable", () => {
  const rows = FIXTURES.switchback.plan.cut_list;

  it("renders one row per label with length and qty", () => {
    render(h(CutListTable, { rows }));
    const body = screen.getAllByRole("rowgroup")[1];
    expect(within(body).getAllByRole("row")).toHaveLength(rows.length);
    expect(screen.getAllByText(rows[0].length_display).length).toBeGreaterThan(0);
  });

  it("row click fires onRowSelect with the label", () => {
    const onRowSelect = vi.fn();
    const { container } = render(h(CutListTable, { rows, onRowSelect }));
    const target = rows[2];
    fireEvent.click(container.querySelector(`tr[data-label="${target.label}"] td`)!);
    expect(onRowSelect).toHaveBeenCalledExactlyOnceWith(target.label);
  });

  it("Enter on a focused row also selects it", () => {
    const onRowSelect = vi.fn();
    const { container } = render(h(CutListTable, { rows, onRowSelect }));
    fireEvent.keyDown(container.querySelector(`tr[data-label="${rows[0].label}"]`)!, { key: "Enter" });
    expect(onRowSelect).toHaveBeenCalledWith(rows[0].label);
  });

  it("marks the selected row", () => {
    const { container } = render(h(CutListTable, { rows, selectedLabel: rows[1].label, onRowSelect: () => {} }));
    expect(container.querySelectorAll('tr[aria-current="true"]')).toHaveLength(1);
  });
});

describe("SummaryCard", () => {
  it("shows the total as an estimate, the quote and the savings", () => {
    const { spec, plan } = FIXTURES.switchback;
    render(h(SummaryCard, { spec, plan }));
    expect(screen.getByTestId("summary-total").textContent).toBe(`~${formatCad(plan.total)}`);
    expect(screen.getByText(/Estimated total/)).toBeTruthy();
    expect(screen.getByTestId("summary-savings").textContent).toBe(`~${formatCad(plan.savings!)}`);
    expect(screen.getByText("All checks pass (7 of 7 passed)")).toBeTruthy();
    expect(screen.getByText(`1' 3"`)).toBeTruthy(); // total rise, 15 in
  });

  it("lists failing rules and drops the estimate label for real prices", () => {
    const { spec, plan } = FIXTURES.straight;
    render(h(SummaryCard, { spec, plan: { ...plan, has_placeholder_prices: false } }));
    expect(screen.getByText("Some checks fail (6 of 7 passed)")).toBeTruthy();
    expect(screen.getByText("Fails: Fits the available length")).toBeTruthy();
    expect(screen.getByTestId("summary-total").textContent).toBe(formatCad(plan.total));
    expect(screen.queryByText("Estimate")).toBeNull();
  });
});

describe("SafetyNotice", () => {
  it("says guidelines, not code compliance", () => {
    render(h(SafetyNotice));
    expect(screen.getByText(/Guidelines, not code compliance/)).toBeTruthy();
    expect(screen.getByText(/permit requirements/)).toBeTruthy();
  });
});
