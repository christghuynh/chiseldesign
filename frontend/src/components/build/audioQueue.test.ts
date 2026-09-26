import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { BuildStep, InstructionsResponse } from "../../types";
import { BuildAudio, type BuildAudioDeps, spokenText } from "./audioQueue";

const { steps } = JSON.parse(
  readFileSync(resolve(import.meta.dirname, "../../../../fixtures/instructions/ramp_switchback.json"), "utf8"),
) as InstructionsResponse;

const tick = () => new Promise((r) => setTimeout(r, 0));

/** Fake TTS server: each request waits until released (or resolves at once when `instant`). */
function fakes(opts: { instant?: boolean; fail?: (text: string) => unknown } = {}) {
  const requests: { text: string; release: () => void; reject: (e: unknown) => void }[] = [];
  const played: string[] = [];
  const spoken: string[] = [];
  const revoked: string[] = [];
  let urlCount = 0;
  const deps: BuildAudioDeps = {
    fetchTts: (text) =>
      new Promise<Blob>((res, rej) => {
        const failure = opts.fail?.(text);
        if (failure) return rej(failure);
        const blob = new Blob([text]);
        requests.push({ text, release: () => res(blob), reject: rej });
        if (opts.instant) res(blob);
      }),
    createUrl: () => `blob:${++urlCount}`,
    revokeUrl: (url) => revoked.push(url),
    player: { play: vi.fn(async (url: string) => void played.push(url)), stop: vi.fn() },
    speaker: { speak: vi.fn((text: string) => void spoken.push(text)), cancel: vi.fn() },
    waitMs: 50,
  };
  return { deps, requests, played, spoken, revoked };
}

describe("spokenText", () => {
  it("reads the title, the text and each callout's spoken form", () => {
    const step = steps.find((s) => s.cut_callouts.length > 1)!;
    const text = spokenText(step);
    expect(text.startsWith(step.title)).toBe(true);
    expect(text).toContain(step.text);
    for (const c of step.cut_callouts) expect(text).toContain(c.spoken);
    expect(text).toMatch(/\.$/);
  });

  it("ends each piece with punctuation so TTS pauses between them", () => {
    const step: BuildStep = {
      n: 1,
      title: "Cut the stringers",
      text: "Cut both.",
      part_labels: ["C"],
      cut_callouts: [{ label: "C", spoken: "two-by-six, ninety inches" }],
      safety_tip: null,
    };
    expect(spokenText(step)).toBe("Cut the stringers. Cut both. two-by-six, ninety inches.");
  });
});

