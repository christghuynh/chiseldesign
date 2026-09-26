// Owner: P4 (VOX-6). Connects BuildAudio to the browser and the store: prefetches every step's TTS
// when the steps load (object URLs go to buildSlice.audioUrls), auto-plays the current step, and
// stops the audio on navigation and when leaving build mode. When TTS fails, or in fixture mode,
// the browser's speechSynthesis reads the step instead (VOX-7b).
import { useEffect, useMemo, useRef } from "react";
import { ApiError, USE_FIXTURES } from "../api/client";
import { type AudioPlayer, BuildAudio, type Speaker } from "../components/build/audioQueue";
import { browserSpeaker } from "../components/build/speech";
import { useStore } from "../store";
import type { BuildStep, TtsRequest } from "../types";

// POST /voice/tts -> audio/mpeg. Kept here rather than in api/client.ts (P2's file) until the
// client grows a binary helper; see reports/p4-build.md.
export async function fetchTts(text: string): Promise<Blob> {
  const body: TtsRequest = { text };
  const res = await fetch("/api/voice/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new ApiError(res.status, err?.error?.code ?? `HTTP_${res.status}`, err?.error?.message ?? res.statusText);
  }
  return res.blob();
}

function htmlAudioPlayer(): AudioPlayer {
  const el = typeof Audio === "undefined" ? null : new Audio();
  return {
    play: (url) => {
      if (!el) return Promise.reject(new Error("No audio element"));
      el.src = url;
      return el.play();
    },
    stop: () => {
      if (!el) return;
      el.pause();
      el.removeAttribute("src");
    },
  };
}

export interface BuildAudioOptions {
  /** Defaults to the browser's speechSynthesis (null when the browser has none). */
  speaker?: Speaker | null;
  /** Defaults to false in fixture mode, where there is no backend to ask. */
  useTts?: boolean;
}

export interface BuildAudioControls {
  /** Replays the current step from the start. */
  repeat: () => void;
  stop: () => void;
  say: (text: string) => void;
}

/**
 * @param step the step being shown, or undefined on the Done screen / while loading.
 * @param autoPlay play each step when it is shown.
 */
export function useBuildAudio(
  steps: BuildStep[],
  step: BuildStep | undefined,
  autoPlay: boolean,
  options: BuildAudioOptions = {},
): BuildAudioControls {
  const setAudioUrls = useStore((s) => s.setAudioUrls);
  const audioRef = useRef<BuildAudio | null>(null);
  if (!audioRef.current) {
    audioRef.current = new BuildAudio({
      fetchTts,
      createUrl: (blob) => URL.createObjectURL(blob),
      revokeUrl: (url) => URL.revokeObjectURL(url),
      player: htmlAudioPlayer(),
      speaker: options.speaker !== undefined ? options.speaker : browserSpeaker(),
      useTts: options.useTts ?? !USE_FIXTURES,
    });
  }
  const audio = audioRef.current;

  // New steps: drop the old audio and prefetch the new set in the background.
  useEffect(() => {
    audio.reset();
    setAudioUrls({});
    if (steps.length === 0) return;
    void audio.prefetch(steps, (n, url) => setAudioUrls({ ...useStore.getState().audioUrls, [n]: url }));
    return () => {
      audio.reset();
      setAudioUrls({});
    };
  }, [audio, steps, setAudioUrls]);

  // Showing a step plays it; moving away stops it.
  useEffect(() => {
    if (step && autoPlay) void audio.play(step);
    else audio.stop();
    return () => audio.stop();
  }, [audio, step, autoPlay]);

  const stepRef = useRef(step);
  stepRef.current = step;
  return useMemo(
    () => ({
      repeat: () => {
        if (stepRef.current) void audio.play(stepRef.current);
      },
      stop: () => audio.stop(),
      say: (text: string) => audio.say(text),
    }),
    [audio],
  );
}
