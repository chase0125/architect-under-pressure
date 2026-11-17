"""Browser regression tests. Requires Python Playwright and a Chromium browser.

Run: python tests/test-browser.py
Optional: --html /path/to/standalone.html --browser /path/to/chromium
The engine suite generates independently source-checked path expectations first.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import tempfile
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
parser = argparse.ArgumentParser()
parser.add_argument('--html', type=Path, default=PROJECT / 'Architect_V3.html')
parser.add_argument('--skip-exhaustive', action='store_true', help='Reuse a completed exhaustive run for the identical HTML hash')
parser.add_argument('--browser', default=shutil.which('chromium') or shutil.which('google-chrome'))
parser.add_argument('--screenshots', type=Path, default=HERE / 'screenshots')
args = parser.parse_args()
args.screenshots.mkdir(parents=True, exist_ok=True)
html_path = args.html.resolve()
markup = html_path.read_text(encoding='utf-8')
# Some managed test browsers block file:// navigation. Load the exact HTML
# into an offline document instead. For the editable variant only, resolve its
# local image reference to the same bytes in the harness (not in the artifact).
if 'src="ops_room.jpg"' in markup:
    image = (html_path.parent / 'ops_room.jpg').read_bytes()
    markup = markup.replace('src="ops_room.jpg"', 'src="data:image/jpeg;base64,' + base64.b64encode(image).decode('ascii') + '"', 1)
def load_page(page):
    page.set_content(markup, wait_until='load')

HELPERS = r"""() => {
    const data = JSON.parse(document.getElementById('scenario-data').textContent);
    const $ = id => document.getElementById(id);
    const canonical = v => Array.isArray(v) ? v.map(canonical) :
        (v && typeof v === 'object') ? Object.fromEntries(Object.keys(v).sort().map(k => [k, canonical(v[k])])) : v;
    const read = () => window.ArchitectUnderPressure.getState();
    let assertions = 0;
    function equal(a, b, label) {
        assertions++;
        if (JSON.stringify(canonical(a)) !== JSON.stringify(canonical(b))) {
            throw new Error(label + '\nactual: ' + JSON.stringify(a) + '\nexpected: ' + JSON.stringify(b));
        }
    }
    function visible(id) { return $(id).getClientRects().length > 0 && getComputedStyle($(id)).visibility !== 'hidden'; }
    function scores(expected) {
        const ids = {rel:'stat-rel', sec:'stat-sec', cost:'stat-cst', spd:'stat-spd', jud:'stat-jud'};
        for (const [key, id] of Object.entries(ids)) equal($(id).textContent, String(expected[key]), 'Score UI ' + key);
    }
    function noOverflow() {
        equal(document.documentElement.scrollWidth <= window.innerWidth, true, 'No horizontal overflow');
    }
    window.__qa = {
        get assertions() { return assertions; },
        chooseAndCheck(step) {
            const scene = data.scenes[step.start.sceneIndex];
            equal(read(), step.start, 'Start-state snapshot');
            equal($('story-text').textContent, step.prompt, 'Exact scene prompt');
            equal($('env-status').textContent, step.start.environment.status, 'Start status UI');
            equal($('env-metrics').textContent, step.start.environment.metrics, 'Start metrics UI');
            equal($('env-status').className, 'status-' + step.start.environment.status.toLowerCase(), 'Start status color');
            equal($('time-display').textContent, scene.time, 'Scene time');
            equal($('decision-tracker').textContent, `Decision ${step.start.sceneIndex + 1} of 5`, 'Progress');
            equal(visible('consequence-text'), false, 'No old consequence');
            equal(visible('continue-btn'), false, 'No premature Continue');
            equal(visible('aftermath'), false, 'No premature report');
            const choices = [...document.querySelectorAll('#choices-container button')];
            equal(choices.map(b => b.textContent), scene.choices.map(c => c.text), 'Exact choice labels/order');
            scores(step.start.scores);
            noOverflow();
            // Hidden Continue cannot skip the choice, even when dispatched manually.
            $('continue-btn').dispatchEvent(new MouseEvent('click', {bubbles:true}));
            equal(read(), step.start, 'Cannot Continue before choice');
            const target = choices.find(b => b.dataset.choiceId === step.after.result.choiceId);
            target.click();
            equal(choices.every(b => b.disabled), true, 'All former choice buttons immediately disabled');
            equal(document.querySelectorAll('#choices-container button').length, 0, 'Choices removed');
            // Detached button callbacks and early Continue events cannot apply twice.
            target.dispatchEvent(new MouseEvent('click', {bubbles:true}));
            choices.forEach(b => b.dispatchEvent(new MouseEvent('click', {bubbles:true})));
            $('continue-btn').click();
            $('continue-btn').dispatchEvent(new MouseEvent('click', {bubbles:true}));
            equal(read(), step.after, 'Exact after-choice state; repeat-click guard');
            equal($('consequence-text').textContent, step.after.result.consequence, 'Exact visible consequence');
            equal(visible('consequence-text'), true, 'Consequence visible');
            equal(visible('continue-btn'), true, 'Continue visible');
            equal($('continue-btn').disabled, true, 'Brief anti-double-click guard');
            equal($('env-status').textContent, step.after.environment.status, 'Post-choice status');
            equal($('env-metrics').textContent, step.after.environment.metrics, 'Post-choice metrics');
            equal($('env-status').className, 'status-' + step.after.environment.status.toLowerCase(), 'Post status color');
            equal(visible('aftermath'), false, 'Final consequence appears before report');
            equal($('decision-tracker').textContent, `Decision ${step.start.sceneIndex + 1} of 5`, 'Tracker does not advance early');
            scores(step.after.scores);
            noOverflow();
            this.staleButton = target;
        },
        advance() {
            equal($('continue-btn').disabled, false, 'Continue enabled after guard');
            $('continue-btn').click();
            const once = read();
            $('continue-btn').dispatchEvent(new MouseEvent('click', {bubbles:true, detail:2}));
            $('continue-btn').click();
            equal(read(), once, 'Repeated Continue cannot skip a scene');
        },
        report(final) {
            equal(read(), final, 'Exact final snapshot');
            equal(visible('aftermath'), true, 'Report visible');
            equal(visible('game-ui'), false, 'Old game UI hidden');
            equal(visible('decision-tracker'), false, 'Tracker hidden on report');
            equal($('end-title').textContent, final.ending.title, 'Exact ending title');
            equal($('end-summary').textContent, final.ending.summary, 'Exact ending summary');
            equal($('decision-log-heading').textContent, 'Decision Log', 'Report log heading');
            equal([...document.querySelectorAll('#decision-log li')].map(li => li.dataset.choiceId),
                  final.decisionLog.map(e => e.choiceId), 'Chronological choice IDs');
            equal([...document.querySelectorAll('#decision-log .log-debrief')].map(p => p.textContent),
                  final.decisionLog.map(e => e.debrief), 'Exact debrief lines');
            const labels = {rel:'Reliability', sec:'Security', cost:'Cost Efficiency', spd:'Response Speed', jud:'Judgment'};
            equal([...$('end-scores').children].map(el => el.textContent),
                  Object.entries(labels).map(([k,l]) => l + ': ' + final.scores[k]), 'Final score display');
            noOverflow();
        },
        replay() {
            $('replay-btn').click();
            const initial = read();
            equal(initial.scores, {rel:50,sec:50,cost:50,spd:50,jud:50}, 'Replay resets every score');
            equal(Object.values(initial.flags).every(v => v === false), true, 'Replay resets every flag');
            equal(initial.decisionLog, [], 'Replay clears log state');
            equal($('decision-log').children.length, 0, 'Replay clears log DOM');
            equal(initial.phase, 'choice', 'Replay starts on a choice');
            equal(initial.sceneIndex, 0, 'Replay starts on scene 1');
            if (this.staleButton) this.staleButton.dispatchEvent(new MouseEvent('click', {bubbles:true}));
            equal(read(), initial, 'Old callbacks cannot affect a new run');
        }
    };
}"""

with tempfile.TemporaryDirectory() as temp:
    fixtures_path = Path(temp) / 'paths.json'
    subprocess.run(['node', str(HERE / 'test-engine.cjs'), '--html', str(html_path), '--fixtures', str(fixtures_path)],
                   check=True, stdout=subprocess.PIPE, text=True)
    fixtures = json.loads(fixtures_path.read_text())
    acceptance = json.loads((HERE / 'acceptance-paths.json').read_text())
    by_path = {tuple(f['path']): f for f in fixtures}
    with sync_playwright() as p:
        launch_args = {'headless': True, 'args': ['--no-sandbox']}
        if args.browser:
            launch_args['executable_path'] = args.browser
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(viewport={'width': 1280, 'height': 900}, reduced_motion='reduce')
        context.set_offline(True)
        page = context.new_page()
        errors = []
        external_requests = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('request', lambda r: external_requests.append(r.url) if r.url.startswith(('https:', 'http:')) else None)
        load_page(page)
        page.clock.install()
        page.evaluate(HELPERS)
        assert page.locator('#scene-image').evaluate('(img) => img.complete && img.naturalWidth > 0')
        page.screenshot(path=str(args.screenshots / 'desktop_scene1.png'), full_page=True)
        # Exhaustive DOM paths: use real UI event handlers with a virtual clock,
        # not direct engine transitions. Every visible state is checked.
        cache_path = HERE / 'browser-exhaustive-report.json'
        html_hash = hashlib.sha256(html_path.read_bytes()).hexdigest()
        if args.skip_exhaustive:
            cached = json.loads(cache_path.read_text())
            assert cached['result'] == 'PASS' and cached['htmlSha256'] == html_hash
            dom_assertions = cached['domAssertions']
            assert cached['exhaustiveDomPaths'] == len(fixtures)
            print(f'Reused completed {len(fixtures)}-path DOM run for identical HTML: {dom_assertions} assertions.', flush=True)
        else:
            for idx, fixture in enumerate(fixtures):
                if idx:
                    page.evaluate('() => window.__qa.replay()')
                for step in fixture['steps']:
                    page.evaluate('(step) => window.__qa.chooseAndCheck(step)', step)
                    page.clock.fast_forward(500)
                    page.evaluate('() => window.__qa.advance()')
                page.evaluate('(final) => window.__qa.report(final)', fixture['final'])
            dom_assertions = page.evaluate('() => window.__qa.assertions')
            assert not errors, errors
            assert not external_requests, external_requests
            print(f'PASS: {len(fixtures)} complete DOM paths, {dom_assertions} browser assertions.', flush=True)
    
            cache_path.write_text(json.dumps({'result':'PASS', 'htmlSha256':html_hash,
                'exhaustiveDomPaths':len(fixtures), 'domAssertions':dom_assertions,
                'javascriptErrors':errors, 'externalHttpRequests':external_requests}, indent=2) + '\n')

        # Native-pointer smoke runs sample a clean recovery and a reopened incident.
        # All eight acceptance cases are already covered in the exhaustive DOM run.
        pointer_context = browser.new_context(viewport={'width':1280,'height':900}, reduced_motion='reduce')
        pointer_context.set_offline(True)
        pointer = pointer_context.new_page()
        pointer.on('pageerror', lambda e: errors.append(str(e)))
        pointer_tests = [acceptance[0], acceptance[-1]]
        for idx, test in enumerate(pointer_tests):
            print(f'Native pointer sample {idx + 1}/2', flush=True)
            load_page(pointer)
            for choice_id in test['path']:
                pointer.locator(f'[data-choice-id="{choice_id}"].choice-btn').click()
                assert pointer.locator('#consequence-text').is_visible()
                pointer.locator('#continue-btn').click()  # Waits for guard naturally.
            assert pointer.locator('#end-title').text_content() == test['ending']
            assert pointer.locator('#decision-log li').count() == 5
            if idx == 0:
                pointer.screenshot(path=str(args.screenshots / 'desktop_report_strong.png'), full_page=True)
            pointer.locator('#replay-btn').click()
            assert pointer.locator('#decision-tracker').text_content() == 'Decision 1 of 5'
            assert pointer.evaluate('() => Object.values(window.ArchitectUnderPressure.getState().flags).every(v => !v)')
        print('PASS: 2 representative paths using native mouse clicks.', flush=True)

        # Native double-click, Continue double-click, keyboard operation.
        load_page(pointer)
        pointer.locator('[data-choice-id="1A"]').dblclick()
        first = pointer.evaluate('() => window.ArchitectUnderPressure.getState()')
        assert first['phase'] == 'consequence' and len(first['decisionLog']) == 1
        assert first['scores'] == {'rel':45, 'sec':50, 'cost':40, 'spd':55, 'jud':40}
        pointer.wait_for_function('() => !document.getElementById("continue-btn").disabled')
        pointer.locator('#continue-btn').dblclick()
        second = pointer.evaluate('() => window.ArchitectUnderPressure.getState()')
        assert second['phase'] == 'choice' and second['sceneIndex'] == 1 and len(second['decisionLog']) == 1
        pointer.locator('[data-choice-id="2A"]').focus()
        pointer.keyboard.press('Enter')
        assert pointer.evaluate('() => window.ArchitectUnderPressure.getState().phase') == 'consequence'
        pointer.wait_for_function('() => !document.getElementById("continue-btn").disabled')
        pointer.locator('#continue-btn').focus()
        pointer.keyboard.press('Enter')
        assert pointer.evaluate('() => window.ArchitectUnderPressure.getState().sceneIndex') == 2

        print('PASS: native double-click and keyboard checks.', flush=True)

        # Mobile layouts, including longest ending and the preserved active threat.
        mobile_context = browser.new_context(reduced_motion='reduce')
        mobile_context.set_offline(True)
        mobile = mobile_context.new_page()
        mobile.set_viewport_size({'width':390, 'height':844})
        mobile.on('pageerror', lambda e: errors.append(str(e)))
        load_page(mobile)
        mobile.clock.install()
        mobile.evaluate(HELPERS)
        mobile.screenshot(path=str(args.screenshots / 'mobile_scene1.png'), full_page=True)
        impact_path = by_path[('1C','2A','3C','4B','5B')]
        for i, step in enumerate(impact_path['steps']):
            if i == 3:
                mobile.screenshot(path=str(args.screenshots / 'mobile_active_threat_scene4.png'), full_page=True)
            mobile.evaluate('(step) => window.__qa.chooseAndCheck(step)', step)
            mobile.clock.fast_forward(500)
            mobile.evaluate('() => window.__qa.advance()')
        mobile.evaluate('(final) => window.__qa.report(final)', impact_path['final'])
        mobile.screenshot(path=str(args.screenshots / 'mobile_report_impact.png'), full_page=True)
        mobile.set_viewport_size({'width':320,'height':640})
        mobile.evaluate('() => window.__qa.replay()')
        for step in by_path[('1A','2C','3C','4C','5A')]['steps']:
            mobile.evaluate('(step) => window.__qa.chooseAndCheck(step)', step)
            mobile.clock.fast_forward(500)
            mobile.evaluate('() => window.__qa.advance()')
        mobile.evaluate('(final) => window.__qa.report(final)', by_path[('1A','2C','3C','4C','5A')]['final'])
        assert mobile.evaluate('() => getComputedStyle(document.getElementById("env-status")).animationName') == 'none'
        mobile_assertions = mobile.evaluate('() => window.__qa.assertions')

        print('PASS: mobile layout and state checks.', flush=True)

        # Missing artwork must not break game logic or later scene rendering.
        fallback = pointer_context.new_page()
        load_page(fallback)
        fallback.locator('#scene-image').evaluate('(img) => { img.src = "missing-artwork-for-test.jpg"; }')
        fallback.wait_for_function('() => !document.getElementById("scene-image-fallback").hidden')
        assert fallback.locator('#scene-image-fallback').is_visible()
        fallback.locator('[data-choice-id="1C"]').click()
        fallback.locator('#continue-btn').click()
        assert fallback.locator('#decision-tracker').text_content() == 'Decision 2 of 5'
        assert fallback.locator('#scene-image-fallback').is_visible()
        assert not errors, errors
        report = {
            'result': 'PASS', 'browser': browser.version, 'html': html_path.name,
            'exhaustiveDomPaths': len(fixtures), 'domAssertions': dom_assertions,
            'nativePointerAcceptancePaths': len(pointer_tests), 'mobileAssertions': mobile_assertions,
            'viewportWidths': [1280, 390, 320], 'javascriptErrors': errors,
            'externalHttpRequests': external_requests,
            'loadMode': 'Offline document injection; file:// navigation is not exercised by this harness',
            'additionalChecks': [
                'Offline execution of shipped HTML via document injection; image load verified',
                'Native choice and Continue double-click protection',
                'Keyboard Enter operation and focus progression',
                'Replay clears all scores, flags, log entries, and old callbacks',
                'No horizontal overflow at desktop and 390px/320px mobile widths',
                'Reduced-motion preference and missing-image fallback'
            ]
        }
        (HERE / 'browser-test-report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)
        browser.close()
