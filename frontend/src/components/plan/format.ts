// Owner: P4. Display helpers shared by the Plan components. Numbers come from the plan; these only format.

const CAD = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" });

/** CAD money, 2 decimals: `$1,234.50`. */
export function formatCad(amount: number): string {
  return CAD.format(amount);
}

/** A 0..1 fraction as a whole percentage: `0.9407` → `94%`. */
export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}
