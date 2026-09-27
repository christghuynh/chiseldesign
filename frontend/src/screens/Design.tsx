import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { KeyFacts } from "../components/KeyFacts";
import { ParamPanel } from "../components/ParamPanel";
import { PushToTalk } from "../components/PushToTalk";
import { RuleBadges } from "../components/RuleBadges";
import { TypedEditBox } from "../components/TypedEditBox";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { useSpeak } from "../hooks/useSpeak";
import { useStore } from "../store";
import type { ParamValue, RuleCheck, TemplateInfo } from "../types";
import { Scene } from "../three/Scene";
import { type EditTurn, recordExchange, withTurns } from "./editMemory";

export function Design() {
  const spec = useStore((state) => state.spec);
  const plan = useStore((state) => state.plan);
  const selected = useStore((state) => state.selectedPartIds);
  const setSelected = useStore((state) => state.setSelected);
  const applyGenerateResult = useStore((state) => state.applyGenerateResult);
  const undo = useStore((state) => state.undo);
  const redo = useStore((state) => state.redo);
  const cursor = useStore((state) => state.cursor);
  const history = useStore((state) => state.history);
  const setScreen = useStore((state) => state.setScreen);
  const setVoiceState = useStore((state) => state.setVoiceState);
  const setLastReply = useStore((state) => state.setLastReply);
  const setLastUtterance = useStore((state) => state.setLastUtterance);
  const { speak } = useSpeak();
  const [template, setTemplate] = useState<TemplateInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState<string | null>(null);
  const [sceneKey, setSceneKey] = useState(0);
  const [adjustOpen, setAdjustOpen] = useState(false);
  // Side panels can be collapsed to their header so more of the model is visible.
  const [collapsed, setCollapsed] = useState({ parameters: false, details: false });
  const togglePanel = (panel: keyof typeof collapsed) => setCollapsed((current) => ({ ...current, [panel]: !current[panel] }));
  const generateTimer = useRef<number | null>(null);
  const pendingPatch = useRef<Record<string, number | string | boolean | null>>({});
  const generation = useRef(0);
  const editTurns = useRef<EditTurn[]>([]);

  useEffect(() => {
    void api.templates()
      .then((items) => setTemplate(items.find((item) => item.key === spec?.template) ?? null))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load parameter controls."));
  }, [spec?.template]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        event.shiftKey ? redo() : undo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [redo, undo]);

  useEffect(() => () => {
    if (generateTimer.current !== null) window.clearTimeout(generateTimer.current);
  }, []);

  const selectedPart = useMemo(() => spec?.parts.find((part) => part.id === selected[0]), [selected, spec?.parts]);

  if (!spec || !plan) {
    return (
      <section aria-labelledby="design-title" className="workflow-empty-page mx-auto max-w-5xl">
        <div className="workflow-empty-page__heading"><p>03 · Design</p><h2 id="design-title">Design</h2></div>
        <EmptyState variant="design" eyebrow="A design starts with a direction" title="Start with a sketch or template" description="Add a photo or pick a starting template, then you can shape the details here.">
          <button type="button" className="app-button" onClick={() => setScreen("capture")}>Start in Capture</button>
        </EmptyState>
      </section>
    );
  }

  const currentSpec = spec;

  async function generate(params: Record<string, ParamValue>, source: "manual" | "fix") {
    const request = ++generation.current;
    setBusy(true);
    setError(null);
    try {
      const result = await api.generate({ template: currentSpec.template, params, meta: currentSpec.meta });
      if (request !== generation.current) return;
      applyGenerateResult(result.spec, result.plan, source);
    } catch (reason) {
      if (request !== generation.current) return;
      setError(reason instanceof Error ? reason.message : "The model could not be updated.");
    } finally {
      if (request === generation.current) setBusy(false);
    }
  }

  function change(name: string, raw: number | string | boolean | null) {
    pendingPatch.current[name] = raw;
    if (generateTimer.current !== null) window.clearTimeout(generateTimer.current);
    generateTimer.current = window.setTimeout(() => {
      generateTimer.current = null;
      const latest = useStore.getState().spec ?? currentSpec;
      const params = { ...latest.params };
      for (const [key, value] of Object.entries(pendingPatch.current)) {
        if (value === null) delete params[key];
        else params[key] = { value, source: "user", confidence: null };
      }
      pendingPatch.current = {};
      void generate(params, "manual");
    }, 150);
  }

  function fix(rule: RuleCheck) {
    if (!rule.fix) return;
    const params = { ...currentSpec.params };
    Object.entries(rule.fix.params_patch).forEach(([name, value]) => {
      if (typeof value === "number" || typeof value === "string" || typeof value === "boolean") {
        params[name] = { value, source: "user", confidence: null };
      }
    });
    void generate(params, "fix");
  }

  async function edit(text: string) {
    const keyword = text.trim().toLowerCase();
    setLastUtterance(text);
    if (keyword === "undo") { undo(); return; }
    if (keyword === "redo") { redo(); return; }
    setBusy(true);
    setVoiceState("processing");
    setError(null);
    try {
      const result = await api.edit({ spec: withTurns(currentSpec, editTurns.current), utterance: text });
      editTurns.current = recordExchange(editTurns.current, text, result.message);
      if (!result.needs_clarification) applyGenerateResult(result.spec, result.plan, "edit");
      setReply(result.message);
      setLastReply(result.message);
      setVoiceState("speaking");
      await speak(result.message);
      setVoiceState("idle");
    } catch (reason) {
      setVoiceState("error");
      setError(reason instanceof Error ? reason.message : "The design edit could not be applied.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="design-title" className="design-workspace">
      <div className="design-workspace__canvas">
        <Scene key={sceneKey} parts={spec.parts} selectedIds={selected} onSelect={(id) => setSelected(id ? [id] : [])} height="100%" background="#ffffff" showReset={false} />
      </div>

      <header className="design-workspace__topbar">
        <div className="design-workspace__history">
          <button type="button" className="app-button app-button--secondary" onClick={() => setScreen("confirm")}>Back to Confirm</button>
          <button type="button" className="app-button app-button--secondary app-icon-button" title="Reset model view" aria-label="Reset model view" onClick={() => setSceneKey((key) => key + 1)}>
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M4 8V4m0 0h4M4 4l3 3a8 8 0 1 1-1.4 9.9" /></svg>
          </button>
          <button type="button" className="app-button app-button--secondary app-icon-button" title="Undo" aria-label="Undo" disabled={cursor <= 0 || busy} onClick={undo}>
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M9 7 4 12l5 5M4 12h10a6 6 0 0 1 6 6" /></svg>
          </button>
          <button type="button" className="app-button app-button--secondary app-icon-button" title="Redo" aria-label="Redo" disabled={cursor >= history.length - 1 || busy} onClick={redo}>
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="m15 7 5 5-5 5m5-5H10a6 6 0 0 0-6 6" /></svg>
          </button>
          <button type="button" className="app-button" onClick={() => setScreen("plan")}>Continue to plan</button>
        </div>
      </header>

      {busy && <div className="design-workspace__status"><LoadingState message="Updating your build plan…" /></div>}
      {error && <div className="design-workspace__status"><ErrorState message={error} /></div>}

      <aside className={`design-workspace__panel design-workspace__panel--parameters${collapsed.parameters ? " is-collapsed" : ""}`} aria-label="Design parameters">
        <PanelToggle label="Parameters" controls="design-panel-parameters" expanded={!collapsed.parameters} onToggle={() => togglePanel("parameters")} />
        <div id="design-panel-parameters" className="design-workspace__panel-scroll" hidden={collapsed.parameters}>
          <div className="design-workspace__panel-intro">
            <p>03 · Shape your design</p>
            <h2 id="design-title">Design workspace</h2>
            <span>Rotate, zoom, and select a part to inspect it.</span>
          </div>
          {template ? <ParamPanel template={template} params={spec.params} onChange={change} busy={busy} /> : <div className="app-card p-4 text-sm text-[var(--text-muted)]">Loading design controls…</div>}
        </div>
      </aside>

      <aside className={`design-workspace__panel design-workspace__panel--details${collapsed.details ? " is-collapsed" : ""}`} aria-label="Design details">
        <PanelToggle label="Details & checks" controls="design-panel-details" expanded={!collapsed.details} onToggle={() => togglePanel("details")} />
        <div id="design-panel-details" className="design-workspace__panel-scroll" hidden={collapsed.details}>
          {selectedPart && (
            <section className="app-card design-workspace__selection" aria-live="polite">
              <p>Selected part</p>
              <strong>{selectedPart.label}: {selectedPart.name}</strong>
              <span>{selectedPart.material} · {selectedPart.thickness} in thick</span>
            </section>
          )}
          <KeyFacts spec={spec} />
          <RuleBadges rules={spec.rule_checks} onApplyFix={fix} busy={busy} />
        </div>
      </aside>

      <button type="button" className="app-button design-workspace__edit-trigger" onClick={() => setAdjustOpen(true)}>
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m4 20 4.2-1 10.5-10.5a2.2 2.2 0 0 0-3.1-3.1L5.1 15.9 4 20Z" /><path d="m13.8 7.2 3.1 3.1" /></svg>
        Make an adjustment
      </button>
      {adjustOpen && (
        <div className="design-workspace__editor-backdrop" role="presentation" onClick={() => setAdjustOpen(false)}>
          <section className="app-card design-workspace__composer" role="dialog" aria-modal="true" aria-labelledby="edits-title" onClick={(event) => event.stopPropagation()}>
            <div className="design-workspace__composer-heading">
              <div><p>Make an adjustment</p><h3 id="edits-title">Edit by voice or text</h3></div>
              <div className="flex items-start gap-2"><PushToTalk disabled={busy} onTranscript={(text) => void edit(text)} /><button type="button" className="app-button app-button--secondary app-icon-button" aria-label="Close adjustment menu" onClick={() => setAdjustOpen(false)}><svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2.1" strokeLinecap="round"><path d="m6.5 6.5 11 11m0-11-11 11" /></svg></button></div>
            </div>
            <TypedEditBox disabled={busy} onSubmit={(text) => void edit(text)} />
            {reply && <p className="design-workspace__reply" role="status">{reply}</p>}
            <div className="design-workspace__composer-footer"><p>Guidelines, not code compliance. Check local permit requirements.</p></div>
          </section>
        </div>
      )}
    </section>
  );
}

/** Header button that collapses or expands a Design side panel. */
function PanelToggle({ label, controls, expanded, onToggle }: { label: string; controls: string; expanded: boolean; onToggle: () => void }) {
  return (
    <button type="button" className="design-workspace__panel-toggle" aria-expanded={expanded} aria-controls={controls} onClick={onToggle} title={expanded ? `Collapse ${label.toLowerCase()}` : `Expand ${label.toLowerCase()}`}>
      <span>{label}</span>
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
    </button>
  );
}
