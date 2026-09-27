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
      className="typed-edit-box"
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
        className="app-input min-h-12 flex-1"
      />
      <button type="submit" disabled={disabled} className="app-button min-h-12 disabled:opacity-50">
        Apply
      </button>
    </form>
  );
}
