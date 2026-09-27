// Owner: P4. One stock piece (board or sheet) with its cut pieces; waste is hatched.
import { useId } from "react";
import type { StockLayout } from "../../types";
import { formatFraction, formatFtIn } from "../../util/units";
import { formatPercent } from "./format";
import { layoutGeometry } from "./layoutGeometry";

export interface LayoutSvgProps {
  layout: StockLayout;
  /** Pieces with this label are drawn emphasized (the selected cut-list row). */
  highlightedLabel?: string | null;
}

export function stockName(layout: StockLayout): string {
  return layout.kind === "sheet"
    ? `${layout.material}, ${formatFraction(layout.width_in)}" × ${formatFraction(layout.length_in)}" sheet`
    : `${layout.material}, ${formatFtIn(layout.length_in)} board`;
}

export function LayoutSvg({ layout, highlightedLabel = null }: LayoutSvgProps) {
  const hatchId = `waste-${useId().replace(/:/g, "")}`;
  const g = layoutGeometry(layout);
  const name = stockName(layout);
  const used = formatPercent(layout.utilization);
  const summary = `${name}: ${layout.pieces.map((p) => p.label).join(", ") || "no pieces"}; ${used} used`;

  return (
    <figure className="layout-svg space-y-1">
      <figcaption className="flex flex-wrap justify-between gap-2 text-sm">
        <span className="font-medium">{name}</span>
        <span>{used} used</span>
      </figcaption>
      <svg viewBox={`0 0 ${g.width} ${g.height}`} width="100%" role="img" aria-label={summary} className="block">
        <defs>
          <pattern id={hatchId} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" fill="#e8eef2" />
            <line x1="0" y1="0" x2="0" y2="8" stroke="#8a9299" strokeWidth="3" />
          </pattern>
        </defs>
        <rect data-stock x={0} y={0} width={g.width} height={g.height} fill={`url(#${hatchId})`} stroke="#33587a" strokeWidth="2" />
        {g.pieces.map((p) => {
          const highlighted = p.label === highlightedLabel;
          const text = p.w >= 70 ? `${p.label} · ${formatFraction(p.lengthIn)}"` : p.w >= 16 ? p.label : null;
          return (
            <g key={p.partId}>
              <rect
                data-piece={p.partId}
                x={p.x}
                y={p.y}
                width={p.w}
                height={p.h}
                fill={highlighted ? "#77b6ea" : "#dbeaf7"}
                stroke={highlighted ? "#37393a" : "#33587a"}
                strokeWidth={highlighted ? 3 : 1.5}
              >
                <title>{`${p.partId}: ${formatFraction(p.lengthIn)}"`}</title>
              </rect>
              {text && (
                <text
                  x={p.x + p.w / 2}
                  y={p.y + p.h / 2}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize="16"
                  fill="#37393a"
                  aria-hidden="true"
                >
                  {text}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
