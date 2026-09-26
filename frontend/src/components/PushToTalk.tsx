// Owner: P2 (P4 reuses it in Build mode). PushToTalkProps is a contract: changing it must be announced.
export interface PushToTalkProps {
  /** Called with the speech-to-text result. */
  onTranscript: (text: string) => void;
  disabled?: boolean;
  /** Button label (default "Hold to talk"). */
  label?: string;
  /** Key held to talk (default a space); null disables the hotkey. */
  hotkey?: string | null;
}

// STUB: renders a disabled button and never calls onTranscript. The real component (hold to record
// with MediaRecorder, /voice/stt, the listening state, the 10 s cap and the hotkey) is task VOX-3.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useRecorder } from "../hooks/useRecorder";
import { useStore } from "../store";

export function PushToTalk({ onTranscript, disabled = false, label = "Hold to talk", hotkey = " " }: PushToTalkProps) {
  const [error, setError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const recording = useRef(false);
  const capTimer = useRef<number | null>(null);
  const setVoiceState = useStore((s) => s.setVoiceState);
  const setLastUtterance = useStore((s) => s.setLastUtterance);
  const recorder = useRecorder((message) => { setError(message); setVoiceState("error"); });

  const finish = useCallback(async () => {
    if (!recording.current) return;
    recording.current = false;
    setIsRecording(false);
    if (capTimer.current !== null) window.clearTimeout(capTimer.current);
    capTimer.current = null;
    const audio = await recorder.stop();
    if (!audio) { setVoiceState("idle"); return; }
    setVoiceState("processing");
    try {
      const transcript = await api.stt(audio);
      setLastUtterance(transcript);
      onTranscript(transcript);
      setVoiceState("idle");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Speech recognition failed. Try again or type your edit.");
      setVoiceState("error");
    }
  }, [onTranscript, recorder, setLastUtterance, setVoiceState]);

  const begin = useCallback(async () => {
    if (disabled || recording.current) return;
    setError(null);
    const started = await recorder.start();
    if (started) { recording.current = true; setIsRecording(true); setVoiceState("recording"); capTimer.current = window.setTimeout(() => void finish(), 10_000); }
  }, [disabled, finish, recorder, setVoiceState]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (hotkey === null || event.key !== hotkey || event.repeat) return;
      const element = document.activeElement;
      if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || (element instanceof HTMLElement && element.isContentEditable)) return;
      event.preventDefault();
      void begin();
    };
    const up = (event: KeyboardEvent) => { if (hotkey !== null && event.key === hotkey) { event.preventDefault(); void finish(); } };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, [begin, finish, hotkey]);

  return (
    <div>
      <button type="button" disabled={disabled} aria-pressed={isRecording} onPointerDown={() => void begin()} onPointerUp={() => void finish()} onPointerLeave={() => void finish()} className="app-button app-button--secondary">
        {isRecording ? "Listening… release to send" : label}
      </button>
      {error && <p className="mt-1 text-sm text-[var(--danger)]" role="alert">{error}</p>}
    </div>
  );
}
