// @vitest-environment jsdom
// The hook follows <html data-theme>, so the 3D canvas and the Design screen repaint when the theme is toggled.
import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { useDarkTheme } from "./useDarkTheme";

afterEach(() => {
  delete document.documentElement.dataset.theme;
});

it("reports the current theme and updates when it is toggled", async () => {
  document.documentElement.dataset.theme = "light";
  const { result } = renderHook(() => useDarkTheme());
  expect(result.current).toBe(false);
  await act(async () => {
    document.documentElement.dataset.theme = "dark";
    await Promise.resolve(); // let the MutationObserver deliver
  });
  expect(result.current).toBe(true);
  await act(async () => {
    document.documentElement.dataset.theme = "light";
    await Promise.resolve();
  });
  expect(result.current).toBe(false);
});
