// Owner: P4 (FE-8). Step-by-step build mode: fetches the steps on entry, shows one step at a time
// in large text, highlights the step's parts in 3D, and moves with buttons or the keyboard
// (← back, → next, R repeat) or by voice ("next", "back", "repeat", "stop"). Each step is read
// aloud (TTS prefetched on entry).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { BuildControls } from "../components/build/BuildControls";
import { BuildDone } from "../components/build/BuildDone";
import { BuildProgress } from "../components/build/BuildProgress";
import { BuildStepView } from "../components/build/BuildStepView";
import { type BuildAction, keyToAction, navigate, partIdsForStep } from "../components/build/navigation";
import { matchVoiceCommand, VOICE_HELP } from "../components/build/voiceCommands";
import { PushToTalk } from "../components/PushToTalk";
import { useBuildAudio } from "../hooks/useBuildAudio";
import { useStore } from "../store";
import { Scene } from "../three/Scene";
import type { BuildStep } from "../types";

const NO_STEPS: BuildStep[] = [];

type LoadState = { kind: "loading" } | { kind: "ready" } | { kind: "error"; message: string };

export function BuildMode() {
  const spec = useStore((s) => s.spec);
  const plan = useStore((s) => s.plan);
  const steps = useStore((s) => s.steps);
  const buildStep = useStore((s) => s.buildStep);
  const setSteps = useStore((s) => s.setSteps);
  const setBuildStep = useStore((s) => s.setBuildStep);
  const highlightedPartIds = useStore((s) => s.highlightedPartIds);
  const setHighlighted = useStore((s) => s.setHighlighted);
  const setScreen = useStore((s) => s.setScreen);

  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [done, setDone] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [autoPlay, setAutoPlay] = useState(true);
  const [heard, setHeard] = useState<string | null>(null);

  // On entry (and on Retry): POST /instructions for the current spec.
  useEffect(() => {
    if (!spec) return;
    let cancelled = false;
    setLoad({ kind: "loading" });
    setDone(false);
    api
      .instructions({ spec })
      .then((res) => {
        if (cancelled) return;
        setSteps(res.steps);
        setLoad({ kind: "ready" });
      })
      .catch((e: unknown) => {
        if (!cancelled) setLoad({ kind: "error", message: e instanceof Error ? e.message : "Something went wrong" });
      });
    return () => {
      cancelled = true;
    };
  }, [spec, attempt, setSteps]);

  const total = steps.length;
  const index = Math.min(buildStep, Math.max(total - 1, 0));
  const step = steps[index];
  const ready = load.kind === "ready";
  const audio = useBuildAudio(ready ? steps : NO_STEPS, ready && !done ? step : undefined, autoPlay);

  // Highlight the current step's parts; clear the highlight when leaving build mode.
  const stepPartIds = useMemo(
    () => (done ? [] : partIdsForStep(step, spec?.parts ?? [])),
    [done, step, spec],
  );
  useEffect(() => setHighlighted(stepPartIds), [stepPartIds, setHighlighted]);
  useEffect(() => () => setHighlighted([]), [setHighlighted]);

  // Latest position, so the keyboard and voice handlers never act on a stale step.
  const posRef = useRef({ index, done, total });
  posRef.current = { index, done, total };

  const onAction = useCallback(
    (action: BuildAction) => {
      const { index, done, total } = posRef.current;
      const next = navigate({ index, done }, action, total);
      if (next.index !== index) setBuildStep(next.index);
      if (next.done !== done) setDone(next.done);
      if (action === "repeat" && !done) audio.repeat();
      if (action === "stop") audio.stop();
    },
    [setBuildStep, audio],
  );

  const onTranscript = useCallback(
    (text: string) => {
      const action = matchVoiceCommand(text);
      setHeard(text);
      if (action) onAction(action);
      else audio.say(VOICE_HELP);
    },
    [onAction, audio],
  );

  useEffect(() => {
    if (load.kind !== "ready") return;
    const onKey = (e: KeyboardEvent) => {
      const action = keyToAction(e);
      if (!action) return;
      e.preventDefault();
      onAction(action);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [load.kind, onAction]);

  if (!spec) {
    return (
      <section aria-labelledby="build-title" className="space-y-4">
        <h2 id="build-title" className="text-2xl font-semibold">
          Build mode
        </h2>
        <p className="text-lg">There is no design yet. Create one first, then come back to build it step by step.</p>
        <button
          type="button"
          onClick={() => setScreen("capture")}
          className="min-h-11 rounded bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
        >
          Start a design
        </button>
      </section>
    );
  }

  return (
    <section aria-labelledby="build-title" className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="build-title" className="text-2xl font-semibold">
          Build mode
        </h2>
        <button
          type="button"
          onClick={() => setScreen("plan")}
          className="min-h-11 rounded border border-slate-400 px-4 py-2 hover:bg-slate-100"
        >
          ← Back to the plan
        </button>
      </div>

      {load.kind === "loading" && (
        <p role="status" className="text-lg">
          Writing your build steps…
        </p>
      )}

      {load.kind === "error" && (
        <div role="alert" className="space-y-3">
          <p className="text-lg">Could not load the build steps: {load.message}</p>
          <button
            type="button"
            onClick={() => setAttempt((n) => n + 1)}
            className="min-h-11 rounded bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
          >
            Try again
          </button>
        </div>
      )}

      {load.kind === "ready" && total === 0 && <p className="text-lg">This design has no build steps.</p>}

      {load.kind === "ready" && step && (
        <>
          <BuildProgress completed={done ? total : index} total={total} />
          <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div className="space-y-6" aria-live="polite">
              {done ? (
                <BuildDone
                  total={total}
                  onBack={() => onAction("back")}
                  onRestart={() => {
                    setBuildStep(0);
                    setDone(false);
                  }}
                  onPlan={() => setScreen("plan")}
                />
              ) : (
                <BuildStepView step={step} index={index} total={total} cutList={plan?.cut_list} />
              )}
            </div>
            <div className="overflow-hidden rounded border border-slate-300">
              <Scene parts={spec.parts} highlightedIds={highlightedPartIds} height="22rem" />
            </div>
          </div>
          {!done && (
            <BuildControls
              onAction={onAction}
              canGoBack={index > 0}
              nextLabel={index === total - 1 ? "Finish" : "Next"}
            />
          )}
          <div className="flex flex-wrap items-center gap-4">
            <PushToTalk onTranscript={onTranscript} label="Hold to talk (say next, back or repeat)" />
            <p role="status" aria-live="polite" className="text-lg text-slate-700">
              {heard !== null &&
                (matchVoiceCommand(heard) ? `Heard: “${heard}”` : `Heard “${heard}”. ${VOICE_HELP}`)}
            </p>
          </div>
          <label className="flex min-h-11 items-center gap-3 text-lg">
            <input
              type="checkbox"
              checked={autoPlay}
              onChange={(e) => setAutoPlay(e.target.checked)}
              className="size-5"
            />
            Read each step aloud
          </label>
        </>
      )}
    </section>
  );
}
