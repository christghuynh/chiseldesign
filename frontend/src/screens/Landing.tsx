import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";

const story = [
  {
    title: "Start with a sketch.",
    description: "A rough drawing, a photo of your space, or a starting template is enough to begin.",
    image: "/landing/capture.jpg",
    alt: "Chisel's confirmation screen showing a photographed accessibility-ramp sketch and key dimensions.",
    side: "left",
    visual: "capture",
  },
  {
    title: "Shape it in 3D.",
    description: "Adjust the dimensions that matter and watch the design respond before you buy a board.",
    image: "/landing/design.png",
    alt: "Chisel's design workspace with a 3D accessibility ramp and parameter panels.",
    side: "right",
    visual: "design",
  },
  {
    title: "Plan every cut.",
    description: "See the materials, the cut list, and how each piece fits on the boards you need.",
    image: "/landing/plan.png",
    alt: "Chisel cutting layouts showing the boards and their optimized cuts.",
    side: "left",
    visual: "plan",
  },
  {
    title: "Build with a clear next step.",
    description: "Take a practical, part-by-part guide with you to the workshop.",
    image: "/landing/build.png",
    alt: "Chisel build mode showing the stringer-cutting step and 3D ramp preview.",
    side: "right",
    visual: "build",
  },
] as const;

const MAX_PROGRESS = story.length - 1;
const WHEEL_DISTANCE_PER_STAGE = 1100;
const STABLE_PORTION = .3;

function clamp(value: number) {
  return Math.max(0, Math.min(MAX_PROGRESS, value));
}

function presence(progress: number, index: number) {
  return Math.max(0, 1 - Math.abs(progress - index));
}

function storyProgress(scrollPosition: number) {
  if (scrollPosition >= MAX_PROGRESS) return MAX_PROGRESS;
  const stage = Math.floor(scrollPosition);
  const withinStage = scrollPosition - stage;
  if (withinStage <= STABLE_PORTION) return stage;
  return stage + (withinStage - STABLE_PORTION) / (1 - STABLE_PORTION);
}

export function Landing() {
  const setScreen = useStore((state) => state.setScreen);
  const [progress, setProgress] = useState(0);
  const [introReady, setIntroReady] = useState(false);
  const [typedTitle, setTypedTitle] = useState("");
  const progressRef = useRef(0);
  const touchY = useRef<number | null>(null);

  const updateProgress = (next: number) => {
    const value = clamp(next);
    progressRef.current = value;
    setProgress(value);
  };

  useEffect(() => {
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      updateProgress(progressRef.current + event.deltaY / WHEEL_DISTANCE_PER_STAGE);
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    const intro = window.setTimeout(() => setIntroReady(true), 80);
    return () => window.clearTimeout(intro);
  }, []);

  useEffect(() => {
    let character = 0;
    let typing: number | undefined;
    const startTyping = window.setTimeout(() => {
      typing = window.setInterval(() => {
        character += 1;
        setTypedTitle(story[0].title.slice(0, character));
        if (character === story[0].title.length && typing !== undefined) window.clearInterval(typing);
      }, 105);
    }, 460);
    return () => {
      window.clearTimeout(startTyping);
      if (typing !== undefined) window.clearInterval(typing);
    };
  }, []);

  const stageProgress = storyProgress(progress);
  const shownStep = Math.floor(stageProgress) + 1;
  const designToPlan = Math.max(0, Math.min(1, stageProgress - 1));

  return (
    <section
      aria-labelledby="landing-title"
      className="landing-story"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown" || event.key === "PageDown") {
          event.preventDefault();
          updateProgress(Math.ceil(progressRef.current + .01));
        }
        if (event.key === "ArrowUp" || event.key === "PageUp") {
          event.preventDefault();
          updateProgress(Math.floor(progressRef.current - .01));
        }
      }}
      onTouchStart={(event) => { touchY.current = event.touches[0]?.clientY ?? null; }}
      onTouchMove={(event) => {
        const currentY = event.touches[0]?.clientY;
        if (touchY.current === null || currentY === undefined) return;
        updateProgress(progressRef.current + (touchY.current - currentY) / 520);
        touchY.current = currentY;
      }}
      onTouchEnd={() => { touchY.current = null; }}
    >
      <div className="landing-story__stage" aria-hidden="true">
        <div className="landing-story__progress">
          <span>{String(shownStep).padStart(2, "0")}</span>
          <i><b style={{ transform: `scaleX(${(stageProgress + 1) / story.length})` }} /></i>
          <span>04</span>
        </div>
        <div className="landing-story__visual-track">
          {designToPlan > 0 && designToPlan < 1 && <i className="landing-story__swap-panel" style={{ left: `${-46 + designToPlan * 146}%` }} />}
          {story.map((step, index) => <StoryVisual key={step.title} step={step} index={index} progress={stageProgress} introReady={introReady} />)}
        </div>
      </div>
      <div className="landing-story__copy-track">
        {story.map((step, index) => <StoryCopy key={step.title} step={step} index={index} progress={stageProgress} typedTitle={typedTitle} onStart={() => setScreen("capture")} />)}
      </div>
      <p className="landing-story__notice">Guidelines, not code compliance. Check local permit requirements.</p>
    </section>
  );
}

