import type { ParamValue, ParseResponse, Spec, TemplateInfo } from "../types";

export interface CaptureSession { parse: ParseResponse; imageUrl: string | null; }
let session: CaptureSession | null = null;
export const setCaptureSession = (next: CaptureSession) => { session = next; };
export const getCaptureSession = () => session;
export const ungeneratedSpec = (spec: Spec): Spec => ({ ...spec, parts: [], rule_checks: [] });

/**
 * A spec (params only, no parts yet) built from the template's own defaults (GET /api/templates),
 * with `values` on top as user-entered params. /generate rejects missing required params
 * (e.g. the ramp's total_rise_in), so callers must not rely on it to fill defaults.
 * Null defaults (e.g. "no length limit") are left out.
 */
export function specFromDefaults(
  template: TemplateInfo,
  values: Record<string, number | string | boolean | undefined> = {},
  meta: Record<string, unknown> = {},
): Spec {
  const params: Record<string, ParamValue> = {};
  for (const [name, value] of Object.entries(template.defaults)) {
    if (typeof value === "number" || typeof value === "string" || typeof value === "boolean") {
      params[name] = { value, source: "default", confidence: null };
    }
  }
  for (const [name, value] of Object.entries(values)) {
    if (value !== undefined) params[name] = { value, source: "user", confidence: null };
  }
  const assumed = Object.keys(params).filter((name) => params[name].source === "default");
  return { schema_version: "1.0", template: template.key, params, assumed, parts: [], rule_checks: [], meta };
}

/** Params that are required by the template's schema but have no value yet. */
export function missingRequired(template: TemplateInfo, spec: Spec): string[] {
  const required = (template.params_schema.required as string[] | undefined) ?? [];
  return required.filter((name) => !(name in spec.params));
}

/**
 * The Capture form's measurement fields are generic ("Total rise", "Desired width", "Available
 * length") but templates name them differently (the ramp's `clear_width_in` is `width_in` on the
 * garden bed, workbench and step platform). Maps each typed value to the first matching param the
 * template has; values with no equivalent are left out.
 */
export const MEASUREMENT_EQUIVALENTS: Record<string, string[]> = {
  total_rise_in: ["total_rise_in"],
  clear_width_in: ["clear_width_in", "width_in"],
  available_length_in: ["available_length_in"],
};

export function measurementValues(template: TemplateInfo, typed: Record<string, number | undefined>): Record<string, number> {
  const known = (template.params_schema.properties ?? {}) as Record<string, unknown>;
  const out: Record<string, number> = {};
  for (const [field, value] of Object.entries(typed)) {
    if (value === undefined || Number.isNaN(value)) continue;
    const target = (MEASUREMENT_EQUIVALENTS[field] ?? [field]).find((name) => name in known);
    if (target) out[target] = value;
  }
  return out;
}

/** The template's numeric presets with their display titles, e.g. ["Length (in)", 72]. */
/**
 * The template's numeric presets as [title, "72 in"] for a preview. When the template marks its key
 * dimensions (`group: "key"`), only those are listed; advanced settings stay out of the preview.
 */
export function presetDimensions(template: TemplateInfo): [string, string][] {
  const props = (template.params_schema.properties ?? {}) as Record<string, { title?: string; unit?: string; group?: string }>;
  const grouped = Object.values(props).some((prop) => prop.group);
  return Object.entries(template.defaults)
    .filter((entry): entry is [string, number] => typeof entry[1] === "number")
    .filter(([name]) => !grouped || props[name]?.group === "key")
    .map(([name, value]) => [props[name]?.title ?? name.replaceAll("_", " "), props[name]?.unit ? `${value} ${props[name].unit}` : String(value)]);
}
