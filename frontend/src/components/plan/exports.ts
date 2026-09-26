// Owner: P4. Plan downloads (FE-10): STEP, STL and cut-list CSV from POST /api/export/*.
// Kept here rather than in api/client.ts (P2's file) so the lanes don't collide; it reuses the client's
// fixture switch and error type. In fixture mode the CSV is built locally from the plan's cut list and
// the 3D formats are unavailable (there is no CAD kernel without the backend).
import { ApiError, USE_FIXTURES } from "../../api/client";
import type { Plan, Spec } from "../../types";

export type ExportKind = "step" | "stl" | "csv";

const ROUTES: Record<ExportKind, string> = {
  step: "/api/export/step",
  stl: "/api/export/stl",
  csv: "/api/export/cutlist.csv",
};

const EXTENSIONS: Record<ExportKind, string> = { step: "step", stl: "stl", csv: "csv" };

/** Formats that work without the backend. */
export const FIXTURE_EXPORTS: ReadonlySet<ExportKind> = new Set(["csv"]);

export interface ExportedFile {
  blob: Blob;
  filename: string;
}

/** `sketchbuild-ramp-switchback.step`, or `sketchbuild-ramp-cut-list.csv` for the CSV. */
export function exportFilename(spec: Spec, kind: ExportKind): string {
  const layout = spec.params.layout?.value;
  const parts = ["sketchbuild", spec.template, typeof layout === "string" && layout !== "auto" ? layout : null, kind === "csv" ? "cut-list" : null];
  return `${parts.filter(Boolean).join("-").replace(/[^a-z0-9-]+/gi, "_").toLowerCase()}.${EXTENSIONS[kind]}`;
}

function csvCell(value: string | number): string {
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** The cut list as CSV, one row per label (the fixture-mode fallback for /export/cutlist.csv). */
export function cutListCsv(plan: Plan): string {
  const header = ["label", "name", "material", "actual_dims_in", "length_in", "length", "qty", "part_ids", "cut_notes"];
  const rows = plan.cut_list.map((r) => [
    r.label,
    r.name,
    r.material,
    r.actual_dims,
    r.length_in,
    r.length_display,
    r.qty,
    r.part_ids.join(" "),
    r.cut_notes.join("; "),
  ]);
  return [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

function filenameFromHeader(header: string | null): string | null {
  const match = header?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function fetchExport(kind: ExportKind, spec: Spec, plan: Plan, useFixtures = USE_FIXTURES): Promise<ExportedFile> {
  const filename = exportFilename(spec, kind);
  if (useFixtures) {
    if (kind !== "csv") throw new ApiError(0, "FIXTURE_MODE", "3D downloads need the backend; they are off in fixture mode.");
    return { blob: new Blob([cutListCsv(plan)], { type: "text/csv" }), filename };
  }
  const res = await fetch(ROUTES[kind], {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spec }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.error?.code ?? `HTTP_${res.status}`, body?.error?.message ?? res.statusText);
  }
  return { blob: await res.blob(), filename: filenameFromHeader(res.headers.get("Content-Disposition")) ?? filename };
}

/** Hand a blob to the browser as a download. */
export function saveBlob({ blob, filename }: ExportedFile): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
