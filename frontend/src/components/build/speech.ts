// Owner: P4 (VOX-7b). Browser speech fallback: used when /voice/tts fails or in fixture mode.
import type { Speaker } from "./audioQueue";

/** The parts of window.speechSynthesis the fallback uses (injectable for tests). */
export interface SynthLike {
  speak: (utterance: SpeechSynthesisUtterance) => void;
  cancel: () => void;
}

/**
 * Splits text into sentences. Chrome stops long utterances after about 15 seconds, so each
 * sentence is queued as its own utterance.
 */
export function sentences(text: string): string[] {
  return (text.match(/[^.!?]+[.!?]*/g) ?? []).map((s) => s.trim()).filter(Boolean);
}

export function browserSpeaker(
  synth: SynthLike | undefined = typeof window !== "undefined" ? window.speechSynthesis : undefined,
  makeUtterance: (text: string) => SpeechSynthesisUtterance = (text) => new SpeechSynthesisUtterance(text),
): Speaker | null {
  if (!synth) return null;
  return {
    speak: (text) => {
      synth.cancel();
      for (const sentence of sentences(text)) {
        const u = makeUtterance(sentence);
        u.rate = 0.95;
        synth.speak(u);
      }
    },
    cancel: () => synth.cancel(),
  };
}
