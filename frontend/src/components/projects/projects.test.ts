// FE-11: the projects API client (auth header, errors) and the save/open actions over the store.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { useStore } from "../../store";
import type { GenerateResponse, Spec } from "../../types";
import { MAX_UPLOADED_VERSIONS, openProject, saveCurrentProject } from "./projectActions";
import { projectErrorMessage, projectsApi } from "./projectsApi";

const load = (name: string) =>
  JSON.parse(readFileSync(resolve(import.meta.dirname, `../../../../fixtures/specs/${name}.json`), "utf8")) as GenerateResponse;
const straight = load("ramp_straight");
const switchback = load("ramp_switchback");

interface Call {
  method: string;
  url: string;
  auth: string | null;
  body: any;
}

/** A fetch stand-in: records calls and answers from `routes` ("POST /api/projects" -> body or [status, body]). */
function mockFetch(routes: Record<string, unknown | ((call: Call) => unknown)>) {
  const calls: Call[] = [];
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const headers = (init.headers ?? {}) as Record<string, string>;
    const call: Call = {
      method: init.method ?? "GET",
      url,
      auth: headers.Authorization ?? null,
      body: typeof init.body === "string" ? JSON.parse(init.body) : null,
    };
    calls.push(call);
    const route = routes[`${call.method} ${url}`];
    if (route === undefined) return new Response(JSON.stringify({ error: { code: "NO_ROUTE", message: url } }), { status: 599 });
    const answer = typeof route === "function" ? route(call) : route;
    const [status, body] = Array.isArray(answer) && typeof answer[0] === "number" ? answer : [200, answer];
    return new Response(JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

beforeEach(() => {
  useStore.setState(useStore.getInitialState(), true);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("projectsApi", () => {
  it("sends the access token as a Bearer header", async () => {
    const calls = mockFetch({ "GET /api/projects": [] });
    await projectsApi.list("tok-123");
    expect(calls[0].auth).toBe("Bearer tok-123");
  });

  it("sends no Authorization header in dev mode", async () => {
    const calls = mockFetch({ "GET /api/projects": [] });
    await projectsApi.list(null);
    expect(calls[0].auth).toBeNull();
  });

  it("turns error bodies into ApiErrors with readable messages", async () => {
    mockFetch({ "GET /api/projects": [503, { error: { code: "AUTH_NOT_CONFIGURED", message: "no tenant" } }] });
    const error = await projectsApi.list(null).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("AUTH_NOT_CONFIGURED");
    expect(projectErrorMessage(error)).toMatch(/aren't set up/);
    expect(projectErrorMessage(new ApiError(401, "UNAUTHORIZED", "x"))).toMatch(/log in again/i);
    expect(projectErrorMessage(new ApiError(404, "NOT_FOUND", "x"))).toMatch(/doesn't exist/);
  });
});

describe("saveCurrentProject", () => {
  const withVersions = (count: number) => {
    const { applyGenerateResult } = useStore.getState();
    for (let i = 0; i < count; i++) {
      const spec: Spec = { ...straight.spec, meta: { ...straight.spec.meta, i } };
      applyGenerateResult(spec, straight.plan, i === 0 ? "parse" : "edit");
    }
  };

  it("creates the project and uploads the history up to the undo cursor", async () => {
    withVersions(3);
    useStore.getState().undo(); // cursor on version 2 of 3: version 3 is a redo, not part of the design
    let versions = 1;
    const calls = mockFetch({
      "POST /api/projects": { id: 7 },
      "POST /api/projects/7/versions": () => ({ n: ++versions }),
    });

    const result = await saveCurrentProject("tok", "  Grandma's porch  ");

    expect(result).toEqual({ id: 7, created: true, n: 2 });
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(["POST /api/projects", "POST /api/projects/7/versions"]);
    expect(calls[0].body.name).toBe("Grandma's porch");
    expect(calls[0].body.spec.meta.i).toBe(0);
    expect(calls[1].body).toMatchObject({ source: "edit", spec: { meta: { i: 1 } } });
    expect(calls.every((c) => c.auth === "Bearer tok")).toBe(true);
    expect(useStore.getState().currentProjectId).toBe(7);
  });

  it("uploads only the most recent versions of a long history", async () => {
    withVersions(MAX_UPLOADED_VERSIONS + 5);
    const calls = mockFetch({ "POST /api/projects": { id: 1 }, "POST /api/projects/1/versions": { n: 2 } });
    await saveCurrentProject(null, "Long");
    expect(calls).toHaveLength(MAX_UPLOADED_VERSIONS);
    expect(calls[0].body.spec.meta.i).toBe(5);
  });

  it("adds one version to the open project on later saves", async () => {
    withVersions(2);
    useStore.getState().setCurrentProjectId(4);
    const calls = mockFetch({ "POST /api/projects/4/versions": { n: 9 } });
    const result = await saveCurrentProject(null, "");
    expect(result).toEqual({ id: 4, created: false, n: 9 });
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toMatchObject({ source: "edit", spec: { meta: { i: 1 } } });
  });

  it("refuses to save when there is no design", async () => {
    await expect(saveCurrentProject(null, "x")).rejects.toThrow(/no design/);
  });
});

describe("openProject", () => {
  it("regenerates the latest version, starts a fresh history and goes to Design", async () => {
    useStore.getState().applyGenerateResult(straight.spec, straight.plan, "parse");
    useStore.getState().applyGenerateResult(straight.spec, straight.plan, "edit");
    useStore.getState().setHighlighted(["A-1"]);
    const calls = mockFetch({
      "GET /api/projects/3": { id: 3, name: "Porch", versions: [{ n: 1, created_at: "2026-09-26T12:00:00Z", source: "manual" }], latest: switchback.spec },
      "POST /api/generate": switchback,
    });

    await openProject("tok", 3);

    expect(calls[1].body).toEqual({ template: "ramp", params: switchback.spec.params, meta: switchback.spec.meta });
    const s = useStore.getState();
    expect(s.spec).toEqual(switchback.spec);
    expect(s.plan).toEqual(switchback.plan);
    expect(s.history).toHaveLength(1);
    expect(s.cursor).toBe(0);
    expect(s.currentProjectId).toBe(3);
    expect(s.highlightedPartIds).toEqual([]);
    expect(s.screen).toBe("design");
  });

  it("leaves the current design alone when the project can't be loaded", async () => {
    useStore.getState().applyGenerateResult(straight.spec, straight.plan, "parse");
    mockFetch({ "GET /api/projects/9": [404, { error: { code: "NOT_FOUND", message: "nope" } }] });
    await expect(openProject(null, 9)).rejects.toBeInstanceOf(ApiError);
    expect(useStore.getState().spec).toEqual(straight.spec);
    expect(useStore.getState().currentProjectId).toBeNull();
  });
});
