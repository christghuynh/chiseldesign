// Owner: P4. The safety disclaimer shown on the Plan screen and in the printed plan.

export function SafetyNotice() {
  return (
    <aside aria-labelledby="safety-title" className="safety-notice rounded border-2 border-amber-500 bg-amber-50 p-4">
      <h3 id="safety-title" className="text-lg font-semibold">
        Safety notice
      </h3>
      <p className="mt-1">
        <strong>Guidelines, not code compliance.</strong> Check local permit requirements before you build. Rule checks
        follow published accessibility guidelines but are not a substitute for an inspector or a qualified builder.
      </p>
      <p className="mt-1">Wear eye and hearing protection when cutting, and follow your tools' safety instructions.</p>
    </aside>
  );
}
