// Owner: P4. Dev page at /dev/plan: the Plan components rendered from the fixture plans, no store.
// Fixtures are fetched from /fixtures, which the dev server always serves.
import { useEffect, useState } from "react";
import { CutListTable } from "../../components/plan/CutListTable";
import { LayoutList } from "../../components/plan/LayoutList";
import { SafetyNotice } from "../../components/plan/SafetyNotice";
import { ShoppingList } from "../../components/plan/ShoppingList";
import { SummaryCard } from "../../components/plan/SummaryCard";
import type { GenerateResponse } from "../../types";

const FIXTURES = ["ramp_switchback", "ramp_straight"] as const;
type FixtureName = (typeof FIXTURES)[number];

export default function PlanDev() {
  const [which, setWhich] = useState<FixtureName>("ramp_switchback");
  const [data, setData] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setLabel(null);
    fetch(`/fixtures/specs/${which}.json`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((json: GenerateResponse) => !cancelled && setData(json))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [which]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4">
      <h1 className="text-xl font-bold">Plan components (fixtures)</h1>
      <div className="flex gap-2">
        {FIXTURES.map((name) => (
          <button
            key={name}
            type="button"
            aria-pressed={name === which}
            onClick={() => setWhich(name)}
            className="min-h-11 rounded border border-slate-400 px-3 aria-pressed:bg-slate-900 aria-pressed:text-white"
          >
            {name}.json
          </button>
        ))}
      </div>
      {error && <p role="alert">Could not load the fixture: {error}</p>}
      {data && (
        <>
          <SummaryCard spec={data.spec} plan={data.plan} />
          <p role="status">Selected row: {label ?? "none"}</p>
          <CutListTable rows={data.plan.cut_list} selectedLabel={label} onRowSelect={(l) => setLabel(l === label ? null : l)} />
          <LayoutList layouts={data.plan.layouts} highlightedLabel={label} />
          <ShoppingList
            items={data.plan.shopping}
            subtotal={data.plan.subtotal}
            tax={data.plan.tax}
            total={data.plan.total}
            estimate={data.plan.has_placeholder_prices}
          />
          <SafetyNotice />
        </>
      )}
    </div>
  );
}
