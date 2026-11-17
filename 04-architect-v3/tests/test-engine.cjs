/* Run with: node tests/test-engine.cjs
 * Optional: node tests/test-engine.cjs --html ../Architect_V3.html --fixtures /tmp/paths.json
 * Uses Node built-ins only. Expectations are read independently from the source
 * Markdown and the specified decision paths, not inferred from engine output.
 */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const project = path.resolve(__dirname, "..");
const htmlPath = path.resolve(option("--html", path.join(project, "Architect_V3.html")));
const html = fs.readFileSync(htmlPath, "utf8");
const spec = fs.readFileSync(path.join(project, "Architect_Under_Pressure_Scenario_Tree_V3.md"), "utf8");
const acceptance = JSON.parse(fs.readFileSync(path.join(__dirname, "acceptance-paths.json"), "utf8"));
const scriptText = id => {
    const match = html.match(new RegExp(`<script\\b[^>]*\\bid="${id}"[^>]*>([\\s\\S]*?)<\\/script>`));
    assert.ok(match, "Missing script: " + id);
    return match[1];
};
const data = JSON.parse(scriptText("scenario-data"));
const sandbox = { module: { exports: {} } };
vm.runInNewContext(scriptText("game-engine"), sandbox, { filename: "Architect_V3.html/game-engine" });
const engine = sandbox.module.exports.createEngine(data);
let assertions = 0;
const plain = value => JSON.parse(JSON.stringify(value));
function equal(actual, expected, label) {
    assertions++;
    assert.deepStrictEqual(plain(actual), plain(expected), label);
}
function check(condition, label) {
    assertions++;
    assert.ok(condition, label);
}
const scoreKeys = ["rel", "sec", "cost", "spd", "jud"];
const sourceScoreKeys = ["REL", "SEC", "CST-EFF", "SPD", "JUD"];
const expectedFlags = [
    "accountsCompromised", "attackActive", "attackContained", "attackPartiallyContained",
    "backlogControlled", "broadBlock", "conservativeRecovery", "dbScaled", "fullTrafficRestored",
    "guardedRamp", "incidentReopened", "indexHotfix", "queryFixed", "recoveryDataGap",
    "recoveryOverload", "releaseRolledBack", "rootCauseFoundEarly", "scaledWrongLayer",
    "stableEnd", "unguardedRamp", "workaroundOnly"
].sort();
const sourceScenes = [];
const sourceChoices = {};
let currentScene = null;
let currentChoice = null;
for (const line of spec.split(/\r?\n/)) {
    const sceneHeading = line.match(/^## Scene (\d) - (.+) \(([^)]+)\)$/);
    const choiceHeading = line.match(/^### (\d[A-C]) - (.+)$/);
    if (sceneHeading) {
        currentScene = { id: Number(sceneHeading[1]), title: sceneHeading[2], time: sceneHeading[3], intro: [], choices: [] };
        sourceScenes.push(currentScene);
        currentChoice = null;
    } else if (line.startsWith("## ")) {
        currentScene = null;
        currentChoice = null;
    } else if (choiceHeading) {
        currentChoice = { id: choiceHeading[1], text: choiceHeading[2], fields: {} };
        sourceChoices[currentChoice.id] = currentChoice;
        currentScene.choices.push(currentChoice);
    } else if (currentChoice) {
        const field = line.match(/^- \*\*([^*]+):\*\* (.+)$/);
        if (field) currentChoice.fields[field[1]] = field[2];
    } else if (currentScene) {
        currentScene.intro.push(line);
    }
}
for (const scene of sourceScenes) {
    const intro = scene.intro.join("\n");
    scene.prompts = Array.from(intro.matchAll(/```text\n([\s\S]*?)\n```/g), match => match[1]);
    scene.start = intro.match(/\*\*Start state:\*\* (.+)/)[1];
    for (const choice of scene.choices) {
        choice.effects = Object.fromEntries(choice.fields["Score effects"].split(" | ").map(part => {
            const [key, value] = part.split(" ");
            return [scoreKeys[sourceScoreKeys.indexOf(key)], Number(value)];
        }));
        choice.setFlags = choice.fields.Flags.split("; ")[0].replace("Set: ", "").split(", ");
        choice.clearFlags = choice.fields.Flags.includes("Clear: ")
            ? choice.fields.Flags.split("Clear: ")[1].split(", ") : [];
    }
}
const titles = {
    reopened: "INCIDENT REOPENED / UNRESOLVED",
    customerImpact: "SERVICE RESTORED, CUSTOMER IMPACT REMAINS",
    strong: "STRONG RECOVERY",
    tradeoffs: "RECOVERY WITH TRADEOFFS"
};
const summaries = Array.from(spec.matchAll(/Exact summary: "([^"]+)"/g), match => match[1]);
function parseEnvironment(text) {
    const first = text.indexOf(" | ");
    return { status: text.slice(0, first), metrics: text.slice(first + 3) };
}
function sourcePrompt(index, selected) {
    return sourceScenes[index].prompts[index === 1 && selected.includes("1C") ? 1 : 0];
}
function sourceStart(index, selected, previous) {
    const start = sourceScenes[index].start;
    if (index === 1) return { ...previous };
    if (index === 0 || index === 2) return parseEnvironment(start.replace("Status: ", "").replace("Metrics: ", ""));
    const metrics = start.split("Base metrics: ")[1];
    if (index === 3) return {
        status: selected.includes("3C") ? "CRITICAL" : "DEGRADED",
        metrics: metrics + (selected.includes("3C") ? " | Threat: ACTIVE" : "")
    };
    return {
        status: selected.includes("3C") ? "CRITICAL" :
            selected.some(id => ["2C", "3B", "4A", "4C"].includes(id)) ? "DEGRADED" : "STABLE",
        metrics
    };
}
function sourceOutcome(choice, selected) {
    const risky = selected.some(id => ["2C", "3C", "4A", "4C"].includes(id));
    const conditional = ["5A", "5C"].includes(choice.id);
    const prefix = conditional ? (risky ? "Risky" : "Safe") : "Exact";
    const postKey = conditional ? prefix + " post-state" : "Post-state";
    return { consequence: choice.fields[prefix + " consequence"], ...parseEnvironment(choice.fields[postKey]) };
}
function expectedEnding(selected, scores) {
    if (selected.includes("5A") && selected.some(id => ["2C", "3C", "4A", "4C"].includes(id))) return "reopened";
    if (selected.includes("3C") || selected.includes("4C")) return "customerImpact";
    if (selected.some(id => ["2C", "3B", "4A", "5A"].includes(id))) return "tradeoffs";
    return scores.rel >= 65 && scores.sec >= 60 && scores.cost >= 35 && scores.jud >= 65 ? "strong" : "tradeoffs";
}

// Exact scenario transcription (all prompts, choices, scores, flags, copy, metrics).
equal(data.flagNames, expectedFlags, "All 21 flags, including scene-local auxiliary flags");
equal(data.scenes.length, 5, "Five decisions");
equal(data.endings.map(item => item.title), Object.values(titles), "Ending titles/priority");
equal(data.endings.map(item => item.summary), summaries, "Exact ending summaries");
for (const scene of sourceScenes) {
    const implemented = data.scenes[scene.id - 1];
    equal(implemented.time, scene.time, "Scene time");
    equal(implemented.title, scene.title, "Scene title");
    equal(implemented.prompt, scene.prompts[0], "Exact prompt");
    if (scene.id === 2) equal(implemented.earlyDiagnosisPrompt, scene.prompts[1], "Alternate scene 2 prompt");
    equal(implemented.choices.length, 3, "Three choices per scene");
    for (let i = 0; i < scene.choices.length; i++) {
        const expected = scene.choices[i];
        const actual = implemented.choices[i];
        equal(actual.id, expected.id, "Choice ID/order");
        equal(actual.text, expected.text, "Exact choice label");
        equal(actual.effects, expected.effects, "Exact score effects");
        equal(actual.setFlags, expected.setFlags, "Set flags");
        equal(actual.clearFlags, expected.clearFlags, "Clear flags");
        equal(actual.debrief, expected.fields["Aftermath decision-log line"], "Exact debrief");
        if (actual.outcomes) {
            equal(actual.outcomes.safe, sourceOutcome(expected, []), "Exact safe outcome");
            equal(actual.outcomes.risk, sourceOutcome(expected, ["2C"]), "Exact risky outcome");
            equal(actual.riskFlags, ["workaroundOnly", "attackActive", "recoveryOverload", "recoveryDataGap"], "Risk set excludes broadBlock");
        } else equal(actual.outcome, sourceOutcome(expected, []), "Exact outcome");
    }
}

const fixtures = [];
const counts = Object.fromEntries(Object.keys(titles).map(key => [key, 0]));
const sourceScenarios = sourceScenes.map(scene => scene.choices.map(choice => choice.id));
const paths = sourceScenarios.reduce((prior, choices) => prior.flatMap(prefix => choices.map(id => [...prefix, id])), [[]]);
equal(paths.length, 243, "3^5 paths");
for (const choicePath of paths) {
    let state = engine.createInitialState();
    let expectedScores = Object.fromEntries(scoreKeys.map(key => [key, 50]));
    const flags = Object.fromEntries(expectedFlags.map(key => [key, false]));
    const selected = [];
    const log = [];
    let previousEnvironment = null;
    const steps = [];
    for (let i = 0; i < 5; i++) {
        const label = choicePath.join(" -> ") + ", scene " + (i + 1);
        equal(state.phase, "choice", label + ": choice phase");
        equal(state.sceneIndex, i, label + ": index");
        equal(state.environment, sourceStart(i, selected, previousEnvironment), label + ": scene-start state");
        equal(engine.getPrompt(i, state.flags), sourcePrompt(i, selected), label + ": conditional prompt");
        equal(state.flags, flags, label + ": flags survive scene changes");
        check(engine.continueGame(state) === state, label + ": cannot Continue before choosing");
        check(engine.choose(state, "invalid") === state, label + ": invalid choices ignored");
        check(engine.choose(state, (i === 0 ? "2A" : "1A")) === state, label + ": wrong-scene choice ignored");
        const startSnapshot = plain(state);
        const choice = sourceChoices[choicePath[i]];
        selected.push(choice.id);
        expectedScores = Object.fromEntries(scoreKeys.map(key => [key, Math.min(100, Math.max(0, expectedScores[key] + choice.effects[key]))]));
        choice.setFlags.forEach(flag => { flags[flag] = true; });
        choice.clearFlags.forEach(flag => { flags[flag] = false; });
        if (choice.id === "5A" && selected.some(id => ["2C", "3C", "4A", "4C"].includes(id))) flags.incidentReopened = true;
        const outcome = sourceOutcome(choice, selected);
        log.push({ choiceId: choice.id, sceneId: i + 1, choiceText: choice.text, debrief: choice.fields["Aftermath decision-log line"] });
        const next = engine.choose(state, choice.id);
        equal(state, startSnapshot, label + ": pure transition does not mutate old state");
        state = next;
        equal(state.phase, "consequence", label + ": consequence cannot be skipped");
        equal(state.sceneIndex, i, label + ": no auto-advance");
        equal(state.scores, expectedScores, label + ": score deltas/clamping");
        equal(state.flags, flags, label + ": exact flag changes");
        equal(state.environment, { status: outcome.status, metrics: outcome.metrics }, label + ": exact post-state");
        equal(state.result, { choiceId: choice.id, consequence: outcome.consequence }, label + ": exact consequence");
        equal(state.decisionLog, log, label + ": chronological decision log");
        equal(state.ending, null, label + ": no ending before Continue");
        for (const retry of sourceScenes[i].choices) check(engine.choose(state, retry.id) === state, label + ": repeated choices ignored");
        const after = plain(state);
        steps.push({ start: startSnapshot, prompt: sourcePrompt(i, selected), after });
        previousEnvironment = state.environment;
        state = engine.continueGame(state);
        check(engine.continueGame(state) === state, label + ": repeated Continue cannot skip scenes");
    }
    const ending = expectedEnding(choicePath, expectedScores);
    equal(state.phase, "aftermath", "Report after five decisions");
    equal(state.ending.id, ending, "Independent ending oracle: " + choicePath.join(" -> "));
    equal(state.ending.title, titles[ending], "Exact ending title");
    equal(state.decisionLog.length, 5, "Five debrief entries");
    if (state.flags.incidentReopened) equal(state.ending.id, "reopened", "Reopened flag always wins");
    if (!state.flags.incidentReopened && (state.flags.accountsCompromised || state.flags.recoveryDataGap)) {
        equal(state.ending.id, "customerImpact", "Customer impact cannot receive Strong Recovery");
    }
    check(engine.choose(state, "5A") === state, "No choices after report");
    equal(engine.createInitialState().scores, Object.fromEntries(scoreKeys.map(key => [key, 50])), "Replay score reset");
    check(Object.values(engine.createInitialState().flags).every(value => value === false), "Replay flag reset");
    counts[ending]++;
    fixtures.push({ path: choicePath, steps, final: plain(state) });
}
const acceptanceResults = acceptance.map(test => {
    const result = fixtures.find(item => item.path.join(",") === test.path.join(","));
    equal(result.final.ending.title, test.ending, "Required acceptance: " + test.path.join(" -> "));
    return { ...test, passed: true, scores: result.final.scores };
});

// Explicit boundaries and otherwise-unreachable seeded-state regression tests.
const thresholds = { rel: 65, sec: 60, cost: 35, spd: 0, jud: 65 };
const atThreshold = { ...engine.createInitialState(), scores: thresholds };
equal(engine.classifyEnding(atThreshold).id, "strong", "Inclusive score thresholds; no response-speed gate");
for (const key of ["rel", "sec", "cost", "jud"]) {
    equal(engine.classifyEnding({ ...atThreshold, scores: { ...thresholds, [key]: thresholds[key] - 1 } }).id, "tradeoffs", "Below threshold: " + key);
}
for (const flag of ["workaroundOnly", "broadBlock", "recoveryOverload", "unguardedRamp"]) {
    equal(engine.classifyEnding({ ...atThreshold, flags: { ...atThreshold.flags, [flag]: true } }).id, "tradeoffs", "Shortcut overrides high scores: " + flag);
}
for (const flag of ["accountsCompromised", "recoveryDataGap"]) {
    const impact = { ...atThreshold, flags: { ...atThreshold.flags, [flag]: true } };
    equal(engine.classifyEnding(impact).id, "customerImpact", "Customer impact overrides high scores");
    equal(engine.classifyEnding({ ...impact, flags: { ...impact.flags, incidentReopened: true } }).id, "reopened", "Reopened overrides customer impact");
}
for (const flag of ["scaledWrongLayer", "dbScaled", "rootCauseFoundEarly", "releaseRolledBack", "indexHotfix"]) {
    equal(engine.classifyEnding({ ...atThreshold, flags: { ...atThreshold.flags, [flag]: true } }).id, "strong", "Historical flag does not disqualify: " + flag);
}
for (const choice of Object.values(sourceChoices)) {
    for (const initialScore of [0, 1, 99, 100]) {
        const seeded = { ...engine.createInitialState(), sceneIndex: Number(choice.id[0]) - 1,
            scores: Object.fromEntries(scoreKeys.map(key => [key, initialScore])) };
        const result = engine.choose(seeded, choice.id);
        for (const key of scoreKeys) equal(result.scores[key], Math.min(100, Math.max(0, initialScore + choice.effects[key])), "Score boundary " + choice.id + ": " + key);
    }
    if (choice.clearFlags.length) {
        const seeded = { ...engine.createInitialState(), sceneIndex: Number(choice.id[0]) - 1 };
        choice.clearFlags.forEach(flag => { seeded.flags[flag] = true; });
        const result = engine.choose(seeded, choice.id);
        choice.clearFlags.forEach(flag => equal(result.flags[flag], false, "Explicitly clear seeded flag: " + flag));
    }
}

const report = {
    result: "PASS", html: path.basename(htmlPath), runtime: process.version,
    assertions, exhaustivePaths: paths.length, acceptanceTests: acceptanceResults,
    endingDistribution: Object.fromEntries(Object.entries(counts).map(([key, count]) => [titles[key], count])),
    checked: [
        "Exact source prompts, choices, consequences, metrics, deltas, flags, and debriefs",
        "All 243 paths including every scene-start and post-choice environment",
        "Both Scene 2 introductions and inherited environment",
        "Both Scene 5 conditional branches; broadBlock does not itself reopen incident",
        "Consequence/Continue gating and repeated/out-of-scene selection no-ops",
        "Ending priority, inclusive thresholds, clamping to 0-100, and seeded flag clearing",
        "Clean initial state for replay; no implicit clearing of unresolved risks"
    ]
};
fs.writeFileSync(path.join(__dirname, "engine-test-report.json"), JSON.stringify(report, null, 2) + "\n");
if (args.includes("--fixtures")) fs.writeFileSync(option("--fixtures"), JSON.stringify(fixtures));
console.log(JSON.stringify(report, null, 2));
