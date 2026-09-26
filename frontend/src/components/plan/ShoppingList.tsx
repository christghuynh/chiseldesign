// Owner: P4. Shopping list with subtotal, an HST toggle and the total. Every number comes from the plan.
import { useId, useState } from "react";
import type { ShoppingItem } from "../../types";
import { formatCad } from "./format";

export interface ShoppingListProps {
  items: ShoppingItem[];
  subtotal: number;
  /** 13% HST on the subtotal, as computed by the backend. */
  tax: number;
  /** Subtotal plus tax. */
  total: number;
  /** `plan.has_placeholder_prices`: label the total as an estimate. */
  estimate?: boolean;
  /** Initial state of the HST toggle (default on). */
  defaultIncludeTax?: boolean;
}

export function ShoppingList({ items, subtotal, tax, total, estimate = false, defaultIncludeTax = true }: ShoppingListProps) {
  const [includeTax, setIncludeTax] = useState(defaultIncludeTax);
  const toggleId = useId();
  const shownTotal = includeTax ? total : subtotal;

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">Shopping list</caption>
          <thead>
            <tr className="border-b-2 border-slate-400">
              <th scope="col" className="px-2 py-2">Item</th>
              <th scope="col" className="px-2 py-2 text-right">Qty</th>
              <th scope="col" className="px-2 py-2 text-right">Unit price</th>
              <th scope="col" className="px-2 py-2 text-right">Subtotal</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.key} className="border-b border-slate-200">
                <th scope="row" className="px-2 py-2 font-normal">
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer" className="underline">
                      {item.description}
                    </a>
                  ) : (
                    item.description
                  )}
                </th>
                <td className="px-2 py-2 text-right whitespace-nowrap">
                  {item.qty} {item.unit}
                </td>
                <td className="px-2 py-2 text-right">{formatCad(item.unit_price)}</td>
                <td className="px-2 py-2 text-right">{formatCad(item.subtotal)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={3} className="px-2 pt-3 text-right font-medium">Subtotal</th>
              <td data-testid="shopping-subtotal" className="px-2 pt-3 text-right">{formatCad(subtotal)}</td>
            </tr>
            {includeTax && (
              <tr>
                <th scope="row" colSpan={3} className="px-2 text-right font-medium">HST (13%)</th>
                <td data-testid="shopping-tax" className="px-2 text-right">{formatCad(tax)}</td>
              </tr>
            )}
            <tr className="text-lg">
              <th scope="row" colSpan={3} className="px-2 pt-1 text-right font-bold">
                {estimate ? "Estimated total" : "Total"} {includeTax ? "(with HST)" : "(before tax)"}
              </th>
              <td data-testid="shopping-total" className="px-2 pt-1 text-right font-bold">{formatCad(shownTotal)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <label htmlFor={toggleId} className="print-hide inline-flex min-h-11 cursor-pointer items-center gap-2">
        <input id={toggleId} type="checkbox" checked={includeTax} onChange={(e) => setIncludeTax(e.target.checked)} className="size-5" />
        Include 13% HST
      </label>
      {estimate && (
        <p className="rounded border border-amber-400 bg-amber-50 px-3 py-2">
          Some prices are placeholders, so this total is an estimate. Check current prices at your store.
        </p>
      )}
    </div>
  );
}
