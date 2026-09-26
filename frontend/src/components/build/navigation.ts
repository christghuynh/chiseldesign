// Owner: P4. Pure build-mode logic (no React), so the screen, the keyboard, and the voice commands
// all move through the steps the same way.
import type { BuildStep, Part } from "../../types";

export type BuildAction = "next" | "back" | "repeat" | "stop";

/** Where the builder is: a step index, or the "Done" screen after the last step. */
export interface BuildPosition {
  index: number;
  done: boolean;
}

/**
 * Applies one navigation action. Next on the last step goes to the Done screen, Back from Done
 * returns to the last step, and Back on the first step stays put. Repeat and stop do not move.
 */
export function navigate(pos: BuildPosition, action: BuildAction, total: number): BuildPosition {
  if (total <= 0) return { index: 0, done: false };
  const index = Math.min(Math.max(pos.index, 0), total - 1);
  switch (action) {
    case "next":
      if (pos.done) return { index, done: true };
      return index + 1 < total ? { index: index + 1, done: false } : { index, done: true };
    case "back":
      if (pos.done) return { index: total - 1, done: false };
      return { index: Math.max(index - 1, 0), done: false };
    default:
      return { index, done: pos.done };
  }
}

/** The subset of a KeyboardEvent the shortcut handler reads. */
export interface KeyLike {
  key: string;
  altKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
  /** True for auto-repeat while a key is held down. */
  repeat?: boolean;
  target?: EventTarget | null;
}

function isTextEntry(target: EventTarget | null | undefined): boolean {
  if (!target || typeof target !== "object") return false;
  const el = target as { tagName?: string; type?: string; isContentEditable?: boolean };
  const tag = el.tagName?.toUpperCase();
  if (tag === "INPUT") return !["checkbox", "radio", "button", "submit", "reset", "range"].includes(el.type ?? "text");
  return tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable === true;
}

/**
 * Keyboard shortcuts: → next, ← back, R repeat. Ignored with modifiers, while typing, and on
 * auto-repeat (holding → must not skip several steps).
 */
export function keyToAction(e: KeyLike): BuildAction | null {
  if (e.altKey || e.ctrlKey || e.metaKey || e.repeat || isTextEntry(e.target)) return null;
  switch (e.key) {
    case "ArrowRight":
      return "next";
    case "ArrowLeft":
      return "back";
    case "r":
    case "R":
      return "repeat";
    default:
      return null;
  }
}

/** Ids of the parts a step works on, for highlighting in the 3D view. */
export function partIdsForStep(step: BuildStep | undefined, parts: Part[]): string[] {
  if (!step || step.part_labels.length === 0) return [];
  const labels = new Set(step.part_labels);
  return parts.filter((p) => labels.has(p.label)).map((p) => p.id);
}
