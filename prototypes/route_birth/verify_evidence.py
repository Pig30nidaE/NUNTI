#!/usr/bin/env python3
"""Offline recheck of independent route-born QA evidence, no model/device I/O.

Preserves failed run verdicts and checks the exact successful subflows plus a
separate final policy run. Human visual/audio quality is never a numeric PASS.
This covers four QA journeys; a later direct-UI journey has separate evidence.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from verify_http import canonical, require, sha, validate_audio, validate_visual

HERE = Path(__file__).resolve().parent


def read(relative):
    return json.loads((HERE / relative).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Evidence output must be new')
    checks = []
    invalid = read('http-invalid-02/verification.json')
    require(invalid['status'] == 'PASS_INDEPENDENT_ROUTE_BIRTH_HTTP_AND_ARTIFACTS'
            and len(invalid['invalidInputs']) == 27 and invalid['postRequests'] == 0, 'Invalid-input evidence differs')
    checks.append({'check': '27 real HTTP invalid inputs rejected without model job submission', 'ok': True,
                   'httpCalls': invalid['httpCallCount']})
    geometry = read('geometry-independent-02.json')
    require(geometry['status'] == 'PASS_ROUTE_INFLUENCE_WITH_FIXED_NONCE_AND_CONTINUOUS_GEOMETRY'
            and geometry['fixedNonceRouteCount'] == 136 and geometry['sameRouteNewJourneyCount'] == 40
            and geometry['generatorSha256'] == sha((HERE / 'generator.py').read_bytes()), 'Current pure geometry evidence differs')
    checks.append({'check': 'fixed-nonce route influence and complete face-ellipse containment', 'ok': True,
                   'fixedNonceRoutes': 136, 'sameRouteNewJourneyCount': 40,
                   'perceptualUniqueness': 'NOT_VERIFIED'})
    artifacts = []
    http_proofs = []
    for relative in ('http-artifacts-02/verification.json', 'http-native-created-01/verification.json'):
        report = read(relative)
        require(report['status'] == 'PASS_INDEPENDENT_ROUTE_BIRTH_HTTP_AND_ARTIFACTS', 'Independent HTTP artifact run failed')
        for job in report['jobs']:
            directory = HERE / Path(relative).parent / job['directory']
            response = json.loads((directory / 'response.json').read_text())
            artifact = response['artifact']
            require(artifact['journeyId'] == job['requestId'] and sha(canonical(artifact)) == job['artifactSha256'], 'Saved HTTP artifact changed')
            require(sha(artifact['inputCanonical'].encode()) == artifact['inputSha256'], 'Canonical input changed')
            validate_visual(artifact['visual'])
            for clip in artifact['voiceManifest']['clips']:
                validate_audio((directory / clip['audioPath']).read_bytes(), clip)
            artifacts.append(artifact)
            http_proofs.append(job)
    require(len(artifacts) == 4 and len({a['characterId'] for a in artifacts}) == 4
            and len({sha(canonical(a['visual']['outline'])) for a in artifacts}) == 4, 'Four exact distinct sampled results missing')
    require(sum(len(a['voiceManifest']['clips']) for a in artifacts) == 12, 'Expected 12 source WAVs')
    checks.append({'check': 'four exact input/outline/voice joins and 12 original WAVs', 'ok': True,
                   'journeyCount': 4, 'sourceWavCount': 12})
    native = read('native-runtime-02/verification.json')
    require(native['status'] == 'FAIL' and native['error'] == 'Foreground loss did not cancel active request',
            'Original whole-run FAIL verdict was changed')
    expected_checks = ['fresh input route/animation/voice runtime join ' + str(i) for i in range(4)]
    expected_checks += ['new native character greeting playback ' + str(i) for i in range(4)]
    require(all(any(c['check'] == name and c['ok'] for c in native['checks']) for name in expected_checks),
            'Native four-case input or greeting evidence missing')
    require(sum(c['check'] == 'arrival, collection and cold-process identity restore' and c['ok'] for c in native['checks']) == 4,
            'Native four-case arrival/save/restore evidence missing')
    require(any(c['check'] == 'actual Android parser and immutable storage boundary checks'
                and c['event']['passed'] == 9 for c in native['checks']), 'Actual nine Android boundary checks missing')
    events = [json.loads(line) for line in (HERE / 'native-runtime-02/runtime-events.jsonl').read_text().splitlines() if line]
    artifact_by_request = {a['journeyId']: a for a in artifacts}
    completed = set()
    for request in (v for v in events if v['kind'] == 'RB_SPEECH_REQUEST'):
        source = artifact_by_request[request['tripId']]
        clip = next(c for c in source['voiceManifest']['clips'] if c['clipId'] == request['clipId'])
        require(all(request[k] == clip[k] for k in ('characterId', 'profileId', 'audioSha256')), 'Actual native speech source join differs')
        group = [v for v in events if v['kind'] == 'RB_SPEECH' and v['requestId'] == request['requestId']]
        if [v['status'] for v in group] == ['QUEUED', 'STARTED', 'COMPLETED']:
            require(all(v['providerId'] == 'qwen3-tts-sohee-local' and v['profileId'] == clip['profileId'] for v in group),
                    'Completed native playback escaped source provider/profile')
            completed.add(request['clipId'])
    expected_complete = {a['characterId'] + '-' + category for a in artifacts for category in ('greeting', 'arrival')}
    require(expected_complete.issubset(completed), 'Four native greetings and arrival clips did not complete')
    fresh_id = read('verify_native_new_request.json')['requestId']
    fresh_events = [v for v in events if v.get('requestId') == fresh_id]
    require(any(v['kind'] == 'RB_STATE' and v['state'] == 'GENERATING' for v in fresh_events)
            and any(v['kind'] == 'RB_READY' for v in fresh_events), 'Fresh native generation interval missing')
    require({v['stage'] for v in fresh_events if v['kind'] == 'RB_ANIMATION'} == {'ROUTE_TRACE', 'ROUTE_TO_BODY', 'FACE_REVEAL', 'COMPLETE'},
            'Fresh native animation stages missing')
    first_ready = next(v for v in fresh_events if v['kind'] == 'RB_READY')
    first_submit = next(v for v in fresh_events if v['kind'] == 'RB_SUBMITTED')
    elapsed = (datetime.fromisoformat(first_ready['at'].replace('Z', '+00:00'))
               - datetime.fromisoformat(first_submit['at'].replace('Z', '+00:00'))).total_seconds()
    checks.append({'check': 'four actual native inputs, eight completed clips, collection and cold restore', 'ok': True,
                   'freshNativeRequestId': fresh_id, 'freshSubmitToReadySeconds': elapsed,
                   'androidBoundaryChecks': 9, 'originalWholeRunStatus': native['status'],
                   'originalWholeRunError': native['error'],
                   'failedExpectationExplanation': 'Actual foreground loss cancelled with core policy reason INACTIVE before onBackground; verifier initially expected only BACKGROUND or SPEECH_NOT_ALLOWED.'})
    policies = read('native-runtime-03/verification.json')
    require(policies['status'] == 'PASS_NATIVE_ROUTE_BIRTH_QUEUE_AND_POLICY', 'Targeted native policy run failed')
    labels = {'real background cancels and return stays silent', 'duplicate suppression and stop cancels active plus pending voice',
              'policy block cancels, prevents new requests, and returns silently', 'cached replay native intermediate morph capture'}
    require(labels.issubset({c['check'] for c in policies['checks'] if c['ok']}), 'Required final targeted checks missing')
    for screenshot in native['screenshots'] + policies['screenshots']:
        base = 'native-runtime-02' if screenshot in native['screenshots'] else 'native-runtime-03'
        require(sha((HERE / base / screenshot['file']).read_bytes()) == screenshot['sha256'], 'Native screenshot changed')
    checks.append({'check': 'final same-APK foreground, duplicate, active/pending stop, block and silent returns', 'ok': True,
                   'status': policies['status']})
    evidence = ['generator.py', 'verify_http.py', 'verify_geometry.py', 'verify_android.py', 'verify_evidence.py',
                'http-invalid-02/verification.json', 'geometry-independent-02.json', 'http-artifacts-02/verification.json',
                'http-native-created-01/verification.json', 'native-runtime-01/verification.json',
                'native-runtime-02/verification.json', 'native-runtime-02/runtime-events.jsonl',
                'native-runtime-03/verification.json', 'native-runtime-03/runtime-events.jsonl']
    report = {'status': 'PASS_INDEPENDENT_FOUR_JOURNEY_ROUTE_BIRTH_EVIDENCE',
              'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Four QA journeys, 12 WAV integrity checks, eight completed native clips, isolated collection/restore and targeted final policy checks.',
              'checks': checks, 'originalFailedRunsPreserved': ['http-invalid-01', 'native-runtime-01', 'native-runtime-02'],
              'evidenceSha256': {p: sha((HERE / p).read_bytes()) for p in evidence},
              'notVerified': ['Human Korean listening or acoustic PCM capture', 'Perceptual uniqueness, visual taste, cuteness or collectibility',
                              'Physical vehicle or real road behavior', 'Direct D/P transition in the new route-born host',
                              'A later direct-gesture fifth journey, which has separate evidence', 'Whole 12 clip native completion; eight completed, other clips used in stop/policy checks']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'checks': len(checks), 'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
