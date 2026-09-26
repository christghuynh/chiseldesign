// Owner: P2. TypedEditBoxProps is a contract (P4 or others may place this component): changing it
// must be announced.
import { useState } from "react";

export interface TypedEditBoxProps {
  /** Called with the trimmed text when the user submits a non-empty edit. */
  onSubmit: (text: string) => void;
  disabled?: boolean;
  /** Input placeholder (default an example edit). */
  placeholder?: string;
}

// Skeleton: an accessible text field and button, the typed fallback for voice edits. The wiring to
// `/edit`, showing the reply as text and speaking it is task VOX-7a.
export function TypedEditBox({ onSubmit, disabled = false, placeholder = "e.g. make it 6 inches wider" }: TypedEditBoxProps) {
  const [text, setText] = useState("");

  return (
    <form
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const trimmed = text.trim();
        if (trimmed === "") return;
        onSubmit(trimmed);
        setText("");
      }}
    >
      <label className="sr-only" htmlFor="typed-edit">
        Type an edit
      </label>
      <input
        id="typed-edit"
        type="text"
        value={text}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) => setText(event.target.value)}
        className="min-h-11 flex-1 rounded border border-slate-400 px-3"
      />
      <button type="submit" disabled={disabled} className="min-h-11 rounded bg-slate-900 px-4 text-white disabled:opacity-50">
        Apply
      </button>
    </form>
  );
}
