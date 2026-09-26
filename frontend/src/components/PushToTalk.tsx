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
export function PushToTalk(props: PushToTalkProps) {
  return (
    <button
      type="button"
      disabled
      aria-disabled="true"
      title="Voice input is not built yet (task VOX-3)"
      className="min-h-11 rounded border border-slate-400 px-4 py-2 text-slate-500"
    >
      {props.label ?? "Hold to talk"}
    </button>
  );
}
