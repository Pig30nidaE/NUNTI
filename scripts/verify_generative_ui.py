#!/usr/bin/env python3
"""Type real fields, draw a touch route, press Create and play audio in the v2 APK."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ADB = ROOT / '.local/pm-tools/sdk/platform-tools/adb'
PACKAGE = 'ai.nunti.avatar.demo'
ACTIVITY = PACKAGE + '/ai.nunti.app.generated.GeneratedCompanionActivity'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--record-speaker', action='store_true')
    parser.add_argument('--record-video', action='store_true', help='Record the real route/create/listen screen without audio replacement.')
    parser.add_argument('--curved-route', action='store_true', help='Draw a continuous bent path with actual touch events.')
    args = parser.parse_args()
    output = ROOT / '.local/generative-mvp' / ('touch-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads((ROOT / '.local/generative-mvp/connection-offline_fixture.json').read_text())
    assert config['mode'] == 'OFFLINE_FIXTURE'
    assert config['baseUrl'] == 'http://127.0.0.1:8767'
    adb = [str(ADB), '-s', args.serial]

    def cmd(*parts, binary=False):
        value = subprocess.run(adb + list(parts), check=True, capture_output=True).stdout
        return value if binary else value.decode()

    def shell(*parts):
        return cmd('shell', shlex.join([str(x) for x in parts]))

    user = shell('am', 'get-current-user').strip()
    assert user.isdigit()

    def events():
        data = cmd('exec-out', 'run-as', PACKAGE, '--user', user, 'cat', 'files/generated-events.jsonl')
        return [json.loads(line) for line in data.splitlines() if line]

    def wait(predicate, start, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = next((e for e in events()[start:] if predicate(e)), None)
            if result:
                return result
            time.sleep(.25)
        raise AssertionError('Native UI timeout: ' + json.dumps(events()[start:][-5:], ensure_ascii=False))

    def tree():
        shell('uiautomator', 'dump', '/data/local/tmp/nunti-generated-ui.xml')
        return ET.fromstring(cmd('exec-out', 'cat', '/data/local/tmp/nunti-generated-ui.xml'))

    def bounds(**attributes):
        matches = [node for node in tree().iter('node') if all(node.get(k) == v for k, v in attributes.items())]
        assert len(matches) == 1, 'UI node not unique: ' + str(attributes)
        points = [int(n) for n in re.findall(r'\d+', matches[0].get('bounds', ''))]
        assert len(points) == 4 and points[2] > points[0] and points[3] > points[1]
        return points

    def tap(**attributes):
        x1, y1, x2, y2 = bounds(**attributes)
        shell('input', 'tap', (x1+x2)//2, (y1+y2)//2)

    proof = {'status': 'FAIL', 'mode': 'OFFLINE_FIXTURE', 'newImageOrTimbreGenerated': False,
        'humanListeningPerformed': False, 'providerApiCalls': 0}
    capture = None
    recorder = None
    recorder_pid = None
    remote_video = '/data/local/tmp/nunti-' + output.name + '.mp4'
    recording = None
    try:
        start = len(events())
        shell('am', 'force-stop', '--user', user, PACKAGE)
        shell('am', 'start', '-W', '--user', user, '-n', ACTIVITY, '--es', 'g_action', 'clear_input')
        wait(lambda e: e['kind'] == 'GEN_GATE' and e.get('visible') is True, start, 20)
        for label, text in [('어디로 떠나나요?', 'Seoul'), ('그곳의 느낌', 'River'), ('이번 여행의 목적', 'Rest')]:
            tap(**{'content-desc': label})
            shell('input', 'text', text)
        shell('input', 'keyevent', 'KEYCODE_BACK')
        if args.record_video:
            started_epoch_ns = time.time_ns()
            remote_command = 'echo $$; exec screenrecord --size 1280x720 --bit-rate 4000000 --time-limit 90 ' + shlex.quote(remote_video)
            recorder = subprocess.Popen(adb + ['shell', shlex.join(['sh', '-c', remote_command])],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            recorder_pid = recorder.stdout.readline().strip()
            assert recorder_pid.isdigit() and int(recorder_pid) > 1, 'Screen recorder PID missing'
            recording = {'source': 'ACTUAL_ANDROID_SCREENRECORD', 'startedEpochNs': started_epoch_ns,
                'timingLimit': 'Host command start is approximate; no audiovisual latency claim.'}
            time.sleep(.6)
        x1, y1, x2, y2 = bounds(**{'content-desc': '여정 경로 입력'})
        if args.curved_route:
            points = [(.12,.78),(.21,.68),(.25,.43),(.36,.27),(.49,.34),(.61,.59),(.76,.60),(.89,.20)]
            actual_points = [(round(x1+(x2-x1)*x), round(y1+(y2-y1)*y)) for x,y in points]
            shell('input', 'motionevent', 'DOWN', *actual_points[0])
            for point in actual_points[1:]:
                shell('input', 'motionevent', 'MOVE', *point)
            shell('input', 'motionevent', 'UP', *actual_points[-1])
        else:
            shell('input', 'swipe', x1+(x2-x1)//6, y1+4*(y2-y1)//5,
                x1+5*(x2-x1)//6, y1+(y2-y1)//5, 800)
        (output / 'typed-route.png').write_bytes(cmd('exec-out', 'screencap', '-p', binary=True))
        tap(text='동반자 만나기')
        submitted = wait(lambda e: e['kind'] == 'GEN_SUBMITTED' and e.get('namespace') == 'generated-companion', start, 20)
        request_id = submitted['requestId']
        ready = wait(lambda e: e['kind'] == 'GEN_READY' and e.get('requestId') == request_id, start, 120)
        wait(lambda e: e['kind'] == 'GEN_ANIMATION' and e.get('requestId') == request_id and e.get('stage') == 'COMPLETE', start, 15)
        req = urllib.request.Request(config['baseUrl'] + '/v2/jobs/' + request_id,
            headers={'Authorization': 'Bearer ' + config['token']})
        with urllib.request.urlopen(req, timeout=10) as response:
            artifact = json.loads(response.read(524288))['data']['artifact']
        actual = json.loads(artifact['inputCanonical'])
        assert actual['destination'] == {'name': 'Seoul', 'traits': 'River'} and actual['purpose'] == 'Rest'
        assert len(actual['route']['points']) > 3 and ready['mode'] == 'OFFLINE_FIXTURE'
        (output / 'ready.png').write_bytes(cmd('exec-out', 'screencap', '-p', binary=True))
        print('PASS actual text fields, touchscreen route, Create button and server input join', flush=True)
        tap(text='음성 시험 시작')
        if args.record_speaker:
            runtime = ROOT / '.local/voice-runtime/venv/bin/python'
            with (output / 'speaker-capture.log').open('w') as log:
                capture = subprocess.Popen([str(runtime), str(ROOT / 'scripts/record_emulator_audio.py'),
                    '--serial', args.serial, '--seconds', '16', '--output', str(output / 'speaker.wav')],
                    stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if capture.poll() is not None:
                    raise AssertionError('Speaker capture stopped before playback')
                packets = output / 'speaker.packets.jsonl'
                if packets.exists() and packets.stat().st_size > 0:
                    break
                time.sleep(.1)
            else:
                raise AssertionError('No authenticated speaker packets')
        play_start = len(events()); tap(text='인사 듣기')
        speech = wait(lambda e: e['kind'] == 'GEN_SPEECH_REQUEST', play_start, 15)
        wait(lambda e: e['kind'] == 'GEN_SPEECH' and e.get('requestId') == speech['requestId'] and e.get('status') == 'COMPLETED', play_start, 30)
        clip = next(c for c in artifact['voiceManifest']['clips'] if c['clipId'] == speech['clipId'])
        assert speech['audioSha256'] == clip['audioSha256'] and speech['profileId'] == clip['profileId']
        proof.update(status='PASS_REAL_FIELDS_GESTURE_BUTTON_AND_AUDIO', requestId=request_id,
            characterId=artifact['characterId'], routePoints=len(actual['route']['points']),
            routeScenario='CURVED_TOUCH' if args.curved_route else 'STRAIGHT_SWIPE',
            imageSha256=artifact['visual']['asset']['sha256'], clipId=clip['clipId'], audioSha256=clip['audioSha256'])
        if capture:
            assert capture.wait(timeout=25) == 0
            summary = json.loads((output / 'speaker.summary.json').read_text())
            assert summary['nonzeroSamples'] > 0 and summary['source'] == 'AUTHENTICATED_EMULATOR_SPEAKER_STREAM'
            proof['speakerCapture'] = {key: summary[key] for key in ('source', 'nonzeroSamples', 'peak', 'sha256', 'evidenceLevel')}
        proof['apkSha256'] = hashlib.sha256((ROOT / '.local/generative-mvp/Nunti-Generative-MVP-debug.apk').read_bytes()).hexdigest()
        (output / 'artifact.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n')
    except Exception as exc:
        proof.update(status='FAIL', error=str(exc))
    finally:
        if capture and capture.poll() is None:
            capture.terminate(); capture.wait(timeout=10)
        if recorder:
            try:
                if recorder.poll() is None:
                    shell('kill', '-2', recorder_pid)
                _, error = recorder.communicate(timeout=12)
                assert recorder.returncode == 0, 'Android screenrecord failed: ' + error[-300:]
                raw_video = cmd('exec-out', 'cat', remote_video, binary=True)
                assert len(raw_video) > 1000 and b'ftyp' in raw_video[:32], 'Recorded MP4 is invalid'
                (output / 'screen-silent.mp4').write_bytes(raw_video)
                recording.update(sha256=hashlib.sha256(raw_video).hexdigest(), bytes=len(raw_video))
                proof['screenRecording'] = recording
                shell('rm', remote_video)
            except Exception as exc:
                proof.update(status='FAIL', videoError=str(exc))
        (output / 'events.jsonl').write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in events()[start:]) + '\n')
        (output / 'verification.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': proof['status'], 'error': proof.get('error'), 'evidence': str(output)}, ensure_ascii=False))
    return 0 if proof['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
