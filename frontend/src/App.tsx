import { useEffect, useState } from "react";
import { AuthButton } from "./components/auth/AuthButton";
import { DEV_ROUTES } from "./dev/registry";
import { SCREENS } from "./screens";
import { useStore } from "./store";

export default function App() {
  const screen = useStore((state) => state.screen);
  const setScreen = useStore((state) => state.setScreen);
  const [helpOpen, setHelpOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const { Component } = SCREENS[screen];

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "?" && !(event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement)) {
        event.preventDefault();
        setHelpOpen(true);
      }
      if (event.key === "Escape") setHelpOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const DevRoute = import.meta.env.DEV ? DEV_ROUTES[window.location.pathname] : undefined;
  if (DevRoute) return <DevRoute />;

  return (
    <div className={`theme-transition ${screen === "landing" ? "app-shell--landing" : screen === "design" ? "app-shell--design" : "min-h-screen"} bg-[var(--bg)] text-[var(--text)]`}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-[var(--surface)] focus:p-3">
        Skip to content
      </a>
      <header className="app-header sticky top-0 z-30">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2">
          <div className="app-brand-cluster">
            <button type="button" onClick={() => setScreen("landing")} className="app-home-button app-home-button--brand" aria-label="Go to Chisel welcome screen">
              <span className="h-8 w-11 shrink-0" aria-hidden="true">
                <img src="/brand/logo.png" alt="" className="h-full w-full object-contain" />
              </span>
              <span className="app-brand-name app-brand-name--chisel">chisel</span>
            </button>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <AuthButton />
            <button
              type="button"
              className="app-button app-button--secondary app-icon-button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? (
                <svg aria-hidden="true" viewBox="0 0 24 24" className="block h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round">
                  <circle cx="12" cy="12" r="3.5" />
                  <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M18.7 5.3l-1.4 1.4M6.7 17.3l-1.4 1.4" />
                </svg>
              ) : (
                <svg aria-hidden="true" viewBox="0 0 24 24" className="block h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20.5 15.2A8.5 8.5 0 0 1 8.8 3.5 8.5 8.5 0 1 0 20.5 15.2Z" />
                </svg>
              )}
            </button>
            <button
              type="button"
              className="app-button app-button--secondary text-sm"
              onClick={() => setScreen("projects")}
              aria-current={screen === "projects" ? "page" : undefined}
            >
              Projects
            </button>
            <button type="button" className="app-button app-button--secondary text-sm" onClick={() => setHelpOpen(true)} aria-haspopup="dialog">
              Shortcuts
            </button>
          </div>
        </div>
      </header>
      <main id="main" className={screen === "design" ? "design-main" : screen === "landing" ? "landing-main" : `mx-auto w-full max-w-7xl px-4 py-7 md:px-6 ${screen === "capture" ? "md:py-5" : "md:py-10"}`}><Component /></main>
      {helpOpen && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" role="presentation">
          <section role="dialog" aria-modal="true" aria-labelledby="shortcuts-title" className="app-card max-w-md p-5 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 id="shortcuts-title" className="m-0 text-xl font-bold">Keyboard shortcuts</h2>
              <button type="button" className="app-button app-button--secondary" onClick={() => setHelpOpen(false)}>Close</button>
            </div>
            <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
              <dt><kbd>Space</kbd></dt><dd>Hold to talk (outside a text field)</dd>
              <dt><kbd>Ctrl/Cmd + Z</kbd></dt><dd>Undo in Design</dd>
              <dt><kbd>Ctrl/Cmd + Shift + Z</kbd></dt><dd>Redo in Design</dd>
              <dt><kbd>?</kbd></dt><dd>Open this help</dd>
            </dl>
          </section>
        </div>
      )}
    </div>
  );
}
