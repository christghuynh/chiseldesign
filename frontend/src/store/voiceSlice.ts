// Owner: P2. Push-to-talk / spoken-reply state for the Design screen.
import type { StateCreator } from "zustand";
import type { AppStore } from "./index";

export type VoiceState = "idle" | "recording" | "processing" | "speaking" | "error";

export interface VoiceSlice {
  voiceState: VoiceState;
  lastUtterance: string | null;
  lastReply: string | null;
  setVoiceState: (state: VoiceState) => void;
  setLastUtterance: (text: string | null) => void;
  setLastReply: (text: string | null) => void;
}

export const createVoiceSlice: StateCreator<AppStore, [], [], VoiceSlice> = (set) => ({
  voiceState: "idle",
  lastUtterance: null,
  lastReply: null,
  setVoiceState: (voiceState) => set({ voiceState }),
  setLastUtterance: (lastUtterance) => set({ lastUtterance }),
  setLastReply: (lastReply) => set({ lastReply }),
});
