// Owner: P4. Download buttons (STEP, STL, cut-list CSV) and "Print plan". Hidden when printing.
import { useId, useState } from "react";
import { USE_FIXTURES } from "../../api/client";
import type { Plan, Spec } from "../../types";
import { type ExportedFile, type ExportKind, FIXTURE_EXPORTS, fetchExport, saveBlob } from "./exports";

export interface DownloadsProps {
  spec: Spec;
  plan: Plan;
  /** Defaults to the app's fixture-mode switch. */
  useFixtures?: boolean;
  /** Defaults to a browser download; tests pass a spy. */
  save?: (file: ExportedFile) => void;
  /** Defaults to `window.print`. */
  print?: () => void;
}

const BUTTONS: { kind: ExportKind; label: string; description: string }[] = [
  { kind: "step", label: "STEP", description: "3D model for CAD software" },
  { kind: "stl", label: "STL", description: "3D mesh for viewers and printers" },
  { kind: "csv", label: "Cut list CSV", description: "Opens in a spreadsheet" },
];

const FIXTURE_HINT = "Not available in fixture mode: 3D downloads need the backend.";

export function Downloads({ spec, plan, useFixtures = USE_FIXTURES, save = saveBlob, print = () => window.print() }: DownloadsProps) {
  const [busy, setBusy] = useState<ExportKind | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hintId = useId();

  async function download(kind: ExportKind) {
    setBusy(kind);
    setError(null);
    try {
      save(await fetchExport(kind, spec, plan, useFixtures));
    } catch (e) {
      const label = BUTTONS.find((b) => b.kind === kind)!.label;
      setError(`Could not download the ${label} file. ${e instanceof Error ? e.message : ""}`.trim());
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="print-hide space-y-2">
      <div className="flex flex-wrap gap-2">
        {BUTTONS.map(({ kind, label, description }) => {
          const unavailable = useFixtures && !FIXTURE_EXPORTS.has(kind);
          return (
            <button
              key={kind}
              type="button"
              aria-disabled={unavailable || busy !== null}
              aria-describedby={unavailable ? hintId : undefined}
              title={unavailable ? FIXTURE_HINT : description}
              onClick={unavailable || busy !== null ? undefined : () => download(kind)}
              className="min-h-11 rounded border border-slate-400 px-4 py-2 font-medium hover:bg-slate-100 aria-disabled:cursor-not-allowed aria-disabled:border-slate-300 aria-disabled:text-slate-500 aria-disabled:hover:bg-transparent"
            >
              {busy === kind ? `Preparing ${label}…` : `Download ${label}`}
            </button>
          );
        })}
        <button
          type="button"
          onClick={print}
          className="min-h-11 rounded border border-slate-400 px-4 py-2 font-medium hover:bg-slate-100"
        >
          Print plan
        </button>
      </div>
      {useFixtures && (
        <p id={hintId} className="text-sm text-slate-700">
          {FIXTURE_HINT}
        </p>
      )}
      {error && (
        <p role="alert" className="rounded border border-red-500 bg-red-50 px-3 py-2 text-red-900">
          {error}
        </p>
      )}
    </div>
  );
}
