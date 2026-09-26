// Owner: P4. Maps one StockLayout (inches) to SVG pixel coordinates for LayoutSvg.
import type { StockLayout } from "../../types";

export interface PieceRect {
  label: string;
  partId: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** Piece length along the stock, in inches (for the label). */
  lengthIn: number;
}

export interface LayoutGeometry {
  width: number;
  height: number;
  pieces: PieceRect[];
}

export interface LayoutGeometryOptions {
  /** Drawing width in px (the SVG scales it to fit its container). */
  width?: number;
  /** Boards are long and thin; stretch their width axis so labels fit. */
  minHeight?: number;
}

/**
 * Scale the stock to `width` px. Sheets keep their aspect ratio; boards get their short axis
 * stretched to at least `minHeight` px. Pieces are clamped to the stock, so nothing is ever drawn
 * outside it even if a layout is off by a rounding error.
 */
export function layoutGeometry(layout: StockLayout, { width = 600, minHeight = 44 }: LayoutGeometryOptions = {}): LayoutGeometry {
  const sx = width / layout.length_in;
  const sy = Math.max(sx, minHeight / layout.width_in);
  const height = layout.width_in * sy;

  const pieces = layout.pieces.map((p) => {
    const x0 = clamp(p.x, 0, layout.length_in);
    const y0 = clamp(p.y, 0, layout.width_in);
    const x1 = clamp(p.x + p.w, 0, layout.length_in);
    const y1 = clamp(p.y + p.h, 0, layout.width_in);
    return { label: p.label, partId: p.part_id, x: x0 * sx, y: y0 * sy, w: (x1 - x0) * sx, h: (y1 - y0) * sy, lengthIn: p.w };
  });

  return { width, height, pieces };
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}
