// Owner: P4. Plan screen (FE-7): summary, cut list with a mini 3D view, cutting layouts, shopping list and
// the safety notice, plus downloads and a print stylesheet (FE-10). Selecting a cut-list row highlights
// its parts in the Scene (uiSlice.setHighlighted).
import { useEffect, useState } from "react";
import { CutListTable } from "../components/plan/CutListTable";
import { Downloads } from "../components/plan/Downloads";
import { LayoutList } from "../components/plan/LayoutList";
import { SafetyNotice } from "../components/plan/SafetyNotice";
import { ShoppingList } from "../components/plan/ShoppingList";
import { SummaryCard } from "../components/plan/SummaryCard";
import { EmptyState } from "../components/common/EmptyState";
import { ProjectHealth } from "../components/ProjectHealth";
import { SaveProject } from "../components/projects/SaveProject";
import { useStore } from "../store";
import { Scene } from "../three/Scene";
import "../components/plan/print.css";

const PRIMARY = "app-button";
const SECONDARY = "app-button app-button--secondary";

export function Plan() {
  const spec = useStore((s) => s.spec);
  const plan = useStore((s) => s.plan);
  const highlightedPartIds = useStore((s) => s.highlightedPartIds);
  const setHighlighted = useStore((s) => s.setHighlighted);
  const setScreen = useStore((s) => s.setScreen);
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);

  // Highlights belong to this screen: start clean, reset when the plan changes, clear on the way out.
  useEffect(() => {
    setSelectedLabel(null);
    setHighlighted([]);
  }, [plan, setHighlighted]);
  useEffect(() => () => setHighlighted([]), [setHighlighted]);

  if (!spec || !plan) {
    return (
      <section aria-labelledby="plan-title" className="workflow-empty-page mx-auto max-w-5xl">
        <div className="workflow-empty-page__heading"><p>04 · Plan</p><h2 id="plan-title">Plan</h2></div>
        <EmptyState variant="plan" eyebrow="Your materials, mapped out" title="There is no plan yet" description="Finish shaping a design first. Then you’ll get a cut list, layouts, materials, and a build-ready plan.">
          <button type="button" onClick={() => setScreen("design")} className="app-button">Back to design</button>
        </EmptyState>
      </section>
    );
  }

  const selectLabel = (label: string | null) => {
    const row = label === null || label === selectedLabel ? undefined : plan.cut_list.find((r) => r.label === label);
    setSelectedLabel(row?.label ?? null);
    setHighlighted(row?.part_ids ?? []);
  };

  const selectPart = (partId: string | null) => {
    const row = partId === null ? undefined : plan.cut_list.find((r) => r.part_ids.includes(partId));
    selectLabel(row && row.label !== selectedLabel ? row.label : null);
  };

  const nav = (
    <div className="print-hide flex flex-wrap gap-2">
      <button type="button" onClick={() => setScreen("design")} className={SECONDARY}>
        Back to design
      </button>
      <button type="button" onClick={() => setScreen("build")} className={PRIMARY}>
        Start building
      </button>
    </div>
  );

  return (
    <section id="plan-screen" aria-labelledby="plan-title" className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="plan-title" className="text-2xl font-semibold">
          Plan
        </h2>
        {nav}
      </div>

      <ProjectHealth spec={spec} plan={plan} showPricing />
      <SummaryCard spec={spec} plan={plan} />

      <section aria-labelledby="cutlist-title" className="plan-cutlist grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-2">
          <h3 id="cutlist-title" className="text-xl font-semibold">
            Cut list
          </h3>
          <p className="print-hide text-slate-700">Select a row to see those parts in the 3D view.</p>
          <CutListTable rows={plan.cut_list} selectedLabel={selectedLabel} onRowSelect={selectLabel} />
        </div>
        <div className="print-hide lg:sticky lg:top-4 lg:self-start">
          <div className="overflow-hidden rounded border border-slate-300">
            <Scene parts={spec.parts} highlightedIds={highlightedPartIds} onSelect={selectPart} height="22rem" />
          </div>
          <p role="status" className="mt-2 min-h-6">
            {selectedLabel
              ? `Showing ${highlightedPartIds.length} ${highlightedPartIds.length === 1 ? "part" : "parts"} labeled ${selectedLabel}.`
              : ""}
          </p>
        </div>
      </section>

      <section aria-labelledby="layouts-title" className="space-y-2">
        <h3 id="layouts-title" className="text-xl font-semibold">
          Cutting layouts
        </h3>
        <p className="text-slate-700">One diagram per board or sheet to buy. Hatched areas are offcuts.</p>
        <LayoutList layouts={plan.layouts} highlightedLabel={selectedLabel} />
      </section>

      <section aria-labelledby="shopping-title" className="space-y-2">
        <h3 id="shopping-title" className="text-xl font-semibold">
          Shopping list
        </h3>
        <ShoppingList
          items={plan.shopping}
          subtotal={plan.subtotal}
          tax={plan.tax}
          total={plan.total}
          estimate={plan.has_placeholder_prices}
        />
      </section>

      <section aria-labelledby="downloads-title" className="print-hide space-y-2">
        <h3 id="downloads-title" className="text-xl font-semibold">
          Downloads
        </h3>
        <Downloads spec={spec} plan={plan} />
      </section>

      <section aria-labelledby="save-title" className="print-hide space-y-2">
        <h3 id="save-title" className="text-xl font-semibold">
          Save
        </h3>
        <SaveProject />
      </section>

      <SafetyNotice />

      {nav}
    </section>
  );
}
