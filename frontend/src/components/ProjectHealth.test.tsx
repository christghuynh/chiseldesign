// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { describe, expect, it } from "vitest";
import type { GenerateResponse, Spec } from "../types";
import { ProjectHealth } from "./ProjectHealth";

const fixture = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../fixtures/specs/ramp_straight.json"), "utf8")) as GenerateResponse;

function readySpec(): Spec {
  return {
    ...fixture.spec,
    params: Object.fromEntries(Object.entries(fixture.spec.params).map(([name, param]) => [name, { ...param, source: "user" }])),
    rule_checks: fixture.spec.rule_checks.map((rule) => ({ ...rule, status: "pass" })),
  };
}

describe("ProjectHealth", () => {
  it("shows a ready planning state when checks and measurements are confirmed", () => {
    render(h(ProjectHealth, { spec: readySpec(), plan: { ...fixture.plan, has_placeholder_prices: false }, showPricing: true }));
    expect(screen.getByText("Planning status ready")).toBeTruthy();
    expect(screen.getByText("Guideline checks pass")).toBeTruthy();
    expect(screen.getByText("Measurements confirmed")).toBeTruthy();
    expect(screen.getByText("Materials priced")).toBeTruthy();
  });

  it("calls out assumptions, warnings, and placeholder prices without calling the design safe", () => {
    const warningSpec = { ...fixture.spec, rule_checks: fixture.spec.rule_checks.map((rule, index) => index === 0 ? { ...rule, status: "warn" as const } : rule) };
    render(h(ProjectHealth, { spec: warningSpec, plan: { ...fixture.plan, has_placeholder_prices: true }, showPricing: true }));
    expect(screen.getByText("Needs attention")).toBeTruthy();
    expect(screen.getByText("Prices are estimates")).toBeTruthy();
    expect(screen.queryByText(/safe to build/i)).toBeNull();
  });
});
