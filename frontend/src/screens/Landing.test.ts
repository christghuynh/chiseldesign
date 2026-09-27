// FE-13: story images must be fully off screen (or faded out) before they're hidden, so they never
// vanish mid-screen while scrolling the landing page.
import { describe, expect, it } from "vitest";
import { visualStyle } from "./Landing";

describe("landing story images", () => {
  it("design slides a full image width plus the screen margin before it's hidden", () => {
    const leaving = visualStyle(1, 1.99, "right");
    expect(leaving.visibility).toBe("visible");
    expect(leaving.transform).toContain("(100% + 12rem)");
    expect(visualStyle(1, 2, "right").visibility).toBe("hidden");
  });

  it("plan drops below the bottom of the screen before it's hidden", () => {
    const leaving = visualStyle(2, 2.99, "left");
    expect(leaving.visibility).toBe("visible");
    expect(leaving.transform).toContain("(50vh + 50% + 8rem)");
    expect(visualStyle(2, 3, "left").visibility).toBe("hidden");
  });

  it("the incoming image starts fully off screen", () => {
    expect(visualStyle(2, 1.01, "left").transform).toMatch(/calc\(0\.99\d* \* \(100% \+ 12rem\)\)/);
    expect(visualStyle(3, 2.01, "right").transform).toMatch(/calc\(0\.99\d* \* \(50vh \+ 50% \+ 8rem\)\)/);
  });

  it("the first image fades out as it shrinks instead of vanishing at full opacity", () => {
    expect(visualStyle(0, 0.5, "left").opacity).toBeCloseTo(0.5);
    expect(visualStyle(0, 0.99, "left").opacity).toBeLessThan(0.02);
  });

  it("images at rest are fully shown", () => {
    for (const [i, side] of [[0, "left"], [1, "right"], [2, "left"], [3, "right"]] as const) {
      const style = visualStyle(i, i, side);
      expect(style.visibility).toBe("visible");
      expect(style.opacity).toBe(1);
    }
  });
});
