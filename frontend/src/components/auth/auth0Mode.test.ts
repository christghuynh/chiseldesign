// @vitest-environment jsdom
// FE-11: with VITE_AUTH0_* set, login goes through Auth0 (mocked here) and saving needs a logged-in user.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement as h } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auth0 = {
  isLoading: false,
  isAuthenticated: false,
  user: undefined as { sub: string; name?: string } | undefined,
  error: undefined as Error | undefined,
  loginWithPopup: vi.fn(async () => {}),
  logout: vi.fn(),
  getAccessTokenSilently: vi.fn(async () => "access-token"),
};

vi.mock("@auth0/auth0-react", () => ({
  Auth0Provider: ({ children }: { children: unknown }) => children,
  useAuth0: () => auth0,
}));

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv("VITE_AUTH0_DOMAIN", "chisel.us.auth0.com");
  vi.stubEnv("VITE_AUTH0_CLIENT_ID", "client-id");
  vi.stubEnv("VITE_AUTH0_AUDIENCE", "https://api.chisel.test");
  Object.assign(auth0, { isLoading: false, isAuthenticated: false, user: undefined, error: undefined });
  auth0.loginWithPopup.mockClear();
  auth0.logout.mockClear();
  vi.stubGlobal("fetch", vi.fn(async () => new Response("[]")));
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

// Modules read the env at import time, so import them after stubbing it.
async function load() {
  const [{ AuthProvider }, { Projects }, { SaveProject }, { useStore }, { AUTH0_CONFIG }] = await Promise.all([
    import("./AuthProvider"),
    import("../../screens/Projects"),
    import("../projects/SaveProject"),
    import("../../store"),
    import("../../hooks/useAuth"),
  ]);
  return { AuthProvider, Projects, SaveProject, useStore, AUTH0_CONFIG };
}

describe("Auth0 mode", () => {
  it("reads the config from VITE_AUTH0_*", async () => {
    const { AUTH0_CONFIG } = await load();
    expect(AUTH0_CONFIG).toEqual({ domain: "chisel.us.auth0.com", clientId: "client-id", audience: "https://api.chisel.test" });
  });

  it("asks logged-out users to log in, with a popup", async () => {
    const { AuthProvider, Projects } = await load();
    render(h(AuthProvider, null, h(Projects)));
    expect(screen.getByText("Log in to see your saved projects")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(auth0.loginWithPopup).toHaveBeenCalledOnce());
    expect(fetch).not.toHaveBeenCalled();
  });

  it("offers 'Log in to save' instead of saving when logged out", async () => {
    const { AuthProvider, SaveProject, useStore } = await load();
    useStore.setState({ spec: { template: "ramp" } as never });
    render(h(AuthProvider, null, h(SaveProject)));
    expect(screen.getByRole("button", { name: "Log in to save" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save project" })).toBeNull();
  });

  it("stores the user and token, and sends the token with requests", async () => {
    Object.assign(auth0, { isAuthenticated: true, user: { sub: "auth0|abc", name: "Everest" } });
    const { AuthProvider, Projects, useStore } = await load();
    render(h(AuthProvider, null, h(Projects)));
    expect(screen.getByText("Everest")).toBeTruthy();
    await waitFor(() => expect(useStore.getState().token).toBe("access-token"));
    expect(useStore.getState().user).toEqual({ sub: "auth0|abc", name: "Everest" });
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer access-token");
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(auth0.logout).toHaveBeenCalledOnce();
  });
});
