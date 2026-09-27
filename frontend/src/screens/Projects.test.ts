// @vitest-environment jsdom
// FE-11: the Projects screen with login off (dev mode, the test build has no VITE_AUTH0_*).
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../components/auth/AuthProvider";
import { useStore } from "../store";
import type { GenerateResponse } from "../types";
import { Projects } from "./Projects";

const switchback = JSON.parse(
  readFileSync(resolve(import.meta.dirname, "../../../fixtures/specs/ramp_switchback.json"), "utf8"),
) as GenerateResponse;

const SUMMARY = { id: 5, name: "Grandma's porch", template: "ramp", updated_at: "2026-09-26T14:00:00Z", thumb: null };

function mockFetch(routes: Record<string, [number, unknown] | unknown>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const key = `${init.method ?? "GET"} ${url}`;
      calls.push(key);
      const route = routes[key];
      const [status, body] = Array.isArray(route) && typeof route[0] === "number" ? route : [200, route];
      return status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body ?? null), { status: route === undefined ? 599 : status });
    }),
  );
  return calls;
}

const renderScreen = () => render(h(AuthProvider, null, h(Projects)));

beforeEach(() => {
  useStore.setState(useStore.getInitialState(), true);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Projects screen (login off)", () => {
  it("signs in as the local dev user and lists saved projects", async () => {
    mockFetch({ "GET /api/projects": [SUMMARY] });
    renderScreen();
    expect(await screen.findByText("Grandma's porch")).toBeTruthy();
    expect(screen.getByText(/Login off/)).toBeTruthy();
    expect(useStore.getState().user?.sub).toBe("dev|local");
  });

  it("opens a project into Design", async () => {
    mockFetch({
      "GET /api/projects": [SUMMARY],
      "GET /api/projects/5": { id: 5, name: SUMMARY.name, versions: [], latest: switchback.spec },
      "POST /api/generate": switchback,
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Open Grandma's porch" }));
    await waitFor(() => expect(useStore.getState().screen).toBe("design"));
    expect(useStore.getState().currentProjectId).toBe(5);
    expect(useStore.getState().plan).toEqual(switchback.plan);
  });

  it("shows an empty state when nothing is saved", async () => {
    mockFetch({ "GET /api/projects": [] });
    renderScreen();
    expect(await screen.findByText("No saved projects yet")).toBeTruthy();
  });

  it("explains a server without auth configured, with a retry", async () => {
    mockFetch({ "GET /api/projects": [503, { error: { code: "AUTH_NOT_CONFIGURED", message: "x" } }] });
    renderScreen();
    expect((await screen.findByRole("alert")).textContent).toMatch(/aren't set up on the server/);
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("saves the current design under a name and refreshes the list", async () => {
    useStore.getState().applyGenerateResult(switchback.spec, switchback.plan, "parse");
    let saved = false;
    const calls = mockFetch({
      "GET /api/projects": [],
      "POST /api/projects": { id: 11 },
    });
    // After the save, the list includes the new project.
    vi.mocked(fetch).mockImplementation(async (url, init = {}) => {
      const key = `${init.method ?? "GET"} ${url}`;
      calls.push(key);
      if (key === "POST /api/projects") {
        saved = true;
        return new Response(JSON.stringify({ id: 11 }));
      }
      return new Response(JSON.stringify(saved ? [{ ...SUMMARY, id: 11, name: "Front ramp" }] : []));
    });
    renderScreen();

    fireEvent.click(await screen.findByRole("button", { name: "Save project" }));
    const input = screen.getByLabelText("Project name") as HTMLInputElement;
    expect(input.value).toMatch(/^Ramp, /);
    fireEvent.change(input, { target: { value: "Front ramp" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Front ramp")).toBeTruthy();
    expect(screen.getByText("Saved the project.")).toBeTruthy();
    expect(useStore.getState().currentProjectId).toBe(11);
    expect(screen.getByRole("button", { name: "Save new version" })).toBeTruthy();
    expect(calls).toContain("POST /api/projects");
  });

  it("deletes a project only after confirming, then shows the empty state", async () => {
    // the list answers with the project until the DELETE has happened
    let deleted = false;
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit = {}) => {
        const key = `${init.method ?? "GET"} ${url}`;
        calls.push(key);
        if (key === "DELETE /api/projects/5") {
          deleted = true;
          return new Response(null, { status: 204 });
        }
        return new Response(JSON.stringify(deleted ? [] : [SUMMARY]));
      }),
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Delete Grandma's porch" }));
    expect(calls).not.toContain("DELETE /api/projects/5"); // the first click only asks
    expect(screen.getByText("Delete this project and its saved versions?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete" }));

    expect(await screen.findByText("No saved projects yet")).toBeTruthy();
    expect(calls.filter((c) => c === "DELETE /api/projects/5")).toHaveLength(1);
    expect(useStore.getState().projects).toEqual([]);
  });

  it("cancelling the confirmation deletes nothing", async () => {
    const calls = mockFetch({ "GET /api/projects": [SUMMARY] });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Delete Grandma's porch" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByText("Grandma's porch")).toBeTruthy();
    expect(screen.queryByText("Delete this project and its saved versions?")).toBeNull();
    expect(screen.getByRole("button", { name: "Delete Grandma's porch" })).toBeTruthy();
    expect(calls.some((c) => c.startsWith("DELETE"))).toBe(false);
  });

  it("deleting the open project unlinks it, so the next save creates a new project", async () => {
    useStore.setState({ currentProjectId: 5 });
    mockFetch({ "GET /api/projects": [SUMMARY], "DELETE /api/projects/5": [204, null] });
    renderScreen();
    expect(await screen.findByText("Open now")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Delete Grandma's porch" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
    await waitFor(() => expect(useStore.getState().currentProjectId).toBeNull());
  });

  it("keeps the project and says why when the server refuses", async () => {
    mockFetch({
      "GET /api/projects": [SUMMARY],
      "DELETE /api/projects/5": [404, { error: { code: "NOT_FOUND", message: "Project 5 not found" } }],
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Delete Grandma's porch" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/doesn't exist or belongs to someone else/);
    expect(screen.getByText("Grandma's porch")).toBeTruthy();
  });
});

