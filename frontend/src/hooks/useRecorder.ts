import { useCallback, useRef } from "react";

export interface RecorderControls {
  start: () => Promise<boolean>;
  stop: () => Promise<Blob | null>;
  supported: boolean;
}

/** A small MediaRecorder wrapper. Its consumer decides where the captured audio is sent. */
export function useRecorder(onError: (message: string) => void): RecorderControls {
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<BlobPart[]>([]);

  const cleanup = useCallback(() => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    recorder.current = null;
  }, []);

  const stop = useCallback(() => new Promise<Blob | null>((resolve) => {
    const active = recorder.current;
    if (!active || active.state === "inactive") return resolve(null);
    active.onstop = () => {
      const audio = new Blob(chunks.current, { type: active.mimeType || "audio/webm" });
      cleanup();
      resolve(audio.size ? audio : null);
    };
    active.stop();
  }), [cleanup]);

  const start = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      onError("Voice input is not supported in this browser. Use the typed edit box instead.");
      return false;
    }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks.current = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
      recorder.current = mimeType ? new MediaRecorder(stream.current, { mimeType }) : new MediaRecorder(stream.current);
      recorder.current.ondataavailable = (event) => { if (event.data.size) chunks.current.push(event.data); };
      recorder.current.start();
      return true;
    } catch (error) {
      cleanup();
      const denied = error instanceof DOMException && error.name === "NotAllowedError";
      onError(denied ? "Microphone permission was denied. Use the typed edit box instead." : "We could not start the microphone. Use the typed edit box instead.");
      return false;
    }
  }, [cleanup, onError]);

  return { start, stop, supported: typeof navigator !== "undefined" && typeof MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia) };
}