function StoryVisual({ step, index, progress, introReady }: { step: typeof story[number]; index: number; progress: number; introReady: boolean }) {
  const opacity = presence(progress, index);
  const direction = step.side === "left" ? 1 : -1;
  const offset = (progress - index) * direction * -13;
  const y = (progress - index) * -3;
  const captureToDesign = Math.max(0, Math.min(1, progress));
  const isCaptureToDesign = progress >= 0 && progress <= 1 && (index === 0 || index === 1);
  const designToPlan = Math.max(0, Math.min(1, progress - 1));
  const isDesignToPlan = progress >= 1 && progress <= 2 && (index === 1 || index === 2);
  const planToBuild = Math.max(0, Math.min(1, progress - 2));
  const isPlanToBuild = progress >= 2 && progress <= 3 && (index === 2 || index === 3);
  const isStable = Math.abs(progress - index) < .001;
  const style = isCaptureToDesign && index === 0
    ? { opacity: 1, transform: `translate3d(0, 0, 0) scale(${1 - captureToDesign * .28})` }
    : isCaptureToDesign && index === 1
      ? { opacity: captureToDesign, transform: "translate3d(0, 0, 0)" }
      : isDesignToPlan && index === 1
    ? { opacity: 1, transform: `translate3d(${designToPlan * -58}%, 0, 0)` }
    : isDesignToPlan && index === 2
      ? { opacity: designToPlan === 0 ? 0 : 1, transform: `translate3d(${(1 - designToPlan) * 58}%, 0, 0)` }
      : isPlanToBuild && index === 2
        ? { opacity: 1, transform: `translate3d(${planToBuild * 8}%, ${planToBuild * 46}%, 0) rotate(${planToBuild * 5}deg)` }
        : isPlanToBuild && index === 3
          ? { opacity: planToBuild === 0 ? 0 : 1, transform: `translate3d(0, ${(1 - planToBuild) * 70}%, 0) rotate(${(1 - planToBuild) * -4}deg)` }
      : { opacity, transform: `translate3d(${offset}%, ${y}%, 0) scale(${.94 + opacity * .06})` };
  const visibility = isCaptureToDesign && index === 0
    ? captureToDesign >= 1 ? "hidden" : "visible"
    : isCaptureToDesign && index === 1
      ? captureToDesign <= 0 ? "hidden" : "visible"
      : isDesignToPlan && index === 1
    ? designToPlan >= 1 ? "hidden" : "visible"
    : isDesignToPlan && index === 2
      ? designToPlan <= 0 ? "hidden" : "visible"
      : isPlanToBuild && index === 2
        ? planToBuild >= 1 ? "hidden" : "visible"
        : isPlanToBuild && index === 3
          ? planToBuild <= 0 ? "hidden" : "visible"
          : opacity === 0 ? "hidden" : "visible";
  const isIntro = index === 0 && isStable && introReady;

  return (
    <figure
      className={`landing-story__visual landing-story__visual--${step.visual} landing-story__visual--${step.side}${isStable ? " is-stable" : ""}${isIntro ? " is-intro-ready" : ""}`}
      style={{ ...style, visibility }}
    >
      <img src={step.image} alt={step.alt} draggable={false} />
    </figure>
  );
}

function StoryCopy({ step, index, progress, typedTitle, onStart }: { step: typeof story[number]; index: number; progress: number; typedTitle: string; onStart: () => void }) {
  const opacity = presence(progress, index);
  const direction = step.side === "left" ? 1 : -1;
  const offset = (progress - index) * direction * 14;
  const captureToDesign = Math.max(0, Math.min(1, progress));
  const isCaptureToDesign = progress >= 0 && progress <= 1 && (index === 0 || index === 1);
  const style = isCaptureToDesign && index === 0
    ? { opacity: 1, transform: `translate3d(0, 0, 0) scale(${1 - captureToDesign * .2})` }
    : isCaptureToDesign && index === 1
      ? { opacity: captureToDesign, transform: "translate3d(0, 0, 0)" }
      : { opacity, transform: `translate3d(${offset}%, ${(progress - index) * -5}%, 0)` };
  const visibility = isCaptureToDesign && index === 0
    ? captureToDesign >= 1 ? "hidden" : "visible"
    : isCaptureToDesign && index === 1
      ? captureToDesign <= 0 ? "hidden" : "visible"
      : opacity === 0 ? "hidden" : "visible";

  return (
    <article
      className={`landing-story__copy landing-story__copy--${step.side}`}
      style={{ ...style, visibility }}
      aria-hidden={opacity < .04}
    >
      {index === 0
        ? <h1 id="landing-title">{typedTitle}<span className="landing-story__cursor is-typing" aria-hidden="true">_</span></h1>
        : <h2>{step.title}</h2>}
      <p>{step.description}</p>
      {index === MAX_PROGRESS && <button type="button" className="app-button" tabIndex={opacity < .7 ? -1 : 0} onClick={onStart}>Start a project</button>}
    </article>
  );
}
