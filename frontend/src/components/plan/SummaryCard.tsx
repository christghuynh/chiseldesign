// Owner: P4. Template, key dimensions, rule status, total and the contractor-quote comparison.
import type { Plan, RuleCheck, Spec } from "../../types";
import { formatFtIn } from "../../util/units";
import { formatCad } from "./format";

export interface SummaryCardProps {
  spec: Spec;
  plan: Plan;
}

/** The params shown as key dimensions, per template. Other templates show their first few params. */
const KEY_PARAMS: Record<string, string[]> = {
  ramp: ["total_rise_in", "clear_width_in", "layout", "slope_ratio"],
};

const PARAM_LABELS: Record<string, string> = {
  total_rise_in: "Total rise",
  clear_width_in: "Clear width",
  layout: "Layout",
  slope_ratio: "Slope",
};

function paramLabel(key: string): string {
  if (PARAM_LABELS[key]) return PARAM_LABELS[key];
  const words = key.replace(/_in$/, "").replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function paramValue(key: string, value: number | string | boolean): string {
  if (key === "slope_ratio" && typeof value === "number") return `1:${value}`;
  if (key.endsWith("_in") && typeof value === "number") return formatFtIn(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value.charAt(0).toUpperCase() + value.slice(1);
  return String(value);
}

export type RuleSummary = "fail" | "warn" | "pass";

export function ruleSummary(checks: RuleCheck[]): RuleSummary {
  if (checks.some((c) => c.status === "fail")) return "fail";
  if (checks.some((c) => c.status === "warn")) return "warn";
  return "pass";
}

const RULE_TEXT: Record<RuleSummary, { text: string; className: string }> = {
  fail: { text: "Some checks fail", className: "border-red-600 bg-red-50 text-red-900" },
  warn: { text: "Passes, with warnings", className: "border-amber-500 bg-amber-50 text-amber-900" },
  pass: { text: "All checks pass", className: "border-green-600 bg-green-50 text-green-900" },
};

export function SummaryCard({ spec, plan }: SummaryCardProps) {
  const keys = KEY_PARAMS[spec.template] ?? Object.keys(spec.params).slice(0, 4);
  const dims = keys.filter((k) => k in spec.params).map((k) => ({ key: k, label: paramLabel(k), value: paramValue(k, spec.params[k].value) }));
  const status = ruleSummary(spec.rule_checks);
  const problems = spec.rule_checks.filter((c) => c.status === "fail" || c.status === "warn");
  const counted = spec.rule_checks.filter((c) => c.status !== "info");
  const passed = counted.filter((c) => c.status === "pass").length;
  const templateName = spec.template.charAt(0).toUpperCase() + spec.template.slice(1).replace(/_/g, " ");

  return (
    <section aria-labelledby="summary-title" className="summary-card rounded border border-slate-300 p-4">
      <h3 id="summary-title" className="text-xl font-semibold">
        {templateName}
      </h3>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        {dims.map((d) => (
          <div key={d.key}>
            <dt className="text-sm text-slate-600">{d.label}</dt>
            <dd className="text-lg font-medium">{d.value}</dd>
          </div>
        ))}
      </dl>

      <div className={`mt-4 rounded border-l-4 px-3 py-2 ${RULE_TEXT[status].className}`}>
        <p className="font-medium">
          {RULE_TEXT[status].text} ({passed} of {counted.length} passed)
        </p>
        {problems.length > 0 && (
          <ul className="mt-1 list-disc pl-5">
            {problems.map((c) => (
              <li key={c.id}>
                {c.status === "fail" ? "Fails" : "Warning"}: {c.title}
              </li>
            ))}
          </ul>
        )}
      </div>

      <dl className="mt-4 flex flex-wrap gap-x-10 gap-y-3">
        <div>
          <dt className="text-sm text-slate-600">{plan.has_placeholder_prices ? "Estimated total (with HST)" : "Total (with HST)"}</dt>
          <dd data-testid="summary-total" className="text-2xl font-bold">
            {plan.has_placeholder_prices && "~"}
            {formatCad(plan.total)}
          </dd>
        </div>
        {plan.contractor_quote !== null && (
          <div>
            <dt className="text-sm text-slate-600">Contractor quote</dt>
            <dd className="text-2xl">{formatCad(plan.contractor_quote)}</dd>
          </div>
        )}
        {plan.savings !== null && (
          <div>
            <dt className="text-sm text-slate-600">{plan.savings >= 0 ? "You save" : "Costs more than the quote by"}</dt>
            <dd data-testid="summary-savings" className={`text-2xl font-bold ${plan.savings >= 0 ? "text-green-800" : "text-red-800"}`}>
              ~{formatCad(Math.abs(plan.savings))}
            </dd>
          </div>
        )}
      </dl>
      {plan.has_placeholder_prices && (
        <p className="mt-2 text-sm">
          <span className="rounded bg-amber-200 px-1.5 py-0.5 font-semibold text-amber-950">Estimate</span> Some prices are
          placeholders; the real total may differ.
        </p>
      )}
    </section>
  );
}
