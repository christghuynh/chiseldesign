// Owner: P4. Save and open (FE-11), as plain functions over the store so they're easy to test.
//
// Save: the first save of a design creates the project and uploads its version history up to the undo
// cursor (PRD §12: anonymous sessions keep versions in the store, and saving uploads them). Later saves
// add the current spec as one new version.
// Open: loads the project's latest spec, regenerates it (the plan is not stored), and starts a fresh
// history with it, so undo can't step back into a different design.
import { api } from "../../api/client";
import { useStore } from "../../store";
import { projectsApi } from "./projectsApi";

/** Upload at most this many versions on the first save (the most recent ones). */
export const MAX_UPLOADED_VERSIONS = 20;

export interface SaveResult {
  id: number;
  created: boolean;
  /** Version number of the current design on the server. */
  n: number;
}

export async function saveCurrentProject(token: string | null, name: string): Promise<SaveResult> {
  const { spec, history, cursor, currentProjectId, setCurrentProjectId } = useStore.getState();
  if (!spec) throw new Error("There is no design to save yet.");

  if (currentProjectId !== null) {
    const source = history[cursor]?.source ?? "manual";
    const { n } = await projectsApi.addVersion(token, currentProjectId, spec, source);
    return { id: currentProjectId, created: false, n };
  }

  const upTo = cursor >= 0 ? history.slice(0, cursor + 1) : [];
  const entries = upTo.length > 0 ? upTo.slice(-MAX_UPLOADED_VERSIONS) : [{ spec, source: "manual" as const }];
  const { id } = await projectsApi.create(token, name.trim() || defaultProjectName(), entries[0].spec);
  let n = 1;
  for (const entry of entries.slice(1)) {
    ({ n } = await projectsApi.addVersion(token, id, entry.spec, entry.source));
  }
  setCurrentProjectId(id);
  return { id, created: true, n };
}

export async function openProject(token: string | null, id: number): Promise<void> {
  const detail = await projectsApi.get(token, id);
  const { template, params, meta } = detail.latest;
  const { spec, plan } = await api.generate({ template, params, meta });
  useStore.setState({ spec, plan, history: [{ spec, plan, source: "manual" }], cursor: 0 });
  const { setCurrentProjectId, setSelected, setHighlighted, setScreen } = useStore.getState();
  setCurrentProjectId(id);
  setSelected([]);
  setHighlighted([]);
  setScreen("design");
}

/**
 * Delete a saved project (and all its versions) and drop it from the list. If it is the project the editor
 * is linked to, the link is cleared: the design stays open, and saving it again makes a new project instead
 * of trying to add a version to one that no longer exists.
 */
export async function deleteProject(token: string | null, id: number): Promise<void> {
  await projectsApi.remove(token, id);
  const { projects, setProjects, currentProjectId, setCurrentProjectId } = useStore.getState();
  setProjects(projects.filter((p) => p.id !== id));
  if (currentProjectId === id) setCurrentProjectId(null);
}

export function defaultProjectName(now = new Date()): string {
  const { spec } = useStore.getState();
  const template = spec?.template ?? "project";
  const label = template.charAt(0).toUpperCase() + template.slice(1).replace(/_/g, " ");
  return `${label}, ${now.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}
