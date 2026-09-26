import { useEffect, useMemo } from "react";
import type { Part } from "../types";
import { partGeometry } from "./geometry";

interface Props {
  part: Part;
  highlighted?: boolean;
  selected?: boolean;
  onSelect?: (partId: string) => void;
}

const COLOR = "#c9a66b";
const SELECTED_COLOR = "#3b82f6";
const HIGHLIGHT_EMISSIVE = "#f59e0b";

// Skeleton: geometry, placement and basic highlight/select. FE-5 adds materials by lumber type,
// hover states and outlines.
export function PartMesh({ part, highlighted = false, selected = false, onSelect }: Props) {
  const geometry = useMemo(() => partGeometry(part), [part]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh
      geometry={geometry}
      position={part.transform.pos}
      rotation={part.transform.rot}
      onClick={
        onSelect
          ? (event) => {
              event.stopPropagation();
              onSelect(part.id);
            }
          : undefined
      }
    >
      <meshStandardMaterial
        color={selected ? SELECTED_COLOR : COLOR}
        emissive={highlighted ? HIGHLIGHT_EMISSIVE : "#000000"}
        emissiveIntensity={highlighted ? 0.6 : 0}
      />
    </mesh>
  );
}
