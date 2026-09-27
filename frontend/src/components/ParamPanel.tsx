// The parameter panel, generated from the template's JSON Schema (FE-6), so a new template needs no UI code.
//
// Schema hints the templates may set on a property: `group` ("key" for the few dimensions people measure,
// "advanced" for construction choices, which fold away under "Advanced settings"), `enum_labels` (readable
// names for choices), `unit` and `empty_label` (what leaving an optional value empty means, "No limit" when
// not given). A template without `group` hints shows every parameter.
//
// Each field keeps a local draft while you type or drag and only sends a value when you finish (Enter,
// leaving the field, or releasing the slider). Out-of-range values show a message instead of snapping, and
// fields stay usable while the model updates.
import { useEffect, useId, useRef, useState } from "react";
import type { ParamValue, TemplateInfo } from "../types";
import { formatFtIn, parseLength } from "../util/units";
import { SourceTag } from "./common/SourceTag";

export type SchemaProperty = {
  title?: string;
  description?: string;
  type?: string | string[];
  enum?: string[];
  enum_labels?: Record<string, string>;
  minimum?: number;
  maximum?: number;
  unit?: string;
  group?: "key" | "advanced";
  /** What an empty optional value means, e.g. "Automatic"; "No limit" when not given. */
  empty_label?: string;
};

type Value = number | string | boolean | null;

interface ParamPanelProps {
  template: TemplateInfo;
  params: Record<string, ParamValue>;
  /** Called once per finished edit. `null` clears an optional parameter. */
  onChange: (name: string, value: Value) => void;
  /** The model is regenerating. Fields stay usable; this only shows a status. */
  busy?: boolean;
}

const typesOf = (property: SchemaProperty) => (Array.isArray(property.type) ? property.type : [property.type]);

export function ParamPanel({ template, params, onChange, busy = false }: ParamPanelProps) {
  const properties = (template.params_schema.properties ?? {}) as Record<string, SchemaProperty>;
  const required = (template.params_schema.required as string[] | undefined) ?? [];
  // Required values nobody has entered yet (e.g. a rise the photo didn't show) still get a field.
  const entries = Object.entries(properties).filter(([name, property]) => params[name] !== undefined || typesOf(property).includes("null") || required.includes(name));
  const grouped = entries.some(([, property]) => property.group);
  const key = grouped ? entries.filter(([, property]) => property.group !== "advanced") : entries;
  const advanced = grouped ? entries.filter(([, property]) => property.group === "advanced") : [];
  const advancedChanged = advanced.filter(([name]) => params[name]?.source === "user").length;

  const field = ([name, property]: [string, SchemaProperty]) => (
    <ParamField key={name} name={name} property={property} current={params[name] ?? null} busy={busy} onChange={onChange} />
  );

  return (
    <section className="app-card p-5" aria-labelledby="parameters-title">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <h3 id="parameters-title" className="m-0 text-lg font-bold">
          {grouped ? "Key dimensions" : "Parameters"}
        </h3>
        {busy && (
          <span role="status" className="text-sm text-[var(--text-muted)]">
            Updating model…
          </span>
        )}
      </div>
      <div className="space-y-5">{key.map(field)}</div>
      {advanced.length > 0 && (
        <details className="mt-5 border-t border-[var(--border)] pt-4">
          <summary className="min-h-11 cursor-pointer font-semibold">
            Advanced settings ({advanced.length})
            {advancedChanged > 0 && <span className="ml-2 text-sm font-normal text-[var(--text-muted)]">{advancedChanged} changed</span>}
          </summary>
          <div className="mt-4 space-y-5">{advanced.map(field)}</div>
        </details>
      )}
    </section>
  );
}

interface ParamFieldProps {
  name: string;
  property: SchemaProperty;
  current: ParamValue | null;
  busy: boolean;
  onChange: (name: string, value: Value) => void;
}

function ParamField({ name, property, current, busy, onChange }: ParamFieldProps) {
  const id = `parameter-${name}`;
  const titleId = `${id}-title`;
  const title = property.title ?? name.replaceAll("_", " ");
  const types = typesOf(property);
  const assumption = current?.source === "inferred" || current?.source === "default";

  let control = null;
  if (property.enum) {
    control = (
      <div className="flex flex-wrap gap-2" role="group" aria-labelledby={titleId}>
        {property.enum.map((choice) => (
          <button
            key={choice}
            type="button"
            aria-pressed={current?.value === choice}
            onClick={() => current?.value !== choice && onChange(name, choice)}
            className={`min-h-10 rounded px-3 text-sm ${current?.value === choice ? "bg-[var(--brand)] text-[var(--brand-contrast)]" : "border border-[var(--border)]"}`}
          >
            {property.enum_labels?.[choice] ?? choice.replaceAll("_", " ")}
          </button>
        ))}
      </div>
    );
  } else if (types.includes("boolean")) {
    control = (
      <label className="flex min-h-11 items-center gap-2">
        <input id={id} type="checkbox" checked={Boolean(current?.value)} onChange={(event) => onChange(name, event.target.checked)} /> On
      </label>
    );
  } else if (types.includes("number") || types.includes("integer")) {
    const value = typeof current?.value === "number" ? current.value : null;
    control = (
      <NumberField
        id={id}
        title={title}
        property={property}
        value={value}
        nullable={types.includes("null")}
        integer={types.includes("integer")}
        busy={busy}
        onCommit={(v) => onChange(name, v)}
      />
    );
  }

  return (
    <div className={`rounded-lg p-3 ${assumption ? "assumption" : ""}`}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        {/* Only text/number/checkbox fields have an element with `id`; a choice group is labelled by
            the title instead, so no <label for> points at a missing element. */}
        {property.enum || control === null ? (
          <span id={titleId} className="font-semibold">
            {title}
          </span>
        ) : (
          <label htmlFor={id} className="font-semibold">
            {title}
          </label>
        )}
        {current ? <SourceTag source={current.source} /> : !types.includes("null") && <span className="source-tag">required</span>}
      </div>
      {property.description && <p className="mb-2 text-sm text-[var(--text-muted)]">{property.description}</p>}
      {control}
    </div>
  );
}

