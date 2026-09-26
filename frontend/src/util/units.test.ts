import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { formatFraction, formatFtIn, parseLength } from "./units";

interface Cases {
  format_ft_in: [number, string][];
  format_fraction: [number, string][];
  parse_length: [string, number][];
  parse_length_errors: string[];
}

// Same file the backend tests read, so the two implementations can't drift apart.
const cases: Cases = JSON.parse(
  readFileSync(resolve(__dirname, "../../../fixtures/units/cases.json"), "utf8"),
);

describe("units", () => {
  it.each(cases.format_ft_in)("formatFtIn(%s) = %s", (inches, expected) => {
    expect(formatFtIn(inches)).toBe(expected);
  });

  it.each(cases.format_fraction)("formatFraction(%s) = %s", (inches, expected) => {
    expect(formatFraction(inches)).toBe(expected);
  });

  it.each(cases.parse_length)("parseLength(%j) = %s", (text, expected) => {
    expect(parseLength(text)).toBeCloseTo(expected, 10);
  });

  it.each(cases.parse_length_errors)("parseLength(%j) throws", (text) => {
    expect(() => parseLength(text)).toThrow();
  });

  it.each([-1, -0.001, Number.NaN, Number.POSITIVE_INFINITY])("rejects %s", (bad) => {
    expect(() => formatFtIn(bad)).toThrow();
    expect(() => formatFraction(bad)).toThrow();
  });

  it("round-trips at 1/16 resolution", () => {
    for (let sixteenths = 0; sixteenths < 16 * 12 * 25; sixteenths++) {
      const inches = sixteenths / 16;
      expect(parseLength(formatFtIn(inches))).toBe(inches);
    }
  });
});
