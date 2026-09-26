import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../store";

// Skeleton (F-5). FE-3 builds the real screen: upload, camera capture, measurements form,
// contractor quote, template picker and loading state.
export function Capture() {
  const applyGenerateResult = useStore((s) => s.applyGenerateResult);
  const setScreen = useStore((s) => s.setScreen);
  const [status, setStatus] = useState<string | null>(null);

  async function loadSample() {
    setStatus("Loading…");
    try {
      const { spec, plan } = await api.generate({ template: "ramp", params: {}, meta: {} });
      applyGenerateResult(spec, plan, "manual");
      setScreen("design");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Something went wrong");
    }
  }

  return (
    <section aria-labelledby="capture-title" className="space-y-4">
      <h2 id="capture-title" className="text-2xl font-semibold">
        Capture
      </h2>
      <p>Photo upload, measurements and the template picker land here (task FE-3).</p>
      <button
        type="button"
        onClick={loadSample}
        className="min-h-11 rounded bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
      >
        Dev: load the sample ramp
      </button>
      {status && <p role="status">{status}</p>}
    </section>
  );
}
