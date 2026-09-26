import { DEV_ROUTES } from "./dev/registry";
import { SCREENS } from "./screens";
import { FLOW, type ScreenKey, useStore } from "./store";

const NAV: ScreenKey[] = [...FLOW, "projects", "overlay"];

// Skeleton (F-5): screen routing driven by the store. FE-1 builds the real shell (stepper,
// responsive layout, the rest of the accessibility baseline).
export default function App() {
  const screen = useStore((s) => s.screen);
  const setScreen = useStore((s) => s.setScreen);
  const { Component } = SCREENS[screen];

  // Dev pages (src/dev/routes) replace the whole app at /dev/<name>, dev server only.
  const DevRoute = import.meta.env.DEV ? DEV_ROUTES[window.location.pathname] : undefined;
  if (DevRoute) return <DevRoute />;

  return (
    <div className="min-h-screen bg-white text-base text-slate-900">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:m-2 focus:rounded focus:bg-white focus:p-2"
      >
        Skip to content
      </a>
      <header className="border-b border-slate-300 px-4 py-3">
        <h1 className="text-xl font-bold">SketchBuild</h1>
        <nav aria-label="Screens" className="mt-2 flex flex-wrap gap-2">
          {NAV.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setScreen(key)}
              aria-current={key === screen ? "page" : undefined}
              className="min-h-11 rounded border border-slate-400 px-3 py-2 hover:bg-slate-100 aria-[current=page]:bg-slate-900 aria-[current=page]:text-white"
            >
              {SCREENS[key].label}
            </button>
          ))}
        </nav>
      </header>
      <main id="main" className="p-4">
        <Component />
      </main>
    </div>
  );
}
