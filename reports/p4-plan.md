# p4-plan report

## Done (tests passing)
- FE-7a (A1): props-only Plan components and the `/dev/plan` page — `frontend/src/components/plan/{SummaryCard,CutListTable,LayoutSvg,LayoutList,ShoppingList,SafetyNotice}.tsx`, `layoutGeometry.ts`, `format.ts`, `plan.test.ts`, `frontend/src/dev/routes/plan.tsx`.
  - LayoutSvg scales each stock piece to fit (boards get a minimum drawing height so labels fit; sheets keep their aspect ratio), labels pieces, hatches waste and shows utilization. Pieces are clamped so nothing draws outside the stock.
  - When `plan.has_placeholder_prices` is set, SummaryCard shows "Estimated total" with `~` and an "Estimate" tag, and ShoppingList says "Estimated total" plus a note that prices are placeholders.
  - Tests: one rect per piece and nothing outside the stock for all 58 fixture layouts; ShoppingList subtotal/tax/total match both fixtures, and the HST toggle works; a CutListTable row click (and Enter) fires with the label; SummaryCard rule status, savings and the estimate label.
- FE-7b (A2): Plan screen wiring — `frontend/src/screens/Plan.tsx`, `Plan.test.ts`. Reads `spec` and `plan` from the store. Selecting a row calls `setHighlighted(row.part_ids)` (a second click clears it), and clicking a part in the Scene selects its row. The screen has "Start building" → `build` and "Back to design" → `design`, plus an empty state when there's no plan. It uses P2's `Scene` directly (it's on main).
- FE-10 (A3): downloads and printing — `frontend/src/components/plan/{exports.ts,Downloads.tsx,print.css,downloads.test.ts}`. STEP, STL and CSV `POST /api/export/*` and save the blob with a filename built from the template and layout. In fixture mode STEP/STL are `aria-disabled` with a tooltip and a visible hint, and the CSV is built locally from `plan.cut_list`. Errors show in a `role="alert"` box. "Print plan" calls `window.print()`. The print stylesheet (only while `#plan-screen` is on the page) hides the header, nav, Scene, buttons and HST toggle, and prints the summary, cut list, layouts, shopping list and safety notice.
- `make test`: 146 backend and 165 frontend tests pass, `tsc` is clean and `vite build` succeeds.
- Checked in Chrome with `npm run dev:fixtures`: `/dev/plan` renders both fixtures, and the in-app Plan screen (Capture → load sample → Plan) highlights a row's parts in the Scene. Fixture mode shows STEP/STL as disabled.

## Failed / partial
- None. Not checked by eye: the actual print preview (the print CSS is untested in a browser) and a real STEP/STL download (the backend routes still return 501 until GEO-17/GEO-18; the UI shows that error).

## Questions logged
- FE-10: export client location and CSV columns — see QUESTIONS.md
- FE-7: Plan clears the 3D highlight on mount and unmount — see QUESTIONS.md

## New dependencies
- Frontend dev dependencies: `jsdom`, `@testing-library/react`, `@testing-library/dom`. Tests opt in per file with `// @vitest-environment jsdom`. The vitest config is unchanged, so tests stay `.test.ts` and use `createElement`. Lane B will likely want the same packages, so expect a `package-lock.json` merge conflict; resolve it by re-running `npm install`.

## Check this in the morning
- The export calls live in `components/plan/exports.ts` rather than P2's `api/client.ts` (see QUESTIONS.md).
- Print preview (Cmd+P on the Plan screen) in Chrome and Safari.
- SummaryCard's key dimensions are per template (`KEY_PARAMS`, ramp only). Other templates fall back to their first four params.
- When GEO-16 replaces the fixtures, the estimate label disappears once `has_placeholder_prices` is false (a test covers this).