describe("BuildAudio prefetch", () => {
  it("requests TTS for every step and reports each URL by step number", async () => {
    const f = fakes({ instant: true });
    const audio = new BuildAudio(f.deps);
    const got: Record<number, string> = {};
    await audio.prefetch(steps, (n, url) => (got[n] = url));
    expect(f.requests.map((r) => r.text)).toEqual(steps.map(spokenText));
    expect(Object.keys(got).map(Number)).toEqual(steps.map((s) => s.n));
    expect(audio.urlFor(steps[0].n)).toBe(got[steps[0].n]);
  });

  it("keeps at most `concurrency` requests in flight, in step order", async () => {
    const f = fakes();
    const audio = new BuildAudio({ ...f.deps, concurrency: 2 });
    const done = audio.prefetch(steps);
    await tick();
    expect(f.requests.map((r) => r.text)).toEqual([spokenText(steps[0]), spokenText(steps[1])]);
    f.requests[0].release();
    await tick();
    expect(f.requests).toHaveLength(3);
    expect(f.requests[2].text).toBe(spokenText(steps[2]));
    for (let i = 0; i < steps.length; i++) {
      f.requests.forEach((r) => r.release());
      await tick();
    }
    await done;
    expect(f.requests.map((r) => r.text)).toEqual(steps.map(spokenText));
  });

  it("does not request steps it already has", async () => {
    const f = fakes({ instant: true });
    const audio = new BuildAudio(f.deps);
    await audio.prefetch(steps);
    await audio.prefetch(steps);
    expect(f.requests).toHaveLength(steps.length);
  });

  it("stops requesting once the server says TTS is not implemented", async () => {
    const f = fakes({ fail: () => new ApiError(501, "NOT_IMPLEMENTED", "VOX-2") });
    const fetchTts = vi.fn(f.deps.fetchTts);
    const audio = new BuildAudio({ ...f.deps, fetchTts, concurrency: 1 });
    await audio.prefetch(steps);
    expect(fetchTts).toHaveBeenCalledTimes(1);
    expect(audio.usingFallback).toBe(true);
  });

  it("keeps going after a one-off server error", async () => {
    const bad = spokenText(steps[1]);
    const f = fakes({ instant: true, fail: (t) => (t === bad ? new ApiError(500, "HTTP_500", "boom") : null) });
    const audio = new BuildAudio(f.deps);
    await audio.prefetch(steps);
    expect(audio.usingFallback).toBe(false);
    expect(audio.urlFor(steps[1].n)).toBeUndefined();
    expect(audio.urlFor(steps[2].n)).toBeDefined();
  });

  it("reset revokes the URLs and drops results that arrive afterwards", async () => {
    const f = fakes();
    const audio = new BuildAudio({ ...f.deps, concurrency: 1 });
    const done = audio.prefetch(steps.slice(0, 2));
    await tick();
    f.requests[0].release();
    await tick();
    const first = audio.urlFor(steps[0].n)!;
    audio.reset();
    expect(f.revoked).toEqual([first]);
    await tick();
    f.requests.forEach((r) => r.release());
    await done;
    expect(audio.urlFor(steps[0].n)).toBeUndefined();
    expect(audio.urlFor(steps[1].n)).toBeUndefined();
  });
});

describe("BuildAudio playback", () => {
  it("plays a prefetched step's audio", async () => {
    const f = fakes({ instant: true });
    const audio = new BuildAudio(f.deps);
    await audio.prefetch(steps);
    await audio.play(steps[3]);
    expect(f.played).toEqual([audio.urlFor(steps[3].n)]);
    expect(f.spoken).toEqual([]);
  });

  it("waits for a step whose audio is still being fetched", async () => {
    const f = fakes();
    const audio = new BuildAudio(f.deps);
    void audio.prefetch(steps.slice(0, 1));
    const playing = audio.play(steps[0]);
    await tick();
    f.requests[0].release();
    await playing;
    expect(f.played).toEqual(["blob:1"]);
  });

  it("navigation stops the current audio, and a superseded play never starts", async () => {
    const f = fakes();
    const audio = new BuildAudio(f.deps);
    void audio.prefetch(steps.slice(0, 2));
    const first = audio.play(steps[0]); // still waiting for its audio
    await tick();
    const stopsBefore = vi.mocked(f.deps.player.stop).mock.calls.length;
    const second = audio.play(steps[1]); // the builder pressed Next
    expect(vi.mocked(f.deps.player.stop).mock.calls.length).toBe(stopsBefore + 1);
    f.requests.forEach((r) => r.release());
    await Promise.all([first, second]);
    expect(f.played).toEqual(["blob:2"]);
  });

  it("stop cancels a play that is waiting", async () => {
    const f = fakes();
    const audio = new BuildAudio(f.deps);
    void audio.prefetch(steps.slice(0, 1));
    const playing = audio.play(steps[0]);
    audio.stop();
    await tick();
    f.requests[0].release();
    await playing;
    expect(f.played).toEqual([]);
    expect(f.spoken).toEqual([]);
  });

  it("repeat (playing the same step again) replays it", async () => {
    const f = fakes({ instant: true });
    const audio = new BuildAudio(f.deps);
    await audio.prefetch(steps);
    await audio.play(steps[0]);
    await audio.play(steps[0]);
    expect(f.played).toEqual(["blob:1", "blob:1"]);
  });
});
