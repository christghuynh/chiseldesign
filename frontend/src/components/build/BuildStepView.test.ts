import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GenerateResponse, InstructionsResponse } from "../../types";
import { BuildControls } from "./BuildControls";
import { BuildProgress } from "./BuildProgress";
import { BuildStepView } from "./BuildStepView";

const fixtures = resolve(import.meta.dirname, "../../../../fixtures");
const { steps } = JSON.parse(
  readFileSync(resolve(fixtures, "instructions/ramp_switchback.json"), "utf8"),
) as InstructionsResponse;
const { plan } = JSON.parse(readFileSync(resolve(fixtures, "specs/ramp_switchback.json"), "utf8")) as GenerateResponse;

// renderToStaticMarkup escapes text; undo the entities the fixture text can contain.
const unescape = (html: string) =>
  html.replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
const render = (el: Parameters<typeof renderToStaticMarkup>[0]) => unescape(renderToStaticMarkup(el));

describe("BuildStepView renders the fixture steps", () => {
  it.each(steps.map((step, i) => [step.n, step, i] as const))("step %i", (_n, step, i) => {
    const html = render(createElement(BuildStepView, { step, index: i, total: steps.length }));
    expect(html).toContain(`Step ${i + 1} of ${steps.length}`);
    expect(html).toContain(step.title);
    expect(html).toContain(step.text);
    for (const c of step.cut_callouts) expect(html).toContain(c.spoken);
    if (step.safety_tip) expect(html).toContain(step.safety_tip);
    else expect(html).not.toContain("Safety:");
  });

  it("shows the cut-list length for callouts when the plan is given", () => {
    const step = steps.find((s) => s.cut_callouts.some((c) => plan.cut_list.some((r) => r.label === c.label)))!;
    const html = render(createElement(BuildStepView, { step, index: 0, total: 1, cutList: plan.cut_list }));
    for (const c of step.cut_callouts) {
      const row = plan.cut_list.find((r) => r.label === c.label);
      if (row) expect(html).toContain(row.length_display);
    }
  });
});

describe("BuildControls and BuildProgress", () => {
  it("disables Previous on the first step and labels Next", () => {
    const html = render(createElement(BuildControls, { onAction: () => {}, canGoBack: false, nextLabel: "Finish" }));
    expect(html).toMatch(/<button[^>]*disabled[^>]*>← Previous/);
    expect(html).toContain("Finish →");
  });

  it("reports progress to assistive tech", () => {
    const html = render(createElement(BuildProgress, { completed: 3, total: 11 }));
    expect(html).toContain('aria-valuenow="3"');
    expect(html).toContain('aria-valuemax="11"');
    expect(html).toContain("width:27%");
  });
});
