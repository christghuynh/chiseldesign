import { useState } from "react";
import { api } from "../api/client";
import { HeroIllustration } from "../components/HeroIllustration";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { useStore } from "../store";
import { setCaptureSession, ungeneratedSpec } from "./flowState";

export function Landing() {
  const setScreen = useStore((state) => state.setScreen);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function tryDemo() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.generate({ template: "ramp", params: {}, meta: {} });
      setCaptureSession({
        parse: {
          spec: ungeneratedSpec(result.spec),
          template_confidence: 0.92,
          questions: ["Is the available length about 12 feet?"],
          raw_notes: "Loaded the offline demo fixture.",
        },
        imageUrl: null,
      });
      setScreen("confirm");
    } catch (reason) {
      const detail = reason instanceof Error ? ` (${reason.message})` : "";
      setError(`The demo service is unavailable${detail}. Start the backend with npm run dev, or use npm run dev:fixtures for the offline demo.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-labelledby="landing-title" className="landing-hero mx-auto max-w-6xl">
      <div className="landing-hero__copy">
        <p className="landing-hero__eyebrow">From sketch to build plan</p>
        <h2 id="landing-title">Start with a sketch. End with a clear craft.</h2>
        <p className="landing-hero__description">
          Upload a photo of your space or try the demo. We’ll help you turn the details into your next steps.
        </p>
        <div className="landing-hero__actions">
          <button type="button" className="app-button" onClick={() => void tryDemo()} disabled={loading}>Try the demo</button>
          <button type="button" className="app-button app-button--secondary" onClick={() => setScreen("capture")}>Start with a photo</button>
        </div>
        {loading && <LoadingState message="Loading the demo…" />}
        {error && <ErrorState message={error} onRetry={() => void tryDemo()} />}
        <p className="landing-hero__notice">Guidelines, not code compliance. Check local permit requirements.</p>
      </div>
      <HeroIllustration />
    </section>
  );
}
