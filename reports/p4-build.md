# p4-build report

## Done (tests passing)
- **FE-8 (B1) Build mode** (`b6a5b4d`): on entry it calls `POST /instructions` and then `setSteps` (loading and error states, Try again button). Large-text step view (step n of N, title, text, cut callouts with the matching cut-list row's material and length, safety tip), progress bar, Previous / Repeat / Next buttons, keyboard shortcuts (← → R; ignored with modifiers, while typing in a text field, and on key auto-repeat), the current step's parts highlighted in `Scene` through `uiSlice.setHighlighted` (cleared on exit), a Done screen, and a "no design yet" state. Dev page `/dev/build`.
  Files: `screens/BuildMode.tsx`, `components/build/{navigation.ts,BuildStepView.tsx,BuildProgress.tsx,BuildControls.tsx,BuildDone.tsx}`, `dev/routes/build.tsx`, tests `navigation.test.ts`, `BuildStepView.test.ts`.
- **VOX-6 (B2) Audio prefetch and queue** (`38f8601`): the `BuildAudio` controller (`components/build/audioQueue.ts`) requests TTS for every step in the background, two requests at a time and in step order. The spoken text is the title, the text, and each callout's `spoken`. Object URLs go to `buildSlice.audioUrls`, keyed by `n`. The current step auto-plays; if its audio is still downloading, it waits up to 6 s. Repeat replays the step, and moving to another step stops the current audio (a play that was superseded never starts). New steps or leaving the screen revokes the URLs. A "Read each step aloud" checkbox turns auto-play off; Repeat still plays.
  Files: `components/build/audioQueue.ts`, `hooks/useBuildAudio.ts`, `screens/BuildMode.tsx`, test `audioQueue.test.ts`.
- **VOX-7b (B3) Browser speech fallback** (`79be815`): `speechSynthesis` reads the step when TTS returns 501/404/503 or the network fails (remaining requests are skipped), when a single step's TTS fails, when the audio element won't play, when the audio takes longer than 6 s, and always in fixture mode (no TTS requests are made). Each sentence is a separate utterance, to avoid Chrome's ~15 s cutoff. Browsers without speech synthesis stay silent instead of throwing. Since `/voice/tts` currently returns 501, this is the path that runs today.
  Files: `components/build/speech.ts`, `hooks/useBuildAudio.ts`, tests `speech.test.ts`, `audioQueue.test.ts`.
- **VOX-5 (B4) Build-mode voice commands** (`20b2cef`): P2's `PushToTalk` goes to `onTranscript`, and the transcript is matched locally against whole words: next/forward/continue, back/previous, repeat/again, stop/pause/quiet (first keyword wins). Unknown phrases get a spoken "Say next, back, or repeat." The last heard phrase is shown in a live status region.
  Files: `components/build/voiceCommands.ts`, `screens/BuildMode.tsx`, test `voiceCommands.test.ts`.

`make test`: 146 backend, 155 frontend (77 new), and `tsc` all pass. `vite build` passes.
Checked in Chrome on `/dev/build` with fixtures: steps render, → moves forward, the callouts show cut-list lengths, the 3D view renders, and the Done screen appears after the last step. No console errors.

## Failed / partial
- None. **B5 (FE-11 Auth + Projects) was not started**, because the Auth0 tenant doesn't exist yet (owner's instruction).
- Not verified by ear: actual audio playback and speech in a browser, which the tool can't hear. The logic is covered by unit tests with fakes.
- Voice commands can't be tried end to end yet, because `PushToTalk` is still P2's disabled stub (VOX-3). The matching and dispatch are unit-tested.

## Questions logged
- VOX-6: where the TTS client call should live. See QUESTIONS.md.
- FE-8: the part highlight is faint (Scene/PartMesh, P2).
- FE-8: placeholder safety text on the Done screen.

## New dependencies
- None.

## Check this in the morning
- Once VOX-2 lands, check `/voice/tts` playback on the real backend: the first step should play within a few seconds, and Next should cut off the audio right away.
- Once VOX-3 lands, check in Build mode that the PushToTalk spacebar hotkey doesn't clash with anything. Build mode itself only uses ← → R.
- Instructions are fetched again every time Build mode opens, so progress starts back at step 1. Tell me if progress should be kept across visits.
- `frontend/package-lock.json` has local drift from `npm install` (removed `"peer": true` flags). It's left uncommitted because it isn't part of this lane.
