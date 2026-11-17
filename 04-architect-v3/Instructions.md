## Open the game

Unzip the project, keep `Architect_V3.html` and `ops_room.jpg` in the same folder, and open `Architect_V3.html` in a browser. The game itself needs no installation, server, API key, AI service, or internet connection.

A separate, ready-to-open download named `Architect_V3.html` is also provided outside this ZIP. That standalone download has the exact same game code and embeds the artwork, so it does not need the separate JPG. The HTML inside this project folder uses the JPG reference to keep the editable source compact.

## What changed from V2

The game now has five decisions with three choices each: bottleneck, query regression, login attack, recovery backlog, and return to launch traffic. All scenario prompts, answer labels, consequences, score effects, post-choice metrics, and debrief lines come from Duke's specification.

The engine tracks all 21 flags named by the choices and conditional rules, including the auxiliary flags omitted from the Word document's shorter flag-summary table. Scene 2 inherits Scene 1's post-choice environment and uses its alternate prompt after early diagnosis. Scenes 3, 4, and 5 update their environment panels at scene load. Scene 5 selects the specified safe or risky outcome without inventing additional fixes.

Scores start at 50 and are clamped to 0-100 after each choice. Ending rules use explicit incident facts before score thresholds. The Aftermath Report shows the exact ending summary, all five scores, and the five chronological debrief lines with their choice IDs.

Choice callbacks are guarded against repeated or stale events. A 450-millisecond interaction guard stops an accidental second click from landing on the newly displayed Continue button. This is not a gameplay timer and does not affect scores or incident logic. Play Again resets every score, flag, log entry, and scene state.

## Where to edit

The HTML contains three labeled sections:

1. `scenario-data`: exact scenario data as JSON.
2. `game-engine`: deterministic state transitions, scoring, environment rules, and ending priority.
3. `game-interface`: DOM rendering, interaction guards, image fallback, and replay.

Keep scenario wording and cloud behavior aligned with Duke's approved specification. No visual redesign or additional scenarios are included.

For read-only debugging, the browser console exposes `ArchitectUnderPressure.getState()`. It returns a copy of the current state, not a writable reference.

## Checks and reports

`TEST_REPORT.md` summarizes the completed source, engine, and browser checks. All 243 paths and all eight acceptance paths pass. The Markdown specification lists seven acceptance paths; the Word version adds `1C -> 2A -> 3A -> 4B -> 5A`, which must receive `RECOVERY WITH TRADEOFFS`.

To rerun the engine checks with Node.js, open a terminal in this folder and run:

```sh
node tests/test-engine.cjs
```

The engine test uses only Node built-ins. It independently reads expected values from the supplied Markdown rather than trusting the game's data.

Optional browser checks require Python, Playwright, and an installed Chromium browser:

```sh
python tests/test-browser.py
```

The browser suite may take several minutes. It tests every path through DOM events, samples native mouse and keyboard input, and checks replay and mobile widths. Its offline-document harness does not navigate to a `file://` URL. When testing the editable HTML, the harness temporarily embeds the local JPG bytes in the test document only; it does not edit the game file.

## Preserved placeholder

The existing **Stress-Test My Real Architecture** button is still V2's placeholder alert. It does not navigate to a consulting website because no destination URL was supplied.
