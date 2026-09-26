import type { ParamValue, TemplateInfo } from "../types";
import { SourceTag } from "./common/SourceTag";

type SchemaProperty = { title?: string; description?: string; type?: string | string[]; enum?: string[]; minimum?: number; maximum?: number };

interface ParamPanelProps {
  template: TemplateInfo;
  params: Record<string, ParamValue>;
  onChange: (name: string, value: number | string | boolean | null) => void;
  busy?: boolean;
}

export function ParamPanel({ template, params, onChange, busy = false }: ParamPanelProps) {
  const properties = (template.params_schema.properties ?? {}) as Record<string, SchemaProperty>;
  return (
    <section className="app-card p-4" aria-labelledby="parameters-title">
      <div className="mb-3 flex items-baseline justify-between gap-2"><h3 id="parameters-title" className="m-0 text-lg font-bold">Parameters</h3>{busy && <span role="status" className="text-sm text-[var(--text-muted)]">Updating model…</span>}</div>
      <div className="space-y-4">
        {Object.entries(properties).map(([name, property]) => {
          const current = params[name];
          if (!current) return null;
          const title = property.title ?? name.replaceAll("_", " ");
          const types = Array.isArray(property.type) ? property.type : [property.type];
          const assumption = current.source === "inferred" || current.source === "default";
          const id = `parameter-${name}`;
          return <div key={name} className={`rounded p-2 ${assumption ? "assumption" : ""}`}>
            <div className="mb-1 flex flex-wrap items-center justify-between gap-2"><label htmlFor={id} className="font-semibold">{title}</label><SourceTag source={current.source} /></div>
            {property.description && <p className="mb-2 text-sm text-[var(--text-muted)]">{property.description}</p>}
            {property.enum ? (
              <div className="flex flex-wrap gap-1" role="group" aria-label={title}>
                {property.enum.map((choice) => <button key={choice} type="button" disabled={busy} aria-pressed={current.value === choice} onClick={() => onChange(name, choice)} className={`min-h-10 rounded px-3 text-sm ${current.value === choice ? "bg-[var(--brand)] text-[var(--brand-contrast)]" : "border border-[var(--border)]"}`}>{choice}</button>)}
              </div>
            ) : types.includes("boolean") ? (
              <label className="flex min-h-11 items-center gap-2"><input id={id} type="checkbox" checked={Boolean(current.value)} disabled={busy} onChange={(event) => onChange(name, event.target.checked)} /> Enable</label>
            ) : types.includes("number") ? (
              <div className="flex items-center gap-2">
                {property.minimum !== undefined && property.maximum !== undefined && <input aria-label={`${title} slider`} type="range" min={property.minimum} max={property.maximum} value={typeof current.value === "number" ? current.value : ""} disabled={busy} onChange={(event) => onChange(name, Number(event.target.value))} className="min-h-11 flex-1" />}
                <input id={id} className="app-input w-24" type="number" min={property.minimum} max={property.maximum} value={typeof current.value === "number" ? current.value : ""} disabled={busy} onChange={(event) => onChange(name, event.target.value === "" && types.includes("null") ? null : Number(event.target.value))} />
              </div>
            ) : null}
            {property.minimum !== undefined && property.maximum !== undefined && <p className="mb-0 mt-1 text-xs text-[var(--text-muted)]">Allowed range: {property.minimum}–{property.maximum} in</p>}
          </div>;
        })}
      </div>
    </section>
  );
}
