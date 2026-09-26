// Owner: P4. Previous / Repeat / Next buttons, with their keyboard shortcuts shown.
import type { BuildAction } from "./navigation";

export interface BuildControlsProps {
  onAction: (action: BuildAction) => void;
  canGoBack: boolean;
  /** Label for the Next button ("Finish" on the last step). */
  nextLabel?: string;
}

const BTN = "min-h-14 rounded px-5 py-3 text-lg font-semibold focus-visible:outline-3 focus-visible:outline-offset-2";

export function BuildControls({ onAction, canGoBack, nextLabel = "Next" }: BuildControlsProps) {
  return (
    <div role="group" aria-label="Step controls" className="flex flex-wrap gap-3">
      <button
        type="button"
        onClick={() => onAction("back")}
        disabled={!canGoBack}
        aria-keyshortcuts="ArrowLeft"
        className={`${BTN} border-2 border-slate-700 hover:bg-slate-100 disabled:border-slate-300 disabled:text-slate-400`}
      >
        ← Previous
      </button>
      <button
        type="button"
        onClick={() => onAction("repeat")}
        aria-keyshortcuts="R"
        className={`${BTN} border-2 border-slate-700 hover:bg-slate-100`}
      >
        Repeat (R)
      </button>
      <button
        type="button"
        onClick={() => onAction("next")}
        aria-keyshortcuts="ArrowRight"
        className={`${BTN} bg-slate-900 text-white hover:bg-slate-700`}
      >
        {nextLabel} →
      </button>
    </div>
  );
}
