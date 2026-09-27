import { HeroIllustration } from "../components/HeroIllustration";
import { useStore } from "../store";

export function Landing() {
  const setScreen = useStore((state) => state.setScreen);

  return (
    <section aria-labelledby="landing-title" className="landing-hero mx-auto max-w-6xl">
      <div className="landing-hero__copy">
        <p className="landing-hero__eyebrow">From sketch to build plan</p>
        <h2 id="landing-title">Start with a sketch. End with a clear craft.</h2>
        <p className="landing-hero__description">
          Upload a photo of your space or choose a template. We’ll help you turn the details into your next steps.
        </p>
        <div className="landing-hero__actions">
          <button type="button" className="app-button" onClick={() => setScreen("capture")}>Get started now</button>
        </div>
        <p className="landing-hero__notice">Guidelines, not code compliance. Check local permit requirements.</p>
      </div>
      <HeroIllustration />
    </section>
  );
}
