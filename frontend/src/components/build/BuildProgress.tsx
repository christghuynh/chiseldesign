// Owner: P4. Progress through the build steps.
export interface BuildProgressProps {
  /** Steps finished so far (the current step counts once the builder moves past it). */
  completed: number;
  total: number;
}

export function BuildProgress({ completed, total }: BuildProgressProps) {
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  return (
    <div
      role="progressbar"
      aria-label="Build progress"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={completed}
      aria-valuetext={`${completed} of ${total} steps done`}
      className="h-3 w-full overflow-hidden rounded-full bg-slate-200"
    >
      <div className="h-full bg-emerald-600 motion-safe:transition-[width]" style={{ width: `${pct}%` }} />
    </div>
  );
}
