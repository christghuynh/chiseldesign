// Owner: P4. The cut list, one row per label. Clicking a row (or Enter/Space on it) selects that label.
import type { KeyboardEvent } from "react";
import type { CutListRow } from "../../types";

export interface CutListTableProps {
  rows: CutListRow[];
  selectedLabel?: string | null;
  onRowSelect?: (label: string) => void;
}

export function CutListTable({ rows, selectedLabel = null, onRowSelect }: CutListTableProps) {
  const onKeyDown = (e: KeyboardEvent, label: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onRowSelect?.(label);
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">
          Cut list{onRowSelect ? ". Select a row to highlight its parts in the 3D view." : ""}
        </caption>
        <thead>
          <tr className="border-b-2 border-slate-400">
            <th scope="col" className="px-2 py-2">Label</th>
            <th scope="col" className="px-2 py-2">Part</th>
            <th scope="col" className="px-2 py-2">Material</th>
            <th scope="col" className="px-2 py-2">Actual size (in)</th>
            <th scope="col" className="px-2 py-2">Length</th>
            <th scope="col" className="px-2 py-2 text-right">Qty</th>
            <th scope="col" className="px-2 py-2">Cut notes</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const selected = row.label === selectedLabel;
            return (
              <tr
                key={row.label}
                data-label={row.label}
                tabIndex={onRowSelect ? 0 : undefined}
                aria-current={selected ? "true" : undefined}
                onClick={onRowSelect ? () => onRowSelect(row.label) : undefined}
                onKeyDown={onRowSelect ? (e) => onKeyDown(e, row.label) : undefined}
                className={`border-b border-slate-200 align-top ${onRowSelect ? "cursor-pointer" : ""} ${selected ? "bg-amber-100" : onRowSelect ? "hover:bg-slate-50" : ""}`}
              >
                <th scope="row" className="px-2 py-2 font-bold">{row.label}</th>
                <td className="px-2 py-2">{row.name}</td>
                <td className="px-2 py-2">{row.material}</td>
                <td className="px-2 py-2 whitespace-nowrap">{row.actual_dims}</td>
                <td className="px-2 py-2 whitespace-nowrap">{row.length_display}</td>
                <td className="px-2 py-2 text-right">{row.qty}</td>
                <td className="px-2 py-2">
                  {row.cut_notes.length > 0 && (
                    <ul className="space-y-1">
                      {row.cut_notes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
