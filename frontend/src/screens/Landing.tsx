import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useStore } from "../store";

type StoryStep = 0 | 1 | 2 | 3;

const story = [
  { eyebrow: "01 · Capture", title: "Start with a sketch.", description: "A rough drawing, a photo of your space, or a starting template is enough to begin.", side: "left" },
  { eyebrow: "02 · Design", title: "Shape it in 3D.", description: "Adjust the dimensions that matter and watch the design respond before you buy a board.", side: "right" },
  { eyebrow: "03 · Plan", title: "Plan every cut.", description: "See the materials, the cut list, and how each piece fits on the boards you need.", side: "left" },
  { eyebrow: "04 · Build", title: "Build with a clear next step.", description: "Take a practical, part-by-part guide with you to the workshop.", side: "right" },
] as const;

export function Landing() {
  const setScreen = useStore((state) => state.setScreen);
  const storyRef = useRef<HTMLElement>(null);
  const [activeStep, setActiveStep] = useState<StoryStep>(0);
  const reduceMotion = useReducedMotion();
  const [touchStart, setTouchStart] = useState<number | null>(null);

  function move(direction: 1 | -1) {
    setActiveStep((current) => Math.max(0, Math.min(story.length - 1, current + direction)) as StoryStep);
  }

  useEffect(() => {
    let distance = 0;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      distance += event.deltaY;
      if (Math.abs(distance) < 65) return;
      move(distance > 0 ? 1 : -1);
      distance = 0;
    };
    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
  }, []);

  const step = story[activeStep];

  return (
    <section ref={storyRef} aria-labelledby="landing-title" className="landing-story" tabIndex={0} onKeyDown={(event) => {
      if (event.key === "ArrowDown" || event.key === "PageDown") { event.preventDefault(); move(1); }
      if (event.key === "ArrowUp" || event.key === "PageUp") { event.preventDefault(); move(-1); }
    }} onTouchStart={(event) => setTouchStart(event.touches[0]?.clientY ?? null)} onTouchEnd={(event) => {
      if (touchStart === null) return;
      const distance = touchStart - (event.changedTouches[0]?.clientY ?? touchStart);
      if (Math.abs(distance) > 45) move(distance > 0 ? 1 : -1);
      setTouchStart(null);
    }}>
      <div className="landing-story__stage" aria-hidden="true">
        <div className="landing-story__progress">
          <span>{String(activeStep + 1).padStart(2, "0")}</span>
          <i><b style={{ transform: `scaleX(${(activeStep + 1) / story.length})` }} /></i>
          <span>04</span>
        </div>
        <div className="landing-story__visual-track">
          <AnimatePresence mode="wait">
            <StoryVisual key={activeStep} step={activeStep} reduceMotion={Boolean(reduceMotion)} />
          </AnimatePresence>
        </div>
      </div>
      <div className={`landing-story__copy-track landing-story__copy-track--${step.side}`}>
        <AnimatePresence mode="wait">
          <motion.article key={step.eyebrow} className="landing-story__copy" initial={{ opacity: 0, x: step.side === "left" ? -42 : 42, y: 16 }} animate={{ opacity: 1, x: 0, y: 0 }} exit={{ opacity: 0, x: step.side === "left" ? -28 : 28, y: -12 }} transition={{ duration: reduceMotion ? 0 : .58, ease: [0.22, 1, 0.36, 1] }}>
            <p className="landing-story__eyebrow">{step.eyebrow}</p>
            {activeStep === 0 ? <h1 id="landing-title">{step.title}</h1> : <h2>{step.title}</h2>}
            <p>{step.description}</p>
            {activeStep === 3 && <button type="button" className="app-button" onClick={() => setScreen("capture")}>Start a project</button>}
          </motion.article>
        </AnimatePresence>
      </div>
      <p className="landing-story__notice">Guidelines, not code compliance. Check local permit requirements.</p>
    </section>
  );
}

function StoryVisual({ step, reduceMotion }: { step: StoryStep; reduceMotion: boolean }) {
  const transition = reduceMotion ? { duration: 0 } : { duration: 0.62, ease: [0.22, 1, 0.36, 1] as const };
  return (
    <motion.div className={`landing-story__visual landing-story__visual--${step}`} initial={{ opacity: 0, scale: 0.96, y: 28 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98, y: -22 }} transition={transition}>
      {step === 0 && <SketchVisual reduceMotion={reduceMotion} />}
      {step === 1 && <DesignVisual />}
      {step === 2 && <PlanVisual />}
      {step === 3 && <BuildVisual reduceMotion={reduceMotion} />}
    </motion.div>
  );
}

