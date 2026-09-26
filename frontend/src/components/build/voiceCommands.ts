// Owner: P4 (VOX-5). Build-mode voice commands, matched locally: no API call beyond STT.
import type { BuildAction } from "./navigation";

/** Spoken when a phrase matches no command. */
export const VOICE_HELP = "Say next, back, or repeat.";

const KEYWORDS: Record<string, BuildAction> = {
  next: "next",
  forward: "next",
  continue: "next",
  back: "back",
  previous: "back",
  repeat: "repeat",
  again: "repeat",
  stop: "stop",
  pause: "stop",
  quiet: "stop",
};

/**
 * Finds the command in a transcript ("Next.", "go back", "can you repeat that"). When a phrase
 * contains several keywords the first one wins; no keyword returns null.
 */
export function matchVoiceCommand(transcript: string): BuildAction | null {
  const words = transcript.toLowerCase().match(/[a-z]+/g) ?? [];
  for (const word of words) {
    const action = KEYWORDS[word];
    if (action) return action;
  }
  return null;
}
