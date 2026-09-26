# Questions

### VOX-6 — Where should the TTS client call live? (p4 Lane B, 2026-09-26)
Question: `POST /voice/tts` returns audio, not JSON, and `api/client.ts` (P2's file) only has JSON helpers. Build mode needs the call now.
Options I see: A) P2 adds `api.tts(text): Promise<Blob>` to `client.ts` and Build mode switches to it. B) Keep it in P4's `hooks/useBuildAudio.ts` (`fetchTts`).
What I did meanwhile: B. `fetchTts` in `frontend/src/hooks/useBuildAudio.ts` throws the client's `ApiError`, so moving it later is a one-line import change.

### FE-8 — Part highlight is hard to see in Build mode (p4 Lane B, 2026-09-26)
Question: Build mode passes the current step's part ids to `Scene` as `highlightedIds`. With the skeleton `PartMesh` (amber emissive tint), the highlighted parts barely stand out in the small view.
Options I see: A) P2 makes the highlight stronger in FE-5 (outline, or dim the parts that aren't highlighted). B) Build mode passes the ids as `selectedIds` too (blue).
What I did meanwhile: kept `highlightedIds` only, as the spec says. Nothing to change on my side if A happens.

### FE-8 — Wording on the Done screen (p4 Lane B, 2026-09-26)
Question: The Done screen says "Walk the ramp slowly once before anyone relies on it, and check every fastener." That's placeholder safety text I wrote. Should it come from the rules/safety copy (NC-3), and should it depend on the template?
What I did meanwhile: left the placeholder in `frontend/src/components/build/BuildDone.tsx`.
