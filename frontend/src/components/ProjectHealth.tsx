import type { Plan, Spec } from "../types";

type HealthTone = "pass" | "attention" | "fail";

type HealthItem = {
  label: string;
  tone: HealthTone;
};

export interface ProjectHealthProps {
  spec: Spec;
  plan: Plan;
  className?: string;
  showPricing?: boolean;
}

/** A small, factual readiness summary; it deliberately never claims code compliance or engineering approval. */
export function ProjectHealth({ spec, plan, className = "", showPricing = false }: ProjectHealthProps) {
  const failed = spec.rule_checks.filter((rule) => rule.status === "fail").length;
  const warnings = spec.rule_checks.filter((rule) => rule.status === "warn").length;
  const assumptions = Object.values(spec.params).filter((param) => param.source === "inferred" || param.source === "default").length;
  const needsAttention = failed > 0 || warnings > 0 || assumptions > 0 || (showPricing && plan.has_placeholder_prices);
  const items: HealthItem[] = [
    failed > 0
      ? { label: `${failed} guideline ${failed === 1 ? "check fails" : "checks fail"}`, tone: "fail" }
      : warnings > 0
        ? { label: `${warnings} guideline ${warnings === 1 ? "warning" : "warnings"}`, tone: "attention" }
        : { label: "Guideline checks pass", tone: "pass" },
    assumptions > 0
      ? { label: `${assumptions} ${assumptions === 1 ? "assumption" : "assumptions"} to review`, tone: "attention" }
      : { label: "Measurements confirmed", tone: "pass" },
  ];

  if (showPricing) {
    items.push(plan.has_placeholder_prices
      ? { label: "Prices are estimates", tone: "attention" }
      : { label: "Materials priced", tone: "pass" });
  }

  return (
    <section className={`project-health ${className}`.trim()} aria-label="Project planning status">
      <p className={`project-health__summary project-health__summary--${needsAttention ? "attention" : "pass"}`}>
        <span aria-hidden="true" className="project-health__summary-mark" />
        {needsAttention ? "Needs attention" : "Planning status ready"}
      </p>
      <ul className="project-health__items">
        {items.map((item) => <li key={item.label} className={`project-health__item project-health__item--${item.tone}`}>{item.label}</li>)}
      </ul>
    </section>
  );
}
