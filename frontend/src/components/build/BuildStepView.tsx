// Owner: P4. One build step in large text: step n of N, title, instruction, cut callouts and
// safety tip. Props only, so it renders the same from fixtures, the store or a dev page.
import type { BuildStep, CutListRow } from "../../types";

export interface BuildStepViewProps {
  step: BuildStep;
  /** Zero-based position of the step in the list. */
  index: number;
  total: number;
  /** When given, each callout also shows its cut-list row (material and length). */
  cutList?: CutListRow[];
}

export function BuildStepView({ step, index, total, cutList = [] }: BuildStepViewProps) {
  const rows = new Map(cutList.map((row) => [row.label, row]));
  return (
    <article aria-labelledby="build-step-title" className="space-y-4">
      <p className="text-lg font-medium text-slate-700">
        Step {index + 1} of {total}
      </p>
      <h3 id="build-step-title" className="text-3xl font-bold leading-tight sm:text-4xl">
        {step.title}
      </h3>
      <p className="max-w-prose text-xl leading-relaxed sm:text-2xl">{step.text}</p>
      {step.cut_callouts.length > 0 && (
        <section aria-label="Cuts for this step" className="space-y-2">
          <h4 className="text-lg font-semibold">Cuts</h4>
          <ul className="space-y-2">
            {step.cut_callouts.map((callout) => {
              const row = rows.get(callout.label);
              return (
                <li
                  key={callout.label}
                  className="flex flex-wrap items-baseline gap-x-3 rounded border border-slate-300 px-3 py-2 text-xl"
                >
                  <span className="font-mono font-bold">{callout.label}</span>
                  {row ? (
                    <span>
                      {row.name}, {row.material}, {row.length_display}
                      {row.qty > 1 ? ` × ${row.qty}` : ""}
                    </span>
                  ) : (
                    <span>{callout.spoken}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {step.safety_tip && (
        <p role="note" className="rounded border-l-4 border-amber-600 bg-amber-50 px-4 py-3 text-lg text-amber-950">
          <strong>Safety: </strong>
          {step.safety_tip}
        </p>
      )}
    </article>
  );
}
