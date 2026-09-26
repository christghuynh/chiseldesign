import { describe, expect, it } from "vitest";
import { DEV_ROUTES } from "./registry";

describe("dev route registry", () => {
  it("serves each file in dev/routes at /dev/<name>", () => {
    expect(Object.keys(DEV_ROUTES)).toContain("/dev/reference");
    expect(typeof DEV_ROUTES["/dev/reference"]).toBe("function");
  });

  it("only produces /dev/ paths", () => {
    for (const path of Object.keys(DEV_ROUTES)) expect(path).toMatch(/^\/dev\/[\w-]+$/);
  });
});
