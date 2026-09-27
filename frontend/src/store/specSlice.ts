// Owner: P2. The current spec/plan and its version history (undo/redo is client-side).
import type { StateCreator } from "zustand";
import type { Plan, Spec, VersionInfo } from "../types";
import type { AppStore } from "./index";

export type VersionSource = VersionInfo["source"];

export interface HistoryEntry {
  spec: Spec;
  plan: Plan | null;
  source: VersionSource;
}

export interface SpecSlice {
  spec: Spec | null;
  plan: Plan | null;
  history: HistoryEntry[];
  /** Index of the current entry in `history`, or -1 when empty. */
  cursor: number;
  /** Set the current spec/plan (a /generate, /edit or fix result) and record it as a new version. */
  applyGenerateResult: (spec: Spec, plan: Plan, source?: VersionSource) => void;
  /** Clear the current generated design before starting a new capture. */
  resetDesign: () => void;
  /** Record the current spec/plan as a new version, dropping any redo tail. */
  pushVersion: (source: VersionSource) => void;
  undo: () => void;
  redo: () => void;
}

export const createSpecSlice: StateCreator<AppStore, [], [], SpecSlice> = (set, get) => ({
  spec: null,
  plan: null,
  history: [],
  cursor: -1,
  applyGenerateResult: (spec, plan, source = "manual") => {
    set({ spec, plan });
    get().pushVersion(source);
  },
  resetDesign: () => set({ spec: null, plan: null, history: [], cursor: -1 }),
  pushVersion: (source) => {
    const { spec, plan, history, cursor } = get();
    if (spec === null) return;
    set({ history: [...history.slice(0, cursor + 1), { spec, plan, source }], cursor: cursor + 1 });
  },
  undo: () => {
    const { history, cursor } = get();
    if (cursor <= 0) return;
    const { spec, plan } = history[cursor - 1];
    set({ cursor: cursor - 1, spec, plan });
  },
  redo: () => {
    const { history, cursor } = get();
    if (cursor >= history.length - 1) return;
    const { spec, plan } = history[cursor + 1];
    set({ cursor: cursor + 1, spec, plan });
  },
});
