// Owner: P4. Log in / log out (FE-11). Rendered on the Projects screen; P2 can also mount it in the header.
import { useState } from "react";
import { useAuth } from "../../hooks/useAuth";

export function AuthButton() {
  const { mode, ready, user, login, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (mode === "dev") {
    return (
      <span className="text-sm text-[var(--text-muted)]" title="Login is off: VITE_AUTH0_* is not set, so everyone is the local dev user">
        Login off (local dev)
      </span>
    );
  }
  if (!ready) return <span className="text-sm text-[var(--text-muted)]">Checking login…</span>;

  if (user) {
    return (
      <span className="flex flex-wrap items-center gap-2 text-sm">
        <span>
          Signed in as <strong>{user.name ?? "you"}</strong>
        </span>
        <button type="button" className="app-button app-button--secondary text-sm" onClick={logout}>
          Log out
        </button>
      </span>
    );
  }

  const onLogin = async () => {
    setBusy(true);
    setError(null);
    try {
      await login();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="flex flex-wrap items-center gap-2 text-sm">
      <button type="button" className="app-button text-sm" onClick={onLogin} disabled={busy}>
        {busy ? "Logging in…" : "Log in"}
      </button>
      {error && (
        <span role="alert" className="text-[var(--danger)]">
          {error}. If nothing opened, allow pop-ups for this site.
        </span>
      )}
    </span>
  );
}
