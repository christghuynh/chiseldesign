import type { RuleCheck } from "../types";

interface RuleBadgesProps {
  rules: RuleCheck[];
  onApplyFix: (rule: RuleCheck) => void;
  busy?: boolean;
}

const tone: Record<RuleCheck["status"], string> = { pass: "rule-status rule-status--pass", warn: "rule-status rule-status--warn", fail: "rule-status rule-status--fail", info: "rule-status rule-status--info" };

export function RuleBadges({ rules, onApplyFix, busy = false }: RuleBadgesProps) {
  return <section className="app-card p-4" aria-labelledby="checks-title"><h3 id="checks-title" className="m-0 text-lg font-bold">Guideline checks</h3><div className="mt-3 space-y-2">{rules.map((rule) => <article key={rule.id} className="rounded border border-[var(--border)] p-3"><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2 py-1 text-xs font-bold uppercase ${tone[rule.status]}`}>{rule.status}</span><strong>{rule.id}: {rule.title}</strong></div><p className="mb-2 mt-2 text-sm">{rule.detail}</p><div className="flex flex-wrap items-center gap-3"><a href={`#${rule.source_ref}`} className="text-sm underline">Guideline reference</a>{rule.fix && <button type="button" disabled={busy} className="app-button text-sm" onClick={() => onApplyFix(rule)}>{rule.fix.label}</button>}</div></article>)}</div></section>;
}
