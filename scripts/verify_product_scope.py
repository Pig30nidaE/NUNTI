#!/usr/bin/env python3
"""Check product scope and audited source hashes without network or media capture."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / 'docs/product/nunti-scope.json'
BRIEF = ROOT / 'docs/product/2026-hmg-app-challenge.md'
OUTPUT = ROOT / 'docs/research/2026-11-03-scope-verification.json'


def main():
    scope = json.loads(SCOPE.read_text())
    checks = []

    def check(name, ok):
        checks.append({'check': name, 'ok': bool(ok)})

    goal = scope['productGoal']
    feature = scope['ownedFeature']
    target = scope['ownedFeatureTarget']
    check('explicit-product-and-owned-feature-schema', scope['schemaVersion'] == 'product-scope-v2')
    check('product-goal-is-driving-habit-improvement', goal['id'] == 'DRIVING_HABIT_IMPROVEMENT_WITH_NUNTI'
          and goal['name'] == '운전습관 개선을 도와주는 아바타 눈티')
    check('habit-improvement-effect-remains-unverified', goal['improvementEffectVerified'] is False)
    check('owned-feature-is-destination-route-generation', feature['id'] == 'DESTINATION_ROUTE_AVATAR_GENERATION')
    check('owned-feature-serves-product-goal', feature['parentGoal'] == goal['id']
          and feature['contribution'] == 'PERSONAL_AVATAR_IDENTITY_FOR_DRIVING_FEEDBACK')
    check('generation-outputs-include-identity-appearance-and-voice', feature['outputs'] == [
        'JOURNEY_AVATAR_IDENTITY', 'APPEARANCE_ASSETS', 'CHARACTER_VOICE_IDENTITY'])
    check('generation-connects-to-feedback-display-and-tts', feature['consumers'] == [
        'EMOTION_AND_FEEDBACK', 'AVATAR_DISPLAY', 'TTS_PLAYBACK'])
    check('generation-does-not-invent-driving-assessment', feature['doesNotCompute'] == [
        'DRIVING_SCORE', 'VERIFIED_DRIVING_EVENTS', 'FINAL_DRIVING_COMMENT'])
    check('external-payload-coordination-remains-deferred', feature['externalPayloadCoordination'] == 'DEFERRED')
    check('no-flat-product-feature-scope', not {'primaryCapability', 'target', 'currentImplementation'}.intersection(scope))
    check('implementation-status-scoped-to-owned-feature', 'ownedFeatureCurrentImplementation' in scope)
    check('navigation-and-screenshot-inputs', target['primaryRouteInputs'] == ['PLEOS_NAVIHELPER', 'NAVIGATION_SCREENSHOT'])
    check('freehand-is-an-auxiliary-tool', target['freehandRole'] == 'DIAGNOSTIC_OR_CORRECTION_ONLY')
    check('visual-result-independent-of-voice-target', target['voiceRequiredForVisualReady'] is False)
    check('commercial-provider-is-a-choice', target['commercialImageProviderMandatory'] is False)
    check('recording-requires-explicit-user-request', scope['recordingPolicy'] == 'EXPLICIT_USER_REQUEST_ONLY')
    check('current-gleo-interface', target['gleoIntegration'] == 'GLEO_INTERFACE')
    for path, expected in scope['sourceSnapshot'].items():
        check('audit-source-unchanged:' + path, hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected)

    entry_points = ('README.md', 'docs/handoff/STATUS.md', 'docs/handoff/prompts/pm.md',
                 'docs/handoff/prompts/avatar.md', 'docs/handoff/prompts/tts.md', 'docs/handoff/prompts/server.md',
                 'docs/product/journey-character-brief.md', 'docs/design/generative-mvp/README.md',
                 'docs/design/generative-mvp/API-SETUP.ko.md')
    for name in entry_points:
        intro = '\n'.join((ROOT / name).read_text().splitlines()[:10])
        check('canonical-brief-linked-at-entry:' + name, BRIEF.name in intro)
        check('product-goal-and-owned-feature-at-entry:' + name,
              re.search(r'운전\s*습관\s*개선', intro) and '담당' in intro and '경로' in intro)
    documents = [BRIEF] + sorted((ROOT / 'docs/research').glob('2026-11-03-*.md'))
    link_count = 0
    for document in documents:
        content = re.sub(r'(?ms)^```.*?^```\s*$', '', document.read_text())
        for value in re.findall(r'!?\[[^\]\n]*\]\(([^\s)]+)', content):
            parsed = urlsplit(value.strip('<>'))
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = re.sub(r':\d+$', '', unquote(parsed.path))
            destination = (document.parent / path).resolve()
            # This report is produced below, so it is not a pre-existing input dependency.
            check('local-link:' + document.name + ':' + value,
                  destination.is_relative_to(ROOT) and (destination.exists() or destination == OUTPUT))
            link_count += 1
    report = {'status': 'PASS_PRODUCT_SCOPE_AND_AUDIT' if all(c['ok'] for c in checks) else 'FAIL',
        'scope': 'Product goal, owned-feature boundaries, local documentation links and audited source hashes only; no new application, habit-improvement effect or live SDK tests.',
        'productGoal': goal['id'], 'ownedFeature': feature['id'],
        'requirements': str(SCOPE.relative_to(ROOT)), 'brief': str(BRIEF.relative_to(ROOT)),
        'checksPassed': sum(c['ok'] for c in checks), 'checksFailed': sum(not c['ok'] for c in checks),
        'localLinksChecked': link_count, 'externalApiCalls': 0, 'mediaCaptured': False, 'checks': checks}
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'checksPassed', 'checksFailed', 'localLinksChecked', 'externalApiCalls', 'mediaCaptured')}))
    return 0 if report['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
