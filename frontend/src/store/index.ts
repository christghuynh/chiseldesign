// Combines the slices into one store. Created in the foundation and not edited afterwards:
// each person edits only their own slice file (see the owner comment at the top of each).
import { create } from "zustand";
import { type AuthSlice, createAuthSlice } from "./authSlice";
import { type BuildSlice, createBuildSlice } from "./buildSlice";
import { createSpecSlice, type SpecSlice } from "./specSlice";
import { createUiSlice, type UiSlice } from "./uiSlice";
import { createVoiceSlice, type VoiceSlice } from "./voiceSlice";

export type AppStore = SpecSlice & UiSlice & VoiceSlice & BuildSlice & AuthSlice;

export const useStore = create<AppStore>()((...a) => ({
  ...createSpecSlice(...a),
  ...createUiSlice(...a),
  ...createVoiceSlice(...a),
  ...createBuildSlice(...a),
  ...createAuthSlice(...a),
}));

export { FLOW } from "./uiSlice";
export type { AuthUser } from "./authSlice";
export type { HistoryEntry, VersionSource } from "./specSlice";
export type { ScreenKey } from "./uiSlice";
export type { VoiceState } from "./voiceSlice";
