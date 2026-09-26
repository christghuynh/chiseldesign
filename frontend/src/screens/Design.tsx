import { useStore } from "../store";
import { REFERENCE_STRINGER } from "../three/referenceStringer";
import { Scene } from "../three/Scene";

// Skeleton. FE-6 builds the real screen: parameter panel generated from the template's
// JSON Schema, debounced /generate, rule badges with "Apply fix", push-to-talk and undo/redo.
export function Design() {
  const spec = useStore((s) => s.spec);
  const selectedPartIds = useStore((s) => s.selectedPartIds);
  const setSelected = useStore((s) => s.setSelected);
  const parts = spec?.parts.length ? spec.parts : [REFERENCE_STRINGER];

  return (
    <section aria-labelledby="design-title" className="space-y-4">
      <h2 id="design-title" className="text-2xl font-semibold">
        Design
      </h2>
      <p>
        {spec?.parts.length
          ? `Showing ${spec.parts.length} parts from the loaded spec. Click a part to select it.`
          : "No spec loaded: showing the hardcoded reference stringer. Load the sample from the Capture screen."}
      </p>
      <div className="overflow-hidden rounded border border-slate-300">
        <Scene parts={parts} selectedIds={selectedPartIds} onSelect={(id) => setSelected(id === null ? [] : [id])} height="28rem" />
      </div>
      {selectedPartIds.length > 0 && <p role="status">Selected: {selectedPartIds.join(", ")}</p>}
    </section>
  );
}
