// Whether the app is in dark mode right now. App.tsx sets `data-theme` on <html>; this hook follows that
// attribute, so a component re-renders the moment the theme is toggled (the 3D canvas, for one, draws its
// colours in JavaScript and can't pick them up from CSS).
import { useSyncExternalStore } from "react";

const isDark = () => document.documentElement.dataset.theme === "dark";

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

export function useDarkTheme(): boolean {
  return useSyncExternalStore(subscribe, isDark, () => false);
}
