import { useState } from "react";
import { api } from "../api/client";
import { LoadingState } from "../components/common/LoadingState";
import { useStore } from "../store";
import { setCaptureSession, ungeneratedSpec } from "./flowState";

export function Landing() {
  const setScreen = useStore((state) => state.setScreen);
  const [loading, setLoading] = useState(false);
  async function tryDemo() {
    setLoading(true);
    try {
      const result = await api.generate({ template: "ramp", params: {}, meta: {} });
      setCaptureSession({ parse: { spec: ungeneratedSpec(result.spec), template_confidence: 0.92, questions: ["Is the available length about 12 feet?"], raw_notes: "Loaded the offline demo fixture." }, imageUrl: null });
      setScreen("confirm");
    } finally { setLoading(false); }
  }
  return <section aria-labelledby="landing-title" className="mx-auto max-w-3xl space-y-6 py-8"><p className="m-0 font-semibold uppercase tracking-wider text-[var(--brand)]">Plan safely. Build confidently.</p><h2 id="landing-title" className="m-0 text-4xl font-bold">Turn a porch sketch into a practical accessibility-ramp plan.</h2><p className="max-w-2xl text-lg text-[var(--text-muted)]">SketchBuild helps you check dimensions, explore safer layouts, and prepare a clear DIY plan—before you buy lumber.</p><div className="flex flex-wrap gap-3"><button type="button" className="app-button" onClick={() => void tryDemo()} disabled={loading}>Try the demo</button><button type="button" className="app-button app-button--secondary" onClick={() => setScreen("capture")}>Start with a photo</button></div>{loading && <LoadingState message="Loading the demo ramp…" />}<p className="text-sm text-[var(--text-muted)]">Guidelines, not code compliance. Check local permit requirements.</p></section>;
}
