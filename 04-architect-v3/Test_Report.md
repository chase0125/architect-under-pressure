# Architect Under Pressure - V3 test report

## Result

**PASS: all 243 possible five-choice paths and all eight acceptance paths.**

The existing V2 interface and artwork are retained. The build replaces the old scenario content and state/ending logic with the supplied V3 rules.

## Source fidelity

The implementation uses `Architect_Under_Pressure_Scenario_Tree_V3.md` for exact scene prompts, choice labels, score effects, flags, consequences, metrics, ending summaries, and debrief lines. A source-level audit compared 74 player-copy fields with the Word version; they matched after normalizing document-layout whitespace. The game preserves the original prompt paragraph breaks from Markdown.

The Word version adds one acceptance case not listed in Markdown: `1C -> 2A -> 3A -> 4B -> 5A` must receive `RECOVERY WITH TRADEOFFS`. It is included below. No contradictory gameplay rule was found between the two versions.

## Required acceptance paths

Final scores are ordered: Reliability, Security, Cost Efficiency, Response Speed, Judgment.

| Path | Expected and actual ending | Final scores | Result |
| --- | --- | --- | --- |
| 1C -> 2A -> 3A -> 4B -> 5C | STRONG RECOVERY | 100, 70, 65, 60, 100 | PASS |
| 1B -> 2B -> 3A -> 4B -> 5C | STRONG RECOVERY | 100, 70, 40, 60, 100 | PASS |
| 1C -> 2A -> 3B -> 4B -> 5C | RECOVERY WITH TRADEOFFS | 95, 60, 65, 65, 100 | PASS |
| 1C -> 2C -> 3A -> 4B -> 5C | RECOVERY WITH TRADEOFFS | 95, 70, 40, 60, 100 | PASS |
| 1C -> 2A -> 3C -> 4B -> 5B | SERVICE RESTORED, CUSTOMER IMPACT REMAINS | 100, 25, 50, 45, 90 | PASS |
| 1C -> 2A -> 3A -> 4C -> 5B | SERVICE RESTORED, CUSTOMER IMPACT REMAINS | 70, 70, 55, 60, 80 | PASS |
| 1C -> 2A -> 3A -> 4B -> 5A | RECOVERY WITH TRADEOFFS | 80, 70, 65, 70, 90 | PASS |
| 1A -> 2C -> 3C -> 4C -> 5A | INCIDENT REOPENED / UNRESOLVED | 30, 25, 0, 100, 0 | PASS |

## Exhaustive engine tests

The Node.js suite completed **27,842 assertions** across all **243 paths**. Expectations are parsed independently from the supplied Markdown and from selected choice IDs, rather than merely comparing the engine with itself.

The checks include exact wording, score changes after every decision, clamping, every named flag and explicit clear operation, chronological decision logs, both Scene 2 prompts, inherited Scene 2 metrics, all new-condition scene-start states, both conditional branches of choices 5A and 5C, ending priority, and inclusive score thresholds. Repeated or out-of-scene choices and premature/repeated Continue calls are verified as no-ops.

Additional seeded-state tests exercise score boundaries and explicit flag clearing even when those boundary values are not reached by normal gameplay.

| Ending | Number of complete paths |
| --- | ---: |
| INCIDENT REOPENED / UNRESOLVED | 69 |
| SERVICE RESTORED, CUSTOMER IMPACT REMAINS | 90 |
| STRONG RECOVERY | 12 |
| RECOVERY WITH TRADEOFFS | 72 |

The counts above describe exhaustive coverage, not probabilities of player behavior.

## Browser checks

The shipped standalone HTML was loaded into an offline Chromium document. All **243 complete paths** were then exercised through the actual DOM event handlers, producing **50,537 assertions**. The browser checks compare both live state and displayed prompts, choices, consequences, metrics, status classes, progress indicators, scores, ending text, and decision logs against the source-checked expected snapshots.

Two representative acceptance paths were additionally tested using native mouse clicks: a Strong Recovery path and the reopened-incident path. Native choice double-clicks, Continue double-clicks, and keyboard Enter operation were checked. Replay resets all scores, flags, log state, report content, and stale callbacks.

A further **409 assertions** covered representative mobile paths at **390px and 320px** widths. The desktop viewport was **1280px** wide. No horizontal overflow was detected. Screenshots of the opening scene, active-threat backlog scene, Strong Recovery report, and customer-impact report were visually inspected. Reduced-motion behavior and the missing-artwork fallback were also checked.

No unexpected JavaScript errors or external HTTP requests were observed in the checked runs.

## Important behavior deliberately preserved from the specification

A STABLE availability panel does not implicitly clear an active attack, compromised accounts, an unfixed query, or a recovery data gap. Those flags continue to affect the ending. A guarded ramp can detect risk and pause the campaign without reopening the incident. Broad IP blocking prevents Strong Recovery but is not itself one of the four flags that reopens the incident on choice 5A. Response Speed is displayed and scored but is not an ending threshold.

## Packaging and limits

The standalone download and editable project HTML have been compared and are identical except for the image source: embedded JPG bytes versus `ops_room.jpg`. Both use the same scene data, CSS, engine, and interface code.

Browser testing used Chromium 144.0.7559.96 and offline document injection. This harness does not test `file://` navigation, which is restricted in the test environment. Safari, Firefox, physical mobile devices, and assistive-technology combinations were not tested. The game code has no network, AI-service, or server dependency.

The existing consulting call-to-action remains a placeholder alert; no consulting URL was supplied. The scenario documents and original V2 source were not modified.
