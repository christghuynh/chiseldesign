/** Decorative blueprint treatment for the landing page; it conveys planning without presenting dimensions as build data. */
export function HeroIllustration() {
  return (
    <div className="hero-illustration" aria-hidden="true">
      <svg viewBox="0 0 560 430" role="presentation">
        <defs>
          <linearGradient id="blueprint-glow" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="currentColor" stopOpacity=".15" />
            <stop offset="1" stopColor="currentColor" stopOpacity=".03" />
          </linearGradient>
        </defs>
        <rect x="56" y="42" width="410" height="320" rx="34" className="hero-illustration__panel" />
        <path d="M91 104H431M91 154H431M91 204H431M91 254H431M91 304H431M142 74V331M212 74V331M282 74V331M352 74V331M422 74V331" className="hero-illustration__grid" />
        <path d="M112 292H181L318 155H405" className="hero-illustration__ramp" />
        <path d="M112 311H190L327 174H405" className="hero-illustration__ramp hero-illustration__ramp--light" />
        <path d="M134 292V311M181 292V311M228 245V265M274 198V219M318 155V174M363 155V174M405 155V174" className="hero-illustration__detail" />
        <path d="M144 266V210H180M198 236V180H234M252 181V126H288M306 126V89H342" className="hero-illustration__rail" />
        <circle cx="112" cy="292" r="10" className="hero-illustration__node" />
        <circle cx="405" cy="155" r="10" className="hero-illustration__node" />
        <path d="M100 340H418M100 340l11-7M100 340l11 7M418 340l-11-7M418 340l-11 7" className="hero-illustration__detail" />
        <path d="M438 95h30M453 80v30M455 269h31M470 254v30" className="hero-illustration__spark" />
        <path d="M71 67h14M78 60v14" className="hero-illustration__spark" />
      </svg>
      <div className="hero-orb hero-orb--one" />
      <div className="hero-orb hero-orb--two" />
    </div>
  );
}
