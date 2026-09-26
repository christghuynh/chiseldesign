// Owner: P4 (VOX-6). Build-mode audio: prefetches TTS for every step in the background, plays the
// current step, and stops whatever is playing when the builder moves on. No React and no browser
// globals here: the hook passes in the real fetch/Audio implementations, the tests pass fakes.
import { ApiError } from "../../api/client";
import type { BuildStep } from "../../types";

/** Plays one audio URL at a time. `play` resolves once playback has started. */
export interface AudioPlayer {
  play: (url: string) => Promise<void>;
  stop: () => void;
}

/** Speaks text without the server (the browser speech fallback). */
export interface Speaker {
  speak: (text: string) => void;
  cancel: () => void;
}

export interface BuildAudioDeps {
  fetchTts: (text: string) => Promise<Blob>;
  createUrl: (blob: Blob) => string;
  revokeUrl: (url: string) => void;
  player: AudioPlayer;
  /** Used when TTS is off or failed for a step. Null when the browser has no speech synthesis. */
  speaker?: Speaker | null;
  /** False skips the server entirely (fixture mode) and always uses the speaker. */
  useTts?: boolean;
  /** How long `play` waits for a step's audio that is still being fetched before falling back. */
  waitMs?: number;
  /** Parallel TTS requests during prefetch. */
  concurrency?: number;
}

/** What is read aloud for a step: title, instruction, then each cut callout. */
export function spokenText(step: BuildStep): string {
  const parts = [step.title, step.text, ...step.cut_callouts.map((c) => c.spoken)];
  return parts
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => (/[.!?]$/.test(p) ? p : `${p}.`))
    .join(" ");
}

/** Errors that mean TTS is not available at all, so the remaining requests are skipped. */
function ttsUnavailable(e: unknown): boolean {
  if (e instanceof ApiError) return e.status === 404 || e.status === 501 || e.status === 503;
  return true; // network error: the backend is down or unreachable
}

const withTimeout = <T>(p: Promise<T>, ms: number, fallback: T): Promise<T> =>
  new Promise((resolve) => {
    const timer = setTimeout(() => resolve(fallback), ms);
    p.then((v) => {
      clearTimeout(timer);
      resolve(v);
    });
  });

export class BuildAudio {
  private readonly urls = new Map<number, string>();
  private readonly pending = new Map<number, Promise<string | null>>();
  /** Bumped by every play/stop, so a play that is still waiting knows it was superseded. */
  private playToken = 0;
  /** Bumped by reset, so an old prefetch drops its results. */
  private generation = 0;
  private ttsDisabled: boolean;

  constructor(private readonly deps: BuildAudioDeps) {
    this.ttsDisabled = deps.useTts === false;
  }

  /** True once TTS is known not to work (fixture mode, 501, backend down). */
  get usingFallback(): boolean {
    return this.ttsDisabled;
  }

  urlFor(n: number): string | undefined {
    return this.urls.get(n);
  }

  /** Requests TTS for every step, in order, a few at a time. Resolves when all have settled. */
  async prefetch(steps: BuildStep[], onUrl?: (n: number, url: string) => void): Promise<void> {
    const gen = this.generation;
    if (this.ttsDisabled) return;
    const resolvers = new Map<number, (url: string | null) => void>();
    const promises = new Map<number, Promise<string | null>>();
    for (const step of steps) {
      if (this.urls.has(step.n) || this.pending.has(step.n)) continue;
      const p = new Promise<string | null>((resolve) => resolvers.set(step.n, resolve));
      promises.set(step.n, p);
      this.pending.set(step.n, p);
    }
    const queue = steps.filter((s) => resolvers.has(s.n));

    const settle = (n: number, url: string | null) => {
      // After a reset the map may already hold a newer prefetch's entry for this step.
      if (this.pending.get(n) === promises.get(n)) this.pending.delete(n);
      resolvers.get(n)!(url);
    };
    const worker = async () => {
      for (let step = queue.shift(); step; step = queue.shift()) {
        if (gen !== this.generation || this.ttsDisabled) {
          settle(step.n, null);
          continue;
        }
        try {
          const blob = await this.deps.fetchTts(spokenText(step));
          if (gen !== this.generation) {
            settle(step.n, null);
            continue;
          }
          const url = this.deps.createUrl(blob);
          this.urls.set(step.n, url);
          onUrl?.(step.n, url);
          settle(step.n, url);
        } catch (e) {
          if (ttsUnavailable(e)) this.ttsDisabled = true;
          settle(step.n, null);
        }
      }
    };
    const workers = Math.max(1, Math.min(this.deps.concurrency ?? 2, queue.length));
    await Promise.all(Array.from({ length: workers }, worker));
  }

  /** Stops anything playing, then plays the step: its prefetched audio, or the speech fallback. */
  async play(step: BuildStep): Promise<void> {
    this.stop();
    const token = this.playToken;
    let url: string | null | undefined = this.urls.get(step.n);
    const inFlight = this.pending.get(step.n);
    if (!url && inFlight) url = await withTimeout(inFlight, this.deps.waitMs ?? 6000, null);
    if (token !== this.playToken) return; // the builder moved on while we waited
    if (url) {
      try {
        await this.deps.player.play(url);
        return;
      } catch {
        if (token !== this.playToken) return;
      }
    }
    this.speakFallback(spokenText(step));
  }

  /** Speaks a short prompt that is not a step (e.g. "Say next, back, or repeat."). */
  say(text: string): void {
    this.stop();
    this.speakFallback(text);
  }

  stop(): void {
    this.playToken++;
    this.deps.player.stop();
    this.deps.speaker?.cancel();
  }

  /** Stops playback, drops any in-flight prefetch and frees the audio URLs. Reusable afterwards. */
  reset(): void {
    this.stop();
    this.generation++;
    for (const url of this.urls.values()) this.deps.revokeUrl(url);
    this.urls.clear();
    this.pending.clear();
  }

  private speakFallback(text: string): void {
    this.deps.speaker?.speak(text);
  }
}
