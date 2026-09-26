// Owner: P4. Wraps the app in Auth0Provider when login is configured (FE-11), and mirrors the login state
// into authSlice so any screen can read `user` from the store. main.tsx renders <AuthProvider><App /></AuthProvider>.
import { Auth0Provider } from "@auth0/auth0-react";
import { type ReactNode, useEffect } from "react";
import { AUTH0_CONFIG, useAuth } from "../../hooks/useAuth";
import { useStore } from "../../store";

function AuthSync() {
  const { user, getToken } = useAuth();
  const setAuth = useStore((s) => s.setAuth);
  const clearAuth = useStore((s) => s.clearAuth);
  const sub = user?.sub ?? null;
  const name = user?.name ?? null;

  useEffect(() => {
    if (sub === null) {
      clearAuth();
      return;
    }
    let live = true;
    getToken()
      .catch(() => null)
      .then((token) => live && setAuth({ sub, name }, token));
    return () => {
      live = false;
    };
    // getToken is a new function each render, so it stays out of the deps: the user identity is what matters.
  },[sub, name, setAuth, clearAuth]);

  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  if (!AUTH0_CONFIG) {
    return (
      <>
        <AuthSync />
        {children}
      </>
    );
  }
  return (
    <Auth0Provider
      domain={AUTH0_CONFIG.domain}
      clientId={AUTH0_CONFIG.clientId}
      authorizationParams={{ audience: AUTH0_CONFIG.audience, redirect_uri: window.location.origin }}
      // Keep the session across page reloads. Refresh tokens avoid third-party cookies, which Safari blocks.
      cacheLocation="localstorage"
      useRefreshTokens
    >
      <AuthSync />
      {children}
    </Auth0Provider>
  );
}
