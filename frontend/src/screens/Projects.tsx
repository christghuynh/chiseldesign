// Owner: P4. Projects screen (FE-11): login, the saved-projects list, open (loads the latest version into
// Design) and save the current design. Anonymous users can use everything else in the app; only saving
// and this list need a login.
import { useCallback, useEffect, useState } from "react";
import { AuthButton } from "../components/auth/AuthButton";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { ProjectList } from "../components/projects/ProjectList";
import { SaveProject } from "../components/projects/SaveProject";
import { openProject } from "../components/projects/projectActions";
import { projectErrorMessage, projectsApi } from "../components/projects/projectsApi";
import { useAuth } from "../hooks/useAuth";
import { useStore } from "../store";

export function Projects() {
  const { mode, ready, user, getToken } = useAuth();
  const projects = useStore((s) => s.projects);
  const setProjects = useStore((s) => s.setProjects);
  const currentProjectId = useStore((s) => s.currentProjectId);
  const hasDesign = useStore((s) => s.spec !== null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);
  const sub = user?.sub ?? null;

  // getToken is a new function every render, so the list reloads when the user changes instead.
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProjects(await projectsApi.list(await getToken()));
    } catch (e) {
      setError(projectErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [sub, setProjects]);

  useEffect(() => {
    if (sub !== null) void load();
  }, [sub, load]);

  const open = async (id: number) => {
    setOpeningId(id);
    setError(null);
    try {
      await openProject(await getToken(), id);
    } catch (e) {
      setError(projectErrorMessage(e));
      setOpeningId(null);
    }
  };

  let content;
  if (mode === "auth0" && !ready) {
    content = <LoadingState message="Checking login…" />;
  } else if (!user) {
    content = (
      <EmptyState title="Log in to see your saved projects">
        You can design, plan and build without an account. Logging in lets you save projects and reopen them later.
      </EmptyState>
    );
  } else if (loading && projects.length === 0) {
    content = <LoadingState message="Loading your projects…" />;
  } else if (projects.length === 0) {
    content = error ? null : (
      <EmptyState title="No saved projects yet">
        {hasDesign ? "Save the current design above to keep it." : "Start a design, then save it from here or from the Plan screen."}
      </EmptyState>
    );
  } else {
    content = <ProjectList projects={projects} currentProjectId={currentProjectId} openingId={openingId} onOpen={open} />;
  }

  return (
    <section aria-labelledby="projects-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="projects-title" className="m-0 text-2xl font-semibold">
          Projects
        </h2>
        <AuthButton />
      </div>
      {hasDesign && user && (
        <div className="app-card p-4">
          <h3 className="m-0 mb-2 text-base font-semibold">Current design</h3>
          <SaveProject onSaved={load} />
        </div>
      )}
      {error && <ErrorState message={error} onRetry={user ? load : undefined} />}
      {content}
      {mode === "dev" && (
        <p className="text-sm text-[var(--text-muted)]">
          Login is off in this build, so projects are saved as the local dev user. The backend needs <code>AUTH_DISABLED=1</code>.
        </p>
      )}
    </section>
  );
}
