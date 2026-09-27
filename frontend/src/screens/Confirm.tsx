// Confirm (FE-4): check what the photo parse found before generating. Every value is editable in the same
// parameter panel as Design (key dimensions first, the rest under Advanced settings), required values the
// parse couldn't read show up as empty "Required" fields, the parse's questions can be answered in words
// (through /edit, so numbers still come from the engine), and the project type can be changed to any template.
import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { ParamPanel, type SchemaProperty } from "../components/ParamPanel";
import { useStore } from "../store";
import type { ParamValue, Spec, TemplateInfo } from "../types";
import { getCaptureSession, missingRequired, setCaptureSession, specFromDefaults, ungeneratedSpec } from "./flowState";

const assumedOf = (params: Record<string, ParamValue>) =>
  Object.entries(params)
    .filter(([, item]) => item.source === "default" || item.source === "inferred")
    .map(([name]) => name);

export function Confirm() {
  const session = getCaptureSession();
  const applyGenerateResult = useStore((state) => state.applyGenerateResult);
  const setScreen = useStore((state) => state.setScreen);
  const [spec, setSpec] = useState<Spec | null>(session?.parse.spec ?? null);
  const [templates, setTemplates] = useState<TemplateInfo[] | null>(null);
  const [questions, setQuestions] = useState<string[]>(session?.parse.questions.slice(0, 3) ?? []);
  const [answers, setAnswers] = useState<string[]>([]);
  const [answering, setAnswering] = useState(false);
  const [answerNote, setAnswerNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .templates()
      .then(setTemplates)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load the project types."));
  }, []);

  if (!spec) {
    return (
      <section aria-labelledby="confirm-title" className="mx-auto max-w-3xl">
        <h2 id="confirm-title" className="text-3xl font-bold">
          Confirm
        </h2>
        <EmptyState title="Nothing to confirm yet">
          <button type="button" className="app-button mt-2" onClick={() => setScreen("capture")}>
            Go to capture
          </button>
        </EmptyState>
      </section>
    );
  }

  const current = spec;
  const template = templates?.find((item) => item.key === current.template) ?? null;
  const properties = (template?.params_schema.properties ?? {}) as Record<string, SchemaProperty>;
  const titleOf = (name: string) => properties[name]?.title ?? name.replaceAll("_", " ");
  const missing = template ? missingRequired(template, current) : [];

  const save = (next: Spec) => {
    setSpec(next);
    if (session) setCaptureSession({ ...session, parse: { ...session.parse, spec: next } });
  };

  const update = (name: string, value: number | string | boolean | null) => {
    const params = { ...current.params };
    if (value === null) delete params[name];
    else params[name] = { value, source: "user", confidence: null };
    save({ ...current, params, assumed: assumedOf(params) });
  };

  const changeTemplate = (key: string) => {
    const info = templates?.find((item) => item.key === key);
    if (!info || key === current.template) return;
    // The parse's values and questions belong to the old type; start the new one from its defaults.
    save(specFromDefaults(info, {}, current.meta));
    setQuestions([]);
    setAnswers([]);
    setAnswerNote(null);
  };

  async function applyAnswers() {
    const text = questions
      .map((question, i) => (answers[i]?.trim() ? `${question} ${answers[i].trim()}` : null))
      .filter((line): line is string => line !== null)
      .join(" ");
    if (!text) return;
    setAnswering(true);
    setAnswerNote(null);
    try {
      const result = await api.edit({ spec: current, utterance: text });
      save({ ...ungeneratedSpec(result.spec), assumed: assumedOf(result.spec.params) });
      if (result.needs_clarification) {
        setAnswerNote(result.message);
      } else {
        setAnswerNote(`${result.message} Check the values above, then generate.`);
        setQuestions(questions.filter((_, i) => !answers[i]?.trim()));
        setAnswers([]);
      }
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 422 && missing.length > 0) {
        setAnswerNote(`Chisel still needs ${missing.map(titleOf).join(" and ")}. Type it into the field above.`);
      } else if (reason instanceof ApiError && reason.status === 503) {
        setAnswerNote("The assistant is unavailable right now. Fill in the values above instead.");
      } else {
        setAnswerNote(reason instanceof Error ? reason.message : "That answer couldn't be applied. Fill in the values above instead.");
      }
    } finally {
      setAnswering(false);
    }
  }

  async function confirm() {
    setLoading(true);
    setError(null);
    try {
      const response = await api.generate({ template: current.template, params: current.params, meta: current.meta });
      applyGenerateResult(response.spec, response.plan, "parse");
      setScreen("design");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not generate the design. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const confidence = session?.parse.template_confidence;
  const hasAnswer = answers.some((answer) => answer?.trim());

  return (
    <section aria-labelledby="confirm-title" className="mx-auto max-w-5xl space-y-5">
      <div>
        <h2 id="confirm-title" className="mb-1 text-3xl font-bold">
          Confirm what we found
        </h2>
        <p className="m-0 text-[var(--text-muted)]">Highlighted values are assumptions. Check them, answer any questions, then generate the design.</p>
      </div>
      {loading && <LoadingState message="Generating the model, checks, and plan…" />}
      {error && <ErrorState message={error} onRetry={() => void confirm()} />}
      <div className="grid gap-5 md:grid-cols-[.8fr_1.2fr]">
        <aside className="app-card space-y-3 self-start p-4">
          <h3 className="m-0">Detected project</h3>
          <div>
            <p className="m-0 font-semibold">{template?.name ?? current.template}</p>
            <p className="m-0 text-sm text-[var(--text-muted)]">
              {confidence === null || confidence === undefined ? "Selected manually" : `${Math.round(confidence * 100)}% confidence`}
            </p>
          </div>
          {session?.imageUrl ? (
            <img
              src={session.imageUrl}
              alt="Uploaded sketch or site"
              className="max-h-56 w-full rounded object-contain"
              // Some browsers can't preview HEIC (iPhone) photos; hide the broken image instead of showing it.
              onError={(event) => {
                event.currentTarget.hidden = true;
              }}
            />
          ) : (
            <p className="m-0 rounded bg-[var(--surface-muted)] p-3 text-sm">No photo attached.</p>
          )}
          <label className="block">
            Wrong type? Change it
            <select className="app-input mt-1 w-full" value={current.template} disabled={!templates} onChange={(event) => changeTemplate(event.target.value)}>
              {(templates ?? []).map((item) => (
                <option key={item.key} value={item.key}>
                  {item.name}
                </option>
              ))}
              {!templates && <option value={current.template}>{current.template}</option>}
            </select>
          </label>
          {template?.description && <p className="m-0 text-sm text-[var(--text-muted)]">{template.description}</p>}
        </aside>

        <div className="space-y-5">
          {questions.length > 0 && (
            <section className="app-card p-4" aria-labelledby="questions-title">
              <h3 id="questions-title" className="mt-0">
                A few questions
              </h3>
              <p className="mt-0 text-sm text-[var(--text-muted)]">Answer in your own words, or skip them and fill in the values below.</p>
              <form
                className="space-y-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  void applyAnswers();
                }}
              >
                {questions.map((question, i) => (
                  <label key={question} className="block">
                    <span className="font-medium">{question}</span>
                    <input
                      className="app-input mt-1 w-full"
                      value={answers[i] ?? ""}
                      placeholder="Your answer"
                      onChange={(event) => setAnswers((prev) => Object.assign([...prev], { [i]: event.target.value }))}
                    />
                  </label>
                ))}
                <button type="submit" className="app-button app-button--secondary" disabled={answering || !hasAnswer}>
                  {answering ? "Applying…" : "Apply answers"}
                </button>
              </form>
            </section>
          )}
          {answerNote && (
            <p className="m-0 rounded bg-[var(--surface-muted)] p-3" role="status">
              {answerNote}
            </p>
          )}
          {template ? <ParamPanel template={template} params={current.params} onChange={update} /> : !error && <LoadingState message="Loading the measurements…" />}
        </div>
      </div>
      {missing.length > 0 && (
        <p className="m-0 text-center text-[var(--text-muted)]" role="status">
          Fill in {missing.map(titleOf).join(" and ")} to generate the design.
        </p>
      )}
      <button type="button" className="app-button w-full" disabled={loading || !template || missing.length > 0} onClick={() => void confirm()}>
        Looks right — generate design
      </button>
    </section>
  );
}
