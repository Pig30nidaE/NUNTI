#!/usr/bin/env python3
"""Exercise the installed v2 APK, real local HTTP, actual WAV playback and restoration."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
ADB = ROOT / '.local/pm-tools/sdk/platform-tools/adb'
PACKAGE = 'ai.nunti.avatar.demo'
ACTIVITY = PACKAGE + '/ai.nunti.app.generated.GeneratedCompanionActivity'


def check(value, message):
    if not value:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--connection', type=Path, default=ROOT / '.local/generative-mvp/connection-offline_fixture.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--no-screenshots', action='store_true', help='Verify events and media hashes without saving screen images.')
    args = parser.parse_args()
    output = args.output or ROOT / '.local/generative-mvp' / ('native-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    adb = [str(ADB), '-s', args.serial]
    config = json.loads(args.connection.read_text())
    check(config['mode'] == 'OFFLINE_FIXTURE', 'This verification never runs paid API generation')
    check(config['baseUrl'] == 'http://127.0.0.1:8767', 'Fixture verification only uses the local server')

    def command(*parts, binary=False):
        result = subprocess.run(adb + list(parts), check=True, capture_output=True)
        return result.stdout if binary else result.stdout.decode()

    def shell(*parts):
        return command('shell', shlex.join([str(x) for x in parts]))

    user = shell('am', 'get-current-user').strip()
    check(user.isdigit(), 'No current Android user')

    def read_private(path, binary=False):
        return command('exec-out', 'run-as', PACKAGE, '--user', user, 'cat', path, binary=binary)

    def events():
        try:
            return [json.loads(line) for line in read_private('files/generated-events.jsonl').splitlines() if line]
        except subprocess.CalledProcessError:
            return []

    def wait(predicate, after=0, seconds=90):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for event in events()[after:]:
                if predicate(event):
                    return event
            time.sleep(.25)
        recent = events()[after:][-8:]
        raise AssertionError('Native timeout: ' + json.dumps(recent, ensure_ascii=False))

    def act(action, **extras):
        parts = ['am', 'start', '-W', '--user', user, '-n', ACTIVITY, '--es', 'g_action', action]
        for key, value in extras.items():
            parts += ['--ez' if isinstance(value, bool) else '--es', key, str(value).lower() if isinstance(value, bool) else str(value)]
        return shell(*parts)

    def get(path):
        request = urllib.request.Request(config['baseUrl'] + path, headers={'Authorization': 'Bearer ' + config['token']})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read(524288))['data']

    def screen(name):
        if not args.no_screenshots:
            (output / (name + '.png')).write_bytes(command('exec-out', 'screencap', '-p', binary=True))

    proof = {'status': 'FAIL', 'mode': 'OFFLINE_FIXTURE', 'at': datetime.now(timezone.utc).isoformat(),
        'providerApiCalls': 0, 'humanQualityVerified': False, 'newImageOrTimbreGenerated': False,
        'videoOrSpeakerRecordingPerformed': False, 'screenshotsCaptured': not args.no_screenshots}
    baseline = len(events())
    try:
        shell('am', 'force-stop', '--user', user, PACKAGE)
        shell('am', 'start', '-W', '--user', user, '-n', ACTIVITY, '--es', 'g_namespace', 'validation')
        wait(lambda e: e['kind'] == 'GEN_GATE' and e.get('visible') is True, baseline, 20)
        value = {'requestId': str(uuid.uuid4()), 'destination': {'name': '경포 바다', 'traits': '해안 산책과 작은 전시'},
            'purpose': '쉬면서 오늘의 기억을 간직하기', 'route': {'points': [[.1,.75],[.22,.31],[.43,.2],[.59,.6],[.8,.23],[.91,.38]]}}
        request_id = value['requestId']
        act('submit', g_input_json=json.dumps(value, ensure_ascii=False, separators=(',', ':')))
        ready = wait(lambda e: e['kind'] == 'GEN_READY' and e.get('requestId') == request_id, baseline, 120)
        check(ready['mode'] == 'OFFLINE_FIXTURE', 'Wrong native origin')
        birth_start = wait(lambda e: e['kind'] == 'GEN_ANIMATION' and e.get('requestId') == request_id and e.get('stage') == 'ROUTE_TRACE', baseline, 15)
        check(birth_start.get('progress') == 0, 'New image inherited a completed animation frame')
        prepared = wait(lambda e: e['kind'] == 'GEN_FORMATION_PREPARED' and e.get('requestId') == request_id, baseline, 15)
        check(prepared['progress'] == 0 and prepared['at'] <= birth_start['at'], 'Animation ran before its formation was prepared')
        wait(lambda e: e['kind'] == 'GEN_ANIMATION' and e.get('requestId') == request_id and e.get('stage') == 'COMPLETE', baseline, 15)
        artifact = get('/v2/jobs/' + request_id)['artifact']
        private_path = 'files/generated-companion-validation/' + request_id
        cached = json.loads(read_private(private_path + '/artifact.json'))
        check(cached == artifact, 'Server/native artifact differs')
        check(artifact['voiceManifest']['schemaVersion'] == 3, 'Not v3 voice media')
        for clip in artifact['voiceManifest']['clips']:
            data = read_private(private_path + '/media/' + clip['audioPath'], binary=True)
            check(hashlib.sha256(data).hexdigest() == clip['audioSha256'], 'Native WAV differs')
        image = artifact['visual']['asset']
        png = read_private(private_path + '/media/' + image['sha256'] + '.png', binary=True)
        check(hashlib.sha256(png).hexdigest() == image['sha256'], 'Native PNG differs')
        screen('ready')
        print('PASS native download, actual JSON, image/WAV hashes, birth animation', flush=True)

        def speech(action, expected, **kwargs):
            start = len(events()); act(action, confirm_quiet_test=True, **kwargs)
            request = wait(lambda e: e['kind'] == 'GEN_SPEECH_REQUEST', start, 10)
            event = wait(lambda e: e['kind'] == 'GEN_SPEECH' and e.get('requestId') == request['requestId'] and e.get('status') == expected, start, 35)
            return request, event

        greeting, _ = speech('greeting', 'COMPLETED')
        completed_before = len([e for e in events() if e['kind'] == 'GEN_SPEECH' and e.get('status') == 'STARTED'])
        start = len(events())
        followup = get('/v2/generation-capabilities')['fixtureFollowupText']
        act('followup', g_text=followup)
        added = wait(lambda e: e['kind'] == 'GEN_FOLLOWUP_READY', start, 90)
        check(added['bindingId'] == ready['bindingId'], 'Followup voice changed')
        check(len([e for e in events() if e['kind'] == 'GEN_SPEECH' and e.get('status') == 'STARTED']) == completed_before, 'Followup auto-played')
        _, repeated = speech('greeting', 'REJECTED')
        check(repeated['reason'] == 'REPEATED_TEXT', 'Catalog append reset playback policy')
        spoken_followup, _ = speech('followup_listen', 'COMPLETED')
        check(spoken_followup['profileId'] == greeting['profileId'], 'Followup profile changed')
        print('PASS actual playback, same voice followup, no auto speech, preserved repeat suppression', flush=True)

        start = len(events()); act('common', confirm_quiet_test=True)
        speaking = wait(lambda e: e['kind'] == 'GEN_SPEECH' and e.get('status') == 'STARTED', start, 15)
        act('stop')
        wait(lambda e: e['kind'] == 'GEN_SPEECH' and e.get('requestId') == speaking['requestId'] and e.get('status') == 'CANCELLED' and e.get('reason') == 'USER_CANCELLED', start, 10)
        act('arrive'); act('save')
        wait(lambda e: e['kind'] == 'GEN_SAVED' and e.get('requestId') == request_id, start, 10)
        start = len(events()); act('arrival', confirm_quiet_test=True)
        speaking = wait(lambda e: e['kind'] == 'GEN_SPEECH' and e.get('status') == 'STARTED', start, 15)
        # The Pleos home key can keep the app's persistent task visible. Open a
        # separate activity to exercise an actual onStop instead of assuming it.
        shell('am', 'start', '-W', '--user', user, '-a', 'android.settings.SETTINGS')
        cancelled = wait(lambda e: e['kind'] == 'GEN_SPEECH' and e.get('requestId') == speaking['requestId'] and e.get('status') == 'CANCELLED' and e.get('reason') in ('BACKGROUND', 'INACTIVE'), start, 15)
        wait(lambda e: e['kind'] == 'GEN_GATE' and e.get('foreground') is False and e.get('visible') is False, start, 10)
        print('PASS stop cancellation, arrival/save, background cancellation', flush=True)

        start = len(events()); shell('am', 'force-stop', '--user', user, PACKAGE)
        shell('am', 'start', '-W', '--user', user, '-n', ACTIVITY, '--es', 'g_namespace', 'validation')
        restored = wait(lambda e: e['kind'] == 'GEN_RESTORED' and e.get('requestId') == request_id, start, 20)
        wait(lambda e: e['kind'] == 'GEN_READY' and e.get('requestId') == request_id, start, 20)
        check(restored['imageSha256'] == image['sha256'] and restored['automaticSpeech'] is False, 'Restore changed companion')
        gate = wait(lambda e: e['kind'] == 'GEN_GATE' and e.get('visible') is True, start, 10)
        check(gate['quietConfirmed'] is False, 'Quiet consent persisted')
        check(not any(e['kind'] == 'GEN_SPEECH' and e.get('status') == 'STARTED' for e in events()[start:]), 'Restore auto-played')
        act('verify_boundaries')
        boundaries = wait(lambda e: e['kind'] == 'GEN_BOUNDARIES', start, 15)
        check(boundaries['passed'] == 10, 'Parser/store boundaries missing')
        check(json.loads(read_private(private_path + '/artifact.json')) == artifact, 'Final artifact changed')
        screen('cold-restored')
        proof.update(status='PASS_NATIVE_V2_FIXTURE_MEDIA_AND_LIFECYCLE', requestId=request_id,
            characterId=artifact['characterId'], imageSha256=image['sha256'], bindingId=ready['bindingId'],
            initialClips=3, newFollowupRecord=True, completedClips=[greeting['clipId'], spoken_followup['clipId']],
            boundaryChecks=boundaries['passed'], quietConsentRestored=False, automaticSpeechAfterRestore=False,
            initialBirthProgress=birth_start['progress'], formationDesign=birth_start['design'],
            formationPreparedBeforeAnimation=True,
            backgroundCancellationReason=cancelled['reason'],
            nativeSourceSha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(list((ROOT / 'android/app/src/debug/kotlin/ai/nunti/app/generated').glob('*.kt'))
                    + list((ROOT / 'android/feature/avatar/src/main/kotlin/ai/nunti/avatar').glob('Generated*.kt'))
                    + list((ROOT / 'android/feature/avatar/src/compose/kotlin/ai/nunti/avatar').glob('Generated*.kt')))})
        (output / 'artifact.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n')
        print('PASS cold restore, immutable collection, ten native boundary rejections', flush=True)
    except Exception as exc:
        proof['error'] = str(exc)
        screen('failed')
    finally:
        (output / 'events.jsonl').write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in events()[baseline:]) + '\n')
        (output / 'verification.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': proof['status'], 'error': proof.get('error'), 'evidence': str(output)}, ensure_ascii=False))
    return 0 if proof['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
