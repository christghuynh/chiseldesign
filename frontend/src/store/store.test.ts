import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import type { GenerateResponse } from "../types";
import { FLOW, useStore } from "./index";

const load = (file: string): GenerateResponse =>
  JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../fixtures/specs", file), "utf8"));
const straight = load("ramp_straight.json");
const switchback = load("ramp_switchback.json");

beforeEach(() => {
  useStore.setState(useStore.getInitialState(), true);
});

describe("combined store", () => {
  it("has every slice's initial state", () => {
    const s = useStore.getState();
    expect(s.spec).toBeNull();
    expect(s.history).toEqual([]);
    expect(s.cursor).toBe(-1);
    expect(s.screen).toBe("landing");
    expect(s.selectedPartIds).toEqual([]);
    expect(s.voiceState).toBe("idle");
    expect(s.steps).toEqual([]);
    expect(s.user).toBeNull();
    expect(FLOW[0]).toBe("capture");
  });
});

describe("spec slice: history, undo and redo", () => {
  it("records each applied result as a version", () => {
    const { applyGenerateResult } = useStore.getState();
    applyGenerateResult(straight.spec, straight.plan, "parse");
    applyGenerateResult(switchback.spec, switchback.plan, "fix");
    const s = useStore.getState();
    expect(s.history.map((h) => h.source)).toEqual(["parse", "fix"]);
    expect(s.cursor).toBe(1);
    expect(s.spec).toBe(switchback.spec);
    expect(s.plan).toBe(switchback.plan);
  });

  it("undoes and redoes, and stops at both ends", () => {
    const { applyGenerateResult } = useStore.getState();
    applyGenerateResult(straight.spec, straight.plan);
    applyGenerateResult(switchback.spec, switchback.plan);

    useStore.getState().undo();
    expect(useStore.getState().spec).toBe(straight.spec);
    useStore.getState().undo(); // already at the first version
    expect(useStore.getState().cursor).toBe(0);
    expect(useStore.getState().spec).toBe(straight.spec);

    useStore.getState().redo();
    expect(useStore.getState().spec).toBe(switchback.spec);
    useStore.getState().redo(); // already at the latest version
    expect(useStore.getState().cursor).toBe(1);
  });

  it("drops the redo tail when a new version is applied after undo", () => {
    const { applyGenerateResult } = useStore.getState();
    applyGenerateResult(straight.spec, straight.plan);
    applyGenerateResult(switchback.spec, switchback.plan);
    useStore.getState().undo();
    applyGenerateResult(straight.spec, straight.plan, "edit");
    const s = useStore.getState();
    expect(s.history).toHaveLength(2);
    expect(s.cursor).toBe(1);
    expect(s.history[1].source).toBe("edit");
    s.redo(); // nothing to redo
    expect(useStore.getState().cursor).toBe(1);
  });

  it("does nothing when there is no spec to record, or nothing to undo", () => {
    const s = useStore.getState();
    s.pushVersion("manual");
    s.undo();
    s.redo();
    expect(useStore.getState().history).toEqual([]);
    expect(useStore.getState().cursor).toBe(-1);
  });
});

describe("other slices", () => {
  it("ui: screen and part selection", () => {
    const s = useStore.getState();
    s.setScreen("design");
    s.setSelected(["A-1"]);
    s.setHighlighted(["B-1", "B-2"]);
    expect(useStore.getState()).toMatchObject({ screen: "design", selectedPartIds: ["A-1"], highlightedPartIds: ["B-1", "B-2"] });
  });

  it("build: setting new steps resets to the first step", () => {
    const s = useStore.getState();
    s.setBuildStep(3);
    s.setSteps([{ n: 1, title: "t", text: "x", part_labels: [], cut_callouts: [], safety_tip: null }]);
    expect(useStore.getState().buildStep).toBe(0);
    expect(useStore.getState().steps).toHaveLength(1);
  });

  it("auth: clearing wipes the user, token and projects", () => {
    const s = useStore.getState();
    s.setAuth({ sub: "auth0|1", name: null }, "token");
    s.setCurrentProjectId(7);
    s.clearAuth();
    expect(useStore.getState()).toMatchObject({ user: null, token: null, projects: [], currentProjectId: null });
  });

  it("voice: state and last exchange", () => {
    const s = useStore.getState();
    s.setVoiceState("recording");
    s.setLastUtterance("make it wider");
    s.setLastReply("Widened to 42 inches.");
    expect(useStore.getState()).toMatchObject({ voiceState: "recording", lastUtterance: "make it wider", lastReply: "Widened to 42 inches." });
  });
});
