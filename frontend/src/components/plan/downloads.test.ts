// @vitest-environment jsdom
// FE-10: download buttons, fixture-mode behaviour, filenames and the local CSV fallback.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement as h } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { GenerateResponse } from "../../types";
import { Downloads } from "./Downloads";
import { cutListCsv, exportFilename, fetchExport } from "./exports";

const { spec, plan } = JSON.parse(
  readFileSync(resolve(import.meta.dirname, "../../../../fixtures/specs/ramp_switchback.json"), "utf8"),
) as GenerateResponse;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const button = (name: RegExp) => screen.getByRole("button", { name });

describe("exports", () => {
  it("names files after the template and layout", () => {
    expect(exportFilename(spec, "step")).toBe("sketchbuild-ramp-switchback.step");
    expect(exportFilename(spec, "stl")).toBe("sketchbuild-ramp-switchback.stl");
    expect(exportFilename(spec, "csv")).toBe("sketchbuild-ramp-switchback-cut-list.csv");
    const auto = { ...spec, params: { ...spec.params, layout: { ...spec.params.layout, value: "auto" } } };
    expect(exportFilename(auto, "step")).toBe("sketchbuild-ramp.step");
  });

  it("builds a CSV with a header and one line per cut-list row, quoting where needed", () => {
    const lines = cutListCsv(plan).trimEnd().split("\r\n");
    expect(lines).toHaveLength(plan.cut_list.length + 1);
    expect(lines[0]).toBe("label,name,material,actual_dims_in,length_in,length,qty,part_ids,cut_notes");
    const first = plan.cut_list[0];
    expect(lines[1].startsWith(`${first.label},${first.name},${first.material},`)).toBe(true);
    expect(lines[1]).toContain(`"${first.length_display.replace(/"/g, '""')}"`); // 7' 6-5/16" has a quote
  });

  it("posts the spec to the export route and uses the server's filename when given", async () => {
    const fetchMock = vi.fn(async () => new Response("ISO-10303-21;", { headers: { "Content-Disposition": 'attachment; filename="ramp.step"' } }));
    vi.stubGlobal("fetch", fetchMock);
    const file = await fetchExport("step", spec, plan, false);
    expect(fetchMock).toHaveBeenCalledWith("/api/export/step", expect.objectContaining({ method: "POST", body: JSON.stringify({ spec }) }));
    expect(file.filename).toBe("ramp.step");
    expect(await file.blob.text()).toBe("ISO-10303-21;");
  });

  it("uses the default filename and the cut-list route for CSV", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response("label\r\n"));
    vi.stubGlobal("fetch", fetchMock);
    const file = await fetchExport("csv", spec, plan, false);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/export/cutlist.csv");
    expect(file.filename).toBe("sketchbuild-ramp-switchback-cut-list.csv");
  });
});

describe("Downloads", () => {
  it("fixture mode: STEP and STL are disabled with a tooltip; CSV is built locally", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const save = vi.fn();
    render(h(Downloads, { spec, plan, useFixtures: true, save }));

    for (const name of [/STEP/, /STL/]) {
      const b = button(name);
      expect(b.getAttribute("aria-disabled")).toBe("true");
      expect(b.getAttribute("title")).toMatch(/fixture mode/);
      fireEvent.click(b);
    }
    expect(save).not.toHaveBeenCalled();

    fireEvent.click(button(/Cut list CSV/));
    await waitFor(() => expect(save).toHaveBeenCalledOnce());
    const [{ blob, filename }] = save.mock.calls[0];
    expect(filename).toBe("sketchbuild-ramp-switchback-cut-list.csv");
    expect(await blob.text()).toBe(cutListCsv(plan));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("backend mode: STEP downloads through the API", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("solid")));
    const save = vi.fn();
    render(h(Downloads, { spec, plan, useFixtures: false, save }));
    expect(button(/STEP/).getAttribute("aria-disabled")).toBe("false");
    fireEvent.click(button(/STL/));
    await waitFor(() => expect(save).toHaveBeenCalledOnce());
    expect(save.mock.calls[0][0].filename).toBe("sketchbuild-ramp-switchback.stl");
  });

  it("shows an error when the export route fails", async () => {
    const body = JSON.stringify({ error: { code: "NOT_IMPLEMENTED", message: "STEP export is not built yet (GEO-17)." } });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status: 501 })));
    const save = vi.fn();
    render(h(Downloads, { spec, plan, useFixtures: false, save }));
    fireEvent.click(button(/STEP/));
    expect((await screen.findByRole("alert")).textContent).toContain("GEO-17");
    expect(save).not.toHaveBeenCalled();
  });

  it("Print plan calls print", () => {
    const print = vi.fn();
    render(h(Downloads, { spec, plan, useFixtures: true, print }));
    fireEvent.click(button(/Print plan/));
    expect(print).toHaveBeenCalledOnce();
  });
});
