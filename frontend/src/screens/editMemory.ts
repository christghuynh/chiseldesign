// VOX-4: conversational memory for voice/typed edits. The Design screen keeps the last few
// exchanges and sends them with each /edit request in `spec.meta.edit_turns`, so a follow-up like
// "six inches" after "How much wider?" is understood. The backend reads them as context only and
// never stores them in the returned spec, so they don't end up in saved projects.
import type { Spec } from "../types";

export interface EditTurn {
  role: "user" | "model";
  text: string;
}

/** Messages kept: the last five user/assistant exchanges (the backend uses the same limit). */
export const MAX_EDIT_TURNS = 10;

/** The spec to post to /edit: the current spec plus the conversation so far. */
export function withTurns(spec: Spec, turns: EditTurn[]): Spec {
  return turns.length ? { ...spec, meta: { ...spec.meta, edit_turns: turns } } : spec;
}

/** Append one exchange (what the user said, what the assistant answered), keeping the most recent. */
export function recordExchange(turns: EditTurn[], utterance: string, reply: string): EditTurn[] {
  const next: EditTurn[] = [...turns];
  if (utterance.trim()) next.push({ role: "user", text: utterance.trim() });
  if (reply.trim()) next.push({ role: "model", text: reply.trim() });
  return next.slice(-MAX_EDIT_TURNS);
}
