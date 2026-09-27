// Owner: P4. The saved-projects list (FE-11). Props only: the Projects screen does the loading and deleting.
import { useState } from "react";
import type { ProjectSummary } from "../../types";

interface ProjectListProps {
  projects: ProjectSummary[];
  currentProjectId: number | null;
  /** Id of the project being opened, if any. */
  openingId: number | null;
  /** Id of the project being deleted, if any. */
  deletingId?: number | null;
  onOpen: (id: number) => void;
  onDelete?: (id: number) => void;
}

function formatUpdated(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

const templateName = (key: string) => key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, " ");

export function ProjectList({ projects, currentProjectId, openingId, deletingId = null, onOpen, onDelete }: ProjectListProps) {
  // Deleting is permanent, so the button asks once, inline, before it does anything.
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const busy = openingId !== null || deletingId !== null;
  return (
    <ul className="grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3" aria-label="Saved projects">
      {projects.map((p) => (
        <li key={p.id} className="app-card flex gap-3 p-3">
          {p.thumb ? (
            <img src={p.thumb} alt="" className="h-20 w-28 flex-none rounded object-cover" />
          ) : (
            <div aria-hidden="true" className="grid h-20 w-28 flex-none place-items-center rounded bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
              {templateName(p.template)}
            </div>
          )}
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <h3 className="m-0 truncate text-base font-semibold">{p.name}</h3>
            <p className="m-0 text-sm text-[var(--text-muted)]">
              {templateName(p.template)} · updated <time dateTime={p.updated_at}>{formatUpdated(p.updated_at)}</time>
            </p>
            <div className="mt-auto flex items-center gap-2">
              <button
                type="button"
                className="app-button app-button--secondary text-sm"
                onClick={() => onOpen(p.id)}
                disabled={busy}
                aria-label={`Open ${p.name}`}
              >
                {openingId === p.id ? "Opening…" : "Open"}
              </button>
              {onDelete && confirmingId !== p.id && (
                <button
                  type="button"
                  className="app-button app-button--secondary text-sm text-[var(--danger)]"
                  onClick={() => setConfirmingId(p.id)}
                  disabled={busy}
                  aria-label={`Delete ${p.name}`}
                >
                  {deletingId === p.id ? "Deleting…" : "Delete"}
                </button>
              )}
              {p.id === currentProjectId && <span className="text-sm font-semibold text-[var(--brand)]">Open now</span>}
            </div>
            {onDelete && confirmingId === p.id && (
              <div role="group" aria-label={`Confirm deleting ${p.name}`} className="flex flex-wrap items-center gap-2 text-sm">
                <span>Delete this project and its saved versions?</span>
                <button
                  type="button"
                  className="app-button text-sm"
                  onClick={() => {
                    setConfirmingId(null);
                    onDelete(p.id);
                  }}
                >
                  Yes, delete
                </button>
                <button type="button" className="app-button app-button--secondary text-sm" onClick={() => setConfirmingId(null)}>
                  Cancel
                </button>
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
