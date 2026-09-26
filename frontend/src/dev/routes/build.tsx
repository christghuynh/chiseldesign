// Owner: P4. /dev/build: Build mode on the switchback fixture, without going through the flow.
import { useEffect, useState } from "react";
import { BuildMode } from "../../screens/BuildMode";
import { useStore } from "../../store";
import type { GenerateResponse } from "../../types";

export default function BuildDev() {
  const hasSpec = useStore((s) => s.spec !== null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (useStore.getState().spec) return;
    fetch("/fixtures/specs/ramp_switchback.json")
      .then((res) => res.json() as Promise<GenerateResponse>)
      .then(({ spec, plan }) => useStore.getState().applyGenerateResult(spec, plan, "manual"))
      .catch((e: unknown) => setError(String(e)));
  }, []);

  return (
    <main className="min-h-screen bg-white p-4 text-base text-slate-900">
      <p className="mb-4 text-sm text-slate-600">Dev page: Build mode on fixtures/specs/ramp_switchback.json.</p>
      {error && <p role="alert">{error}</p>}
      {hasSpec ? <BuildMode /> : <p role="status">Loading the fixture…</p>}
    </main>
  );
}