function SketchVisual({ reduceMotion }: { reduceMotion: boolean }) {
  const draw = { pathLength: 1, opacity: 1 };
  return <div className="story-sketch"><div className="story-sketch__paper"><span>PORCH PLATFORM</span><motion.svg viewBox="0 0 600 420" fill="none" xmlns="http://www.w3.org/2000/svg"><motion.path initial={{ pathLength: reduceMotion ? 1 : 0, opacity: reduceMotion ? 1 : 0 }} animate={draw} transition={{ duration: .9, ease: "easeInOut" }} d="M112 317 271 227 468 313 304 400 112 317Z M271 227v-106l197 86v106M112 317V210l159-89M112 210l192 86 164-89M304 296v104" className="story-line"/><motion.path initial={{ pathLength: reduceMotion ? 1 : 0, opacity: reduceMotion ? 1 : 0 }} animate={draw} transition={{ duration: .74, delay: .18 }} d="M160 186v122M219 154v121M339 150v121M400 178v121M96 346h188M334 345l124-71M165 116h106M478 322l66-38" className="story-line story-line--thin"/><motion.path initial={{ pathLength: reduceMotion ? 1 : 0, opacity: reduceMotion ? 1 : 0 }} animate={draw} transition={{ duration: .62, delay: .42 }} d="M142 98h77m-38-32v65M490 287v67m-33-34h66" className="story-line story-line--measure"/></motion.svg><b>48 in × 36 in</b></div></div>;
}

function DesignVisual() {
  return <div className="story-window story-window--design"><WindowBar label="Design workspace"/><div className="story-window__design-body"><div className="story-mini-panel"><b>Key dimensions</b><span>Height <strong>34 in</strong></span><span>Width <strong>48 in</strong></span><span>Depth <strong>24 in</strong></span></div><div className="story-model"><i/><svg viewBox="0 0 420 290" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="m88 207 141-80 132 57-142 81-131-58Z" className="story-model__top"/><path d="m88 207 131 58v-42L88 166v41Zm131 58 142-81v-39l-142 78v42Z" className="story-model__edge"/><path d="m118 194 29 13v-83l-29-13v83Zm182-100 29 13v85l-29-13V94Zm-149 129 26 11v-76l-26-11v76Zm113-64 26 12v76l-26-12v-76Z" className="story-model__legs"/><path d="m120 127 140 60M153 109l140 60M183 92l140 61M213 75l139 60" className="story-model__grain"/></svg><em>Live 3D model</em></div></div></div>;
}

function PlanVisual() {
  return <div className="story-window story-window--plan"><WindowBar label="Build plan"/><div className="story-window__plan-body"><div className="story-cut-list"><b>Cut list</b>{[["A-1", "2 × 4 · 45 in"], ["A-2", "2 × 4 · 21 in"], ["B-1", "1 × 6 · 48 in"], ["B-2", "1 × 6 · 24 in"]].map(([label, detail]) => <span key={label}><i>{label}</i>{detail}</span>)}</div><div className="story-layout"><b>Board layout</b><svg viewBox="0 0 270 186" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="16" y="18" width="238" height="148" rx="10" className="story-layout__board"/><path d="M44 18v148m93-148v148m71-148v148M16 76h238m-238 45h238" className="story-layout__cut"/><path d="M50 47h80m-80 88h154m-65-58h76" className="story-layout__label"/></svg><small>4 boards · 86% used</small></div></div></div>;
}

function BuildVisual({ reduceMotion }: { reduceMotion: boolean }) {
  return <div className="story-window story-window--build"><WindowBar label="Build mode"/><div className="story-window__build-body"><div className="story-build-model"><svg viewBox="0 0 270 245" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="m45 171 89-51 91 39-90 53-90-41Z" className="story-build-model__top"/><path d="m45 171 90 41v-28l-90-41v28Zm90 41 90-53v-26l-90 51v28Z" className="story-build-model__edge"/><path d="M72 159v-55m36 71v-55m64 24V89m31 40v-55" className="story-build-model__legs"/></svg><em>Part A-1 highlighted</em></div><div className="story-checklist"><b>Assemble the frame</b><p>Secure the long rails to both end frames.</p>{["Gather parts A-1 to A-4", "Clamp the first frame square", "Drive exterior screws"].map((item, index) => <motion.span key={item} initial={{ opacity: reduceMotion ? 1 : 0, x: reduceMotion ? 0 : 18 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: reduceMotion ? 0 : .22 + index * .13 }}><i>{index === 0 ? "✓" : index + 1}</i>{item}</motion.span>)}</div></div></div>;
}

function WindowBar({ label }: { label: string }) {
  return <div className="story-window__bar"><i/><i/><i/><span>{label}</span></div>;
}
