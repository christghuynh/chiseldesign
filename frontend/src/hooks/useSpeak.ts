import { useCallback, useEffect, useRef } from "react";
import { api } from "../api/client";

/** One speech channel: a new reply always interrupts the prior one. */
export function useSpeak() {
  const audio = useRef<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    audio.current?.pause();
    audio.current = null;
    window.speechSynthesis?.cancel();
  }, []);

  const speak = useCallback(async (text: string) => {
    stop();
    try {
      const blob = await api.tts(text);
      const url = URL.createObjectURL(blob);
      const player = new Audio(url);
      audio.current = player;
      player.onended = () => { URL.revokeObjectURL(url); if (audio.current === player) audio.current = null; };
      await player.play();
    } catch {
      if ("speechSynthesis" in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        window.speechSynthesis.speak(utterance);
      }
    }
  }, [stop]);

  useEffect(() => stop, [stop]);
  return { speak, stop };
}
