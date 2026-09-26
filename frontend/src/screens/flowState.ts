import type { ParseResponse, Spec } from "../types";

export interface CaptureSession { parse: ParseResponse; imageUrl: string | null; }
let session: CaptureSession | null = null;
export const setCaptureSession = (next: CaptureSession) => { session = next; };
export const getCaptureSession = () => session;
export const ungeneratedSpec = (spec: Spec): Spec => ({ ...spec, parts: [], rule_checks: [] });
