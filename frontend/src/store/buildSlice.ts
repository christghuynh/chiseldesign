// Owner: P4. Build-mode instructions and progress.
import type { StateCreator } from "zustand";
import type { BuildStep } from "../types";
import type { AppStore } from "./index";

export interface BuildSlice {
  steps: BuildStep[];
  /** Index into `steps` of the step being shown. */
  buildStep: number;
  /** Prefetched TTS audio URL per step, keyed by `BuildStep.n`. */
  audioUrls: Record<number, string>;
  setSteps: (steps: BuildStep[]) => void;
  setBuildStep: (index: number) => void;
  setAudioUrls: (urls: Record<number, string>) => void;
}

export const createBuildSlice: StateCreator<AppStore, [], [], BuildSlice> = (set) => ({
  steps: [],
  buildStep: 0,
  audioUrls: {},
  setSteps: (steps) => set({ steps, buildStep: 0 }),
  setBuildStep: (buildStep) => set({ buildStep }),
  setAudioUrls: (audioUrls) => set({ audioUrls }),
});
