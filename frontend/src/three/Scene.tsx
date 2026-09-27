// Owner: P2. Other screens (Plan, Build mode) render this component, so SceneProps is a contract:
// changing it must be announced.
import { Bounds, OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useMemo, useState } from "react";
import type { Part } from "../types";
import { PartMesh } from "./PartMesh";

export interface SceneProps {
  parts: Part[];
  /** Parts drawn with a glow. */
  highlightedIds?: string[];
  /** Parts drawn as selected. */
  selectedIds?: string[];
  /** Called with the clicked part's id, or null when the background is clicked. */
  onSelect?: (partId: string | null) => void;
  /** Orbit controls on or off (default true). */
  interactive?: boolean;
  /** CSS height of the scene (default "100%"). */
  height?: number | string;
  /** Optional canvas background color. Defaults to the active theme's scene color. */
  background?: string;
  /** Whether the built-in reset control is shown (default true). */
  showReset?: boolean;
}

// Skeleton: fixed camera, ground grid and axes. Y is up; +X is travel up the ramp, +Z is the
// walker's right. The axes helper draws X red, Y green, Z blue so the frame is visible.
// preserveDrawingBuffer lets a caller capture the canvas as a project thumbnail.
// FE-5 adds auto-framing to the model bounds.
export function Scene({ parts, highlightedIds = [], selectedIds = [], onSelect, interactive = true, height = "100%", background, showReset = true }: SceneProps) {
  const highlighted = useMemo(() => new Set(highlightedIds), [highlightedIds]);
  const selected = useMemo(() => new Set(selectedIds), [selectedIds]);
  const [viewKey, setViewKey] = useState(0);
  const dark = document.documentElement.dataset.theme === "dark";
  const lightCanvas = background !== undefined || !dark;

  return (
    <div style={{ height, width: "100%", position: "relative" }}>
      {interactive && showReset && <button type="button" className="app-button app-button--secondary absolute right-3 top-3 z-10 text-sm" onClick={() => setViewKey((key) => key + 1)}>Reset view</button>}
      <Canvas
        camera={{ position: [220, 140, 260], fov: 45, near: 1, far: 5000 }}
        gl={{ preserveDrawingBuffer: true }}
        onPointerMissed={onSelect ? () => onSelect(null) : undefined}
        aria-label="3D model of the ramp"
      >
        <color attach="background" args={[background ?? (dark ? "#232526" : "#e8eef2")]} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[200, 300, 150]} intensity={1.2} />
        <gridHelper args={[600, 50, lightCanvas ? "#8a9299" : "#6b7075", lightCanvas ? "#d3dce3" : "#37393a"]} />
        <axesHelper args={[60]} />
        <Bounds key={viewKey} fit clip observe margin={1.3}>
          {parts.map((part) => (
            <PartMesh
              key={part.id}
              part={part}
              highlighted={highlighted.has(part.id)}
              selected={selected.has(part.id)}
              onSelect={onSelect}
            />
          ))}
        </Bounds>
        <OrbitControls enabled={interactive} makeDefault enableDamping={!window.matchMedia("(prefers-reduced-motion: reduce)").matches} />
      </Canvas>
    </div>
  );
}
