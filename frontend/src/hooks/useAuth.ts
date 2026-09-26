// Owner: P4. Login (FE-11). One hook for the whole app, with two modes chosen at build time:
//
// - auth0: VITE_AUTH0_DOMAIN, VITE_AUTH0_CLIENT_ID and VITE_AUTH0_AUDIENCE are set. Login uses a popup
//   (a redirect would reload the page and lose the unsaved design in the store).
// - dev: any of them is missing. There is no login; everyone is a fixed local user and requests carry
//   no token, which matches the backend's AUTH_DISABLED=1 dev user.
import { useAuth0 } from "@auth0/auth0-react";
import type { AuthUser } from "../store";

export interface Auth0Config {
  domain: string;
  clientId: string;
  audience: string;
}

function readConfig(): Auth0Config | null {
  const env = import.meta.env;
  const domain = (env.VITE_AUTH0_DOMAIN ?? "").trim();
  const clientId = (env.VITE_AUTH0_CLIENT_ID ?? "").trim();
  const audience = (env.VITE_AUTH0_AUDIENCE ?? "").trim();
  return domain && clientId && audience ? { domain, clientId, audience } : null;
}

/** The Auth0 settings, or null when login is off (dev mode). Fixed at build time. */
export const AUTH0_CONFIG = readConfig();

export const DEV_USER: AuthUser = { sub: "dev|local", name: "Local dev" };

export interface AuthApi {
  mode: "auth0" | "dev";
  /** False while Auth0 is still restoring the session. */
  ready: boolean;
  user: AuthUser | null;
  /** Error from the last login attempt, if any. */
  error: string | null;
  login: () => Promise<void>;
  logout: () => void;
  /** An access token for the API, or null in dev mode. */
  getToken: () => Promise<string | null>;
}

function useAuth0Mode(): AuthApi {
  const { isLoading, isAuthenticated, user, error, loginWithPopup, logout, getAccessTokenSilently } = useAuth0();
  return {
    mode: "auth0",
    ready: !isLoading,
    user: isAuthenticated && user?.sub ? { sub: user.sub, name: user.name ?? user.email ?? null } : null,
    error: error?.message ?? null,
    login: () => loginWithPopup(),
    logout: () => void logout({ logoutParams: { returnTo: window.location.origin } }),
    getToken: async () => (await getAccessTokenSilently()) ?? null,
  };
}

const DEV_AUTH: AuthApi = {
  mode: "dev",
  ready: true,
  user: DEV_USER,
  error: null,
  login: async () => {},
  logout: () => {},
  getToken: async () => null,
};

function useDevMode(): AuthApi {
  return DEV_AUTH;
}

/** Login state and a token getter. The mode is a build-time constant, so the hook choice never changes. */
export const useAuth: () => AuthApi = AUTH0_CONFIG ? useAuth0Mode : useDevMode;
