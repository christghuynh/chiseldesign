// Owner: P4. Login state and the saved-projects list.
import type { StateCreator } from "zustand";
import type { ProjectSummary } from "../types";
import type { AppStore } from "./index";

export interface AuthUser {
  /** The Auth0 subject id. */
  sub: string;
  name: string | null;
}

export interface AuthSlice {
  user: AuthUser | null;
  token: string | null;
  projects: ProjectSummary[];
  currentProjectId: number | null;
  setAuth: (user: AuthUser, token: string) => void;
  clearAuth: () => void;
  setProjects: (projects: ProjectSummary[]) => void;
  setCurrentProjectId: (id: number | null) => void;
}

export const createAuthSlice: StateCreator<AppStore, [], [], AuthSlice> = (set) => ({
  user: null,
  token: null,
  projects: [],
  currentProjectId: null,
  setAuth: (user, token) => set({ user, token }),
  clearAuth: () => set({ user: null, token: null, projects: [], currentProjectId: null }),
  setProjects: (projects) => set({ projects }),
  setCurrentProjectId: (currentProjectId) => set({ currentProjectId }),
});
