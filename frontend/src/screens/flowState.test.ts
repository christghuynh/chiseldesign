import { describe, expect, it } from "vitest";
import type { TemplateInfo } from "../types";
import { missingRequired, specFromDefaults } from "./flowState";

const ramp: TemplateInfo = {
  key: "ramp",
  name: "Ramp",
  description: "",
  params_schema: { required: ["total_rise_in"], properties: { total_rise_in: {}, clear_width_in: {}, available_length_in: {}, layout: {} } },
  defaults: { clear_width_in: 36, available_length_in: null, layout: "auto", edge_curb: true },
};

describe("specFromDefaults", () => {
  it("fills defaults, skips null defaults and marks them assumed", () => {
    const spec = specFromDefaults(ramp);
    expect(spec.params.clear_width_in).toEqual({ value: 36, source: "default", confidence: null });
    expect(spec.params.edge_curb.value).toBe(true);
    expect("available_length_in" in spec.params).toBe(false);
    expect(spec.assumed.sort()).toEqual(["clear_width_in", "edge_curb", "layout"]);
    expect(spec.parts).toEqual([]);
    expect(spec.template).toBe("ramp");
  });

  it("puts user values on top and keeps them out of assumed", () => {
    const spec = specFromDefaults(ramp, { total_rise_in: 14, layout: "straight", clear_width_in: undefined }, { contractor_quote_cad: 4000 });
    expect(spec.params.total_rise_in).toEqual({ value: 14, source: "user", confidence: null });
    expect(spec.params.layout.source).toBe("user");
    expect(spec.params.clear_width_in.source).toBe("default");
    expect(spec.assumed).not.toContain("total_rise_in");
    expect(spec.meta.contractor_quote_cad).toBe(4000);
  });
});

describe("missingRequired", () => {
  it("lists required params with no value", () => {
    expect(missingRequired(ramp, specFromDefaults(ramp))).toEqual(["total_rise_in"]);
    expect(missingRequired(ramp, specFromDefaults(ramp, { total_rise_in: 21 }))).toEqual([]);
  });
});

describe("measurementValues / presetDimensions", () => {
  const bed: TemplateInfo = {
    key: "garden_bed", name: "Raised garden bed", description: "",
    params_schema: { properties: { length_in: { title: "Length (in)" }, width_in: { title: "Width (in)" }, height_in: { title: "Height (in)" }, board: {} } },
    defaults: { length_in: 72, width_in: 24, height_in: 30, board: "2x10_PT" },
  };

  it("maps the form's generic width to each template's own width param and drops the rest", async () => {
    const { measurementValues } = await import("./flowState");
    expect(measurementValues(bed, { clear_width_in: 30, total_rise_in: 21, available_length_in: undefined })).toEqual({ width_in: 30 });
    expect(measurementValues(ramp, { clear_width_in: 42, total_rise_in: 14 })).toEqual({ clear_width_in: 42, total_rise_in: 14 });
  });

  it("lists every numeric preset with its title", async () => {
    const { presetDimensions } = await import("./flowState");
    expect(presetDimensions(bed)).toEqual([["Length (in)", "72"], ["Width (in)", "24"], ["Height (in)", "30"]]);
  });

  it("shows only the key dimensions, with units, when the template marks them", async () => {
    const { presetDimensions } = await import("./flowState");
    const grouped: TemplateInfo = {
      ...bed,
      params_schema: { properties: { length_in: { title: "Length", unit: "in", group: "key" }, height_in: { title: "Height", unit: "in", group: "key" }, gap_in: { title: "Gap", unit: "in", group: "advanced" } } },
      defaults: { length_in: 72, height_in: 29.25, gap_in: 0.125 },
    };
    expect(presetDimensions(grouped)).toEqual([["Length", "72 in"], ["Height", "29.25 in"]]);
  });
});
