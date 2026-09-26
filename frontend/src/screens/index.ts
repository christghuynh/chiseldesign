import type { ComponentType } from "react";
import type { ScreenKey } from "../store";
import { BuildMode } from "./BuildMode";
import { Capture } from "./Capture";
import { Confirm } from "./Confirm";
import { Design } from "./Design";
import { Landing } from "./Landing";
import { Overlay } from "./Overlay";
import { Plan } from "./Plan";
import { Projects } from "./Projects";

// Owner: P2 (screen registry; each screen file belongs to its own owner).
export const SCREENS: Record<ScreenKey, { label: string; Component: ComponentType }> = {
  landing: { label: "Welcome", Component: Landing },
  capture: { label: "Capture", Component: Capture },
  confirm: { label: "Confirm", Component: Confirm },
  design: { label: "Design", Component: Design },
  plan: { label: "Plan", Component: Plan },
  build: { label: "Build mode", Component: BuildMode },
  projects: { label: "Projects", Component: Projects },
  overlay: { label: "Overlay", Component: Overlay },
};
