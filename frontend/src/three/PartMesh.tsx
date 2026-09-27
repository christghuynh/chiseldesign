import { useEffect, useMemo, useState } from "react";
import type { Part } from "../types";
import { partGeometry } from "./geometry";

interface Props {
  part: Part;
  highlighted?: boolean;
  selected?: boolean;
  onSelect?: (partId: string) => void;
}

const MATERIAL_COLORS: Record<string, string> = {
  "2x4_PT": "#b77945",
  "2x6_PT": "#aa6f3c",
  "2x8_PT": "#985b2f",
  "4x4_PT": "#79522e",
  "5/4x6_PT_deck": "#d0a15d",
  "3/4_ext_ply": "#d8bd7e",
};
const SELECTED_COLOR = "#7d80da"; // palette: soft periwinkle
const HIGHLIGHT_EMISSIVE = "#b0a3d4"; // palette: wisteria

// Skeleton: geometry, placement and basic highlight/select. FE-5 adds materials by lumber type,
// hover states and outlines.
export function PartMesh({ part, highlighted = false, selected = false, onSelect }: Props) {
  const geometry = useMemo(() => partGeometry(part), [part]);
  const [hovered, setHovered] = useState(false);
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
      onPointerOver={(event) => { event.stopPropagation(); setHovered(true); document.body.style.cursor = onSelect ? "pointer" : "default"; }}
      onPointerOut={() => { setHovered(false); document.body.style.cursor = "default"; }}
    >
      <meshStandardMaterial
        color={selected ? SELECTED_COLOR : MATERIAL_COLORS[part.material] ?? "#c9a66b"}
        emissive={highlighted || hovered ? HIGHLIGHT_EMISSIVE : "#000000"}
        emissiveIntensity={highlighted ? 0.65 : hovered ? 0.3 : 0}
      />
    </mesh>
  );
}
