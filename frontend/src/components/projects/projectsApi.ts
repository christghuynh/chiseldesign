// Owner: P4. Saved projects (FE-11): the /api/projects routes (INF-6), with the Auth0 access token as a
// Bearer header. Kept here rather than in api/client.ts (P2's file), like the export calls. In fixture
// mode there is no backend, so projects live in memory for the session.
import { ApiError, USE_FIXTURES } from "../../api/client";
import type {
  ProjectCreateResponse,
  ProjectDetail,
  ProjectSummary,
  Spec,
  VersionCreateResponse,
  VersionInfo,
  VersionResponse,
} from "../../types";

export type VersionSource = VersionInfo["source"];

async function request<T>(token: string | null, method: "GET" | "POST" | "DELETE", url: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new ApiError(res.status, err?.error?.code ?? `HTTP_${res.status}`, err?.error?.message ?? res.statusText);
  }
  if (res.status === 204) return undefined as T; // DELETE answers with no body
  return res.json() as Promise<T>;
}

// ---- fixture mode: an in-memory stand-in with the same shapes and 404 behavior ----

interface FakeProject {
  id: number;
  name: string;
  template: string;
  updated_at: string;
  versions: { n: number; created_at: string; source: VersionSource; spec: Spec }[];
}

const fake = { nextId: 1, projects: new Map<number, FakeProject>() };

/** Test hook: forget the fixture-mode projects. */
export function resetFixtureProjects() {
  fake.nextId = 1;
  fake.projects.clear();
}

function fakeProject(id: number): FakeProject {
  const project = fake.projects.get(id);
  if (!project) throw new ApiError(404, "NOT_FOUND", `Project ${id} not found`);
  return project;
}

const fixtureApi = {
  list: async (): Promise<ProjectSummary[]> =>
    [...fake.projects.values()]
      .map(({ id, name, template, updated_at }) => ({ id, name, template, updated_at, thumb: null }))
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at) || b.id - a.id),
  create: async (name: string, spec: Spec): Promise<ProjectCreateResponse> => {
    const id = fake.nextId++;
    const now = new Date().toISOString();
    fake.projects.set(id, { id, name, template: spec.template, updated_at: now, versions: [{ n: 1, created_at: now, source: "manual", spec }] });
    return { id };
  },
  get: async (id: number): Promise<ProjectDetail> => {
    const p = fakeProject(id);
    return {
      id: p.id,
      name: p.name,
      versions: p.versions.map(({ n, created_at, source }) => ({ n, created_at, source })),
      latest: p.versions[p.versions.length - 1].spec,
    };
  },
  remove: async (id: number): Promise<void> => {
    fakeProject(id); // 404 when it does not exist, like the server
    fake.projects.delete(id);
  },
  addVersion: async (id: number, spec: Spec, source: VersionSource): Promise<VersionCreateResponse> => {
    const p = fakeProject(id);
    const n = p.versions.length + 1;
    p.updated_at = new Date().toISOString();
    p.versions.push({ n, created_at: p.updated_at, source, spec });
    return { n };
  },
  getVersion: async (id: number, n: number): Promise<VersionResponse> => {
    const version = fakeProject(id).versions.find((v) => v.n === n);
    if (!version) throw new ApiError(404, "NOT_FOUND", `Version ${n} not found`);
    return { spec: version.spec };
  },
};

export const projectsApi = {
  list: (token: string | null): Promise<ProjectSummary[]> =>
    USE_FIXTURES ? fixtureApi.list() : request(token, "GET", "/api/projects"),
  create: (token: string | null, name: string, spec: Spec): Promise<ProjectCreateResponse> =>
    USE_FIXTURES ? fixtureApi.create(name, spec) : request(token, "POST", "/api/projects", { name, spec }),
  get: (token: string | null, id: number): Promise<ProjectDetail> =>
    USE_FIXTURES ? fixtureApi.get(id) : request(token, "GET", `/api/projects/${id}`),
  remove: (token: string | null, id: number): Promise<void> =>
    USE_FIXTURES ? fixtureApi.remove(id) : request(token, "DELETE", `/api/projects/${id}`),
  addVersion: (token: string | null, id: number, spec: Spec, source: VersionSource): Promise<VersionCreateResponse> =>
    USE_FIXTURES ? fixtureApi.addVersion(id, spec, source) : request(token, "POST", `/api/projects/${id}/versions`, { spec, source }),
  getVersion: (token: string | null, id: number, n: number): Promise<VersionResponse> =>
    USE_FIXTURES ? fixtureApi.getVersion(id, n) : request(token, "GET", `/api/projects/${id}/versions/${n}`),
};

/** A message for the UI, with the auth failures spelled out. */
export function projectErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return "Your login has expired. Log in again to use saved projects.";
    if (e.status === 503) return "Saved projects aren't set up on the server yet (Auth0 isn't configured).";
    if (e.status === 404) return "That project doesn't exist or belongs to someone else.";
    return e.message;
  }
  return e instanceof Error ? e.message : "Something went wrong.";
}