interface NumberFieldProps {
  id: string;
  title: string;
  property: SchemaProperty;
  value: number | null;
  nullable: boolean;
  /** Whole numbers only (schema type "integer"), like a count of steps. */
  integer?: boolean;
  busy: boolean;
  onCommit: (value: number | null) => void;
}

const show = (value: number | null) => (value === null ? "" : String(Number(value.toFixed(3))));

export function NumberField({ id, title, property, value, nullable, integer = false, busy, onCommit }: NumberFieldProps) {
  const { minimum: min, maximum: max } = property;
  const inches = property.unit === "in";
  const empty = property.empty_label ?? "No limit";
  const [draft, setDraft] = useState(show(value));
  const [error, setError] = useState<string | null>(null);
  // While dragging, the slider shows this; after a commit, `pending` holds the sent value until the model answers.
  const [dragging, setDragging] = useState<number | null>(null);
  const [pending, setPending] = useState<number | null | undefined>(undefined);
  const typing = useRef(false);
  const errorId = useId();

  // A new value from the model (a voice edit, undo, a fix) replaces the draft unless you're typing in it.
  useEffect(() => {
    if (busy) return;
    setPending(undefined);
    if (!typing.current) {
      setDraft(show(value));
      setError(null);
    }
  }, [value, busy]);

  const commit = (text: string) => {
    const trimmed = text.trim();
    if (trimmed === "") {
      if (nullable) {
        setError(null);
        if (value !== null) {
          setPending(null);
          onCommit(null);
        }
      } else {
        setError("Enter a value.");
      }
      return;
    }
    let n: number;
    try {
      n = inches ? parseLength(trimmed) : Number(trimmed);
    } catch {
      n = Number.NaN;
    }
    if (!Number.isFinite(n)) {
      setError(inches ? `Enter a length, like 36 or 3' 0".` : "Enter a number.");
      return;
    }
    if (integer && !Number.isInteger(n)) {
      setError("Enter a whole number.");
      return;
    }
    if ((min !== undefined && n < min) || (max !== undefined && n > max)) {
      setError(`Must be between ${min ?? "…"} and ${max ?? "…"}${inches ? " in" : ""}.`);
      return;
    }
    setError(null);
    setDraft(show(n));
    if (n !== value) {
      setPending(n);
      onCommit(n);
    }
  };

  const endDrag = () => {
    if (dragging === null) return;
    const n = dragging;
    setDragging(null);
    commit(String(n));
  };

  const shown = dragging ?? (pending === undefined ? value : pending);
  const hint = inches && shown !== null && shown >= 12 ? `= ${formatFtIn(shown)}` : null;

  return (
    <div>
      <div className="flex items-center gap-2">
        {min !== undefined && max !== undefined && (
          <input
            aria-label={`${title} slider`}
            type="range"
            min={min}
            max={max}
            step={integer || max - min > 20 ? 1 : 0.125}
            value={shown ?? min}
            onChange={(event) => {
              const n = Number(event.target.value);
              setDragging(n);
              setDraft(show(n));
              setError(null);
            }}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            onKeyUp={endDrag}
            onBlur={endDrag}
            className="min-h-11 flex-1"
          />
        )}
        <input
          id={id}
          className="app-input w-24"
          type="text"
          inputMode={integer ? "numeric" : "decimal"}
          autoComplete="off"
          value={draft}
          placeholder={nullable ? empty : value === null ? "Required" : undefined}
          aria-invalid={error !== null}
          aria-describedby={error ? errorId : undefined}
          onFocus={() => {
            typing.current = true;
          }}
          onChange={(event) => {
            setDraft(event.target.value);
            if (error) setError(null);
          }}
          onBlur={(event) => {
            typing.current = false;
            commit(event.target.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit(draft);
            if (event.key === "Escape") {
              setDraft(show(value));
              setError(null);
            }
          }}
        />
        {inches && <span className="text-sm text-[var(--text-muted)]">in</span>}
      </div>
      <div className="mt-1 flex flex-wrap justify-between gap-2 text-xs text-[var(--text-muted)]">
        <span>{hint}</span>
        {min !== undefined && max !== undefined && (
          <span>
            {min}–{max}
            {inches ? " in" : ""}
            {nullable ? ` · leave empty for ${empty.toLowerCase()}` : ""}
          </span>
        )}
      </div>
      {error && (
        <p id={errorId} role="alert" className="m-0 mt-1 text-sm text-[var(--danger)]">
          {error}
        </p>
      )}
    </div>
  );
}
