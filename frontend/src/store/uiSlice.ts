// Owner: P2. Which screen is showing, and which parts are selected or highlighted in the 3D view.
import type { StateCreator } from "zustand";
import type { AppStore } from "./index";

export type ScreenKey = "landing" | "capture" | "confirm" | "design" | "plan" | "build" | "projects" | "overlay";

/** The main flow, in order. Landing, Projects and Overlay sit outside it. */
export const FLOW: ScreenKey[] = ["capture", "confirm", "design", "plan", "build"];

export interface UiSlice {
  screen: ScreenKey;
  setScreen: (screen: ScreenKey) => void;
  selectedPartIds: string[];
  highlightedPartIds: string[];
  setSelected: (ids: string[]) => void;
  setHighlighted: (ids: string[]) => void;
}

export const createUiSlice: StateCreator<AppStore, [], [], UiSlice> = (set) => ({
  screen: "landing",
  setScreen: (screen) => set({ screen }),
  selectedPartIds: [],
  highlightedPartIds: [],
  setSelected: (selectedPartIds) => set({ selectedPartIds }),
  setHighlighted: (highlightedPartIds) => set({ highlightedPartIds }),
});
