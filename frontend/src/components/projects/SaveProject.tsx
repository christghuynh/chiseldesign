// Owner: P4. "Save project" (FE-11), used on the Plan and Projects screens. Anyone can design; saving
// needs a login, so logged-out users get a login button first (a popup, so the design stays in memory).
import { type FormEvent, useEffect, useState } from "react";
import { useAuth } from "../../hooks/useAuth";
import { useStore } from "../../store";
import { defaultProjectName, saveCurrentProject } from "./projectActions";
import { projectErrorMessage } from "./projectsApi";

interface SaveProjectProps {
  /** Called after a successful save, e.g. to refresh a project list. */
  onSaved?: () => void;
}

export function SaveProject({ onSaved }: SaveProjectProps) {
  const { mode, ready, user, login, getToken } = useAuth();
  const spec = useStore((s) => s.spec);
  const currentProjectId = useStore((s) => s.currentProjectId);
  const setCurrentProjectId = useStore((s) => s.setCurrentProjectId);
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // "Saved the project." is about the project the editor is linked to; once that is deleted it would be wrong.
  const linked = currentProjectId !== null;
  useEffect(() => {
    if (!linked) setStatus(null);
  }, [linked]);

  if (!spec) return null;

  const run = async (action: () => Promise<string>) => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      setStatus(await action());
      onSaved?.();
    } catch (e) {
      setError(projectErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const saveVersion = () =>
    run(async () => {
      const { n } = await saveCurrentProject(await getToken(), "");
      return `Saved as version ${n}.`;
    });

  const submitNew = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      setCurrentProjectId(null);
      const result = await saveCurrentProject(await getToken(), name);
      setNaming(false);
      return result.n > 1 ? `Saved the project with ${result.n} versions.` : "Saved the project.";
    });
  };

  const startNaming = () => {
    setName(defaultProjectName());
    setStatus(null);
    setNaming(true);
  };

  const onLogin = () =>
    run(async () => {
      await login();
      return "Logged in. You can save now.";
    });

  let body;
  if (mode === "auth0" && !ready) {
    body = <span className="text-sm text-[var(--text-muted)]">Checking login…</span>;
  } else if (!user) {
    body = (
      <button type="button" className="app-button app-button--secondary" onClick={onLogin} disabled={busy}>
        Log in to save
      </button>
    );
  } else if (naming) {
    body = (
      <form onSubmit={submitNew} className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col text-sm">
          Project name
          <input
            className="min-h-11 rounded border border-[var(--border)] bg-[var(--surface)] px-3"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={120}
            required
            autoFocus
          />
        </label>
        <button type="submit" className="app-button" disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </button>
        <button type="button" className="app-button app-button--secondary" onClick={() => setNaming(false)} disabled={busy}>
          Cancel
        </button>
      </form>
    );
  } else if (currentProjectId !== null) {
    body = (
      <span className="flex flex-wrap gap-2">
        <button type="button" className="app-button" onClick={saveVersion} disabled={busy}>
          {busy ? "Saving…" : "Save new version"}
        </button>
        <button type="button" className="app-button app-button--secondary" onClick={startNaming} disabled={busy}>
          Save as new project
        </button>
      </span>
    );
  } else {
    body = (
      <button type="button" className="app-button" onClick={startNaming} disabled={busy}>
        Save project
      </button>
    );
  }

  return (
    <div className="print-hide flex flex-col gap-2">
      {body}
      <p aria-live="polite" className="m-0 text-sm text-[var(--text-muted)]">
        {status}
      </p>
      {error && (
        <p role="alert" className="m-0 text-sm text-[var(--danger)]">
          {error}
        </p>
      )}
    </div>
  );
}
