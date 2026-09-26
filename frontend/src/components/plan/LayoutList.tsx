// Owner: P4. Every cutting layout, grouped by material, one LayoutSvg per stock piece.
import type { StockLayout } from "../../types";
import { LayoutSvg } from "./LayoutSvg";

export interface LayoutListProps {
  layouts: StockLayout[];
  highlightedLabel?: string | null;
}

export function LayoutList({ layouts, highlightedLabel = null }: LayoutListProps) {
  const byMaterial = new Map<string, StockLayout[]>();
  for (const layout of layouts) byMaterial.set(layout.material, [...(byMaterial.get(layout.material) ?? []), layout]);

  return (
    <div className="space-y-6">
      {[...byMaterial].map(([material, group]) => (
        <section key={material} aria-label={`${material} layouts`} className="layout-group">
          <h4 className="mb-2 font-semibold">
            {material} <span className="font-normal text-slate-600">({group.length} {group[0].kind === "sheet" ? "sheets" : "boards"})</span>
          </h4>
          <ul className="grid gap-4 md:grid-cols-2">
            {group.map((layout) => (
              <li key={layout.stock_id}>
                <LayoutSvg layout={layout} highlightedLabel={highlightedLabel} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
