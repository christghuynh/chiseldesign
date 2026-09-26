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
