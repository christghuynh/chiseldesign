import { describe, expect, it } from "vitest";
import { browserSpeaker, sentences, type SynthLike } from "./speech";

function fakeSynth() {
  const log: string[] = [];
  const synth: SynthLike = {
    speak: (u) => void log.push(`speak:${u.text}`),
    cancel: () => void log.push("cancel"),
  };
  const make = (text: string) => ({ text, rate: 1 }) as SpeechSynthesisUtterance;
  return { synth, make, log };
}

describe("sentences", () => {
  it("splits on sentence punctuation and keeps it", () => {
    expect(sentences("Cut the stringers. Wear eye protection! Ready?")).toEqual([
      "Cut the stringers.",
      "Wear eye protection!",
      "Ready?",
    ]);
  });

  it("keeps text without punctuation and drops empty pieces", () => {
    expect(sentences("two-by-six, ninety inches")).toEqual(["two-by-six, ninety inches"]);
    expect(sentences("  ")).toEqual([]);
  });
});

describe("browserSpeaker", () => {
  it("returns null when the browser has no speech synthesis", () => {
    expect(browserSpeaker(undefined)).toBeNull();
  });

  it("cancels what is speaking, then queues one utterance per sentence", () => {
    const { synth, make, log } = fakeSynth();
    browserSpeaker(synth, make)!.speak("Step one. Say next, back, or repeat.");
    expect(log).toEqual(["cancel", "speak:Step one.", "speak:Say next, back, or repeat."]);
  });

  it("cancel stops speech", () => {
    const { synth, make, log } = fakeSynth();
    browserSpeaker(synth, make)!.cancel();
    expect(log).toEqual(["cancel"]);
  });
});
