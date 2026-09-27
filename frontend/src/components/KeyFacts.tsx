// "At a glance": the numbers a builder wants from the current design (slope, lengths, runs, landings...).
// The engine formats them per template in `spec.meta.summary`; this only displays the text. It fits one or two
// columns to the width it gets (the Design side panel is narrow), not to the screen size.
import type { Spec } from "../types";

export interface KeyFact {
  label: string;
  value: string;
  detail?: string;
}

/** The template's summary, or an empty list when the template has none (or the data is malformed). */
export function keyFacts(spec: Spec): KeyFact[] {
  const raw = spec.meta?.summary;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (fact): fact is KeyFact =>
      typeof fact === "object" && fact !== null && typeof fact.label === "string" && typeof fact.value === "string" && (fact.detail === undefined || typeof fact.detail === "string"),
  );
}

export function KeyFacts({ spec }: { spec: Spec }) {
  const facts = keyFacts(spec);
  if (facts.length === 0) return null;
  return (
    <section className="app-card p-4" aria-labelledby="key-facts-title">
      <h3 id="key-facts-title" className="mt-0 text-lg font-bold">
        At a glance
      </h3>
      <dl className="m-0 grid grid-cols-[repeat(auto-fill,minmax(8rem,1fr))] gap-x-4 gap-y-3">
        {facts.map((fact) => (
          <div key={fact.label}>
            <dt className="text-sm text-[var(--text-muted)]">{fact.label}</dt>
            <dd className="m-0 font-semibold">{fact.value}</dd>
            {fact.detail && <dd className="m-0 text-sm text-[var(--text-muted)]">{fact.detail}</dd>}
          </div>
        ))}
      </dl>
    </section>
  );
}
