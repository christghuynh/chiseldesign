// Owner: P4. Shown after the last step.
export interface BuildDoneProps {
  total: number;
  onRestart: () => void;
  onBack: () => void;
  onPlan: () => void;
}

const BTN = "min-h-14 rounded px-5 py-3 text-lg font-semibold";

export function BuildDone({ total, onRestart, onBack, onPlan }: BuildDoneProps) {
  return (
    <section aria-labelledby="build-done-title" className="space-y-4">
      <h3 id="build-done-title" className="text-4xl font-bold">
        Done!
      </h3>
      <p className="text-xl">
        You finished all {total} steps. Walk the ramp slowly once before anyone relies on it, and check every
        fastener.
      </p>
      <div className="flex flex-wrap gap-3">
        <button type="button" onClick={onBack} className={`${BTN} border-2 border-slate-700 hover:bg-slate-100`}>
          ← Last step
        </button>
        <button type="button" onClick={onRestart} className={`${BTN} border-2 border-slate-700 hover:bg-slate-100`}>
          Start over
        </button>
        <button type="button" onClick={onPlan} className={`${BTN} bg-slate-900 text-white hover:bg-slate-700`}>
          Back to the plan
        </button>
      </div>
    </section>
  );
}
