#!/usr/bin/env python3
"""Exercise fresh route submissions in the installed native route-born debug host.

Emulator only, namespace isolated. Uses real Car/foreground/audio observations,
existing single voice queue and fresh append-only events. Does not modify vehicle
state, clear app data, install an APK, kill a bridge/model, or edit private state.
Each --input is actually POSTed by the app; a new UUID can create local model work.
Coordinate access to the emulator before running. Screenshots need human review.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
from urllib.request import urlopen
from urllib.parse import urlsplit
import uuid

from verify_http import canonical, require, sha, validate_visual

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'ai.nunti.avatar.demo'
COMPONENT = PACKAGE + '/ai.nunti.app.routebirth.RouteBirthActivity'
NAMESPACE = 'route-birth-validation'
EVENT_FILE = 'files/route-born-events.jsonl'
PROVIDER = 'qwen3-tts-sohee-local'


def now():
    return datetime.now(timezone.utc).isoformat()


class Device:
    def __init__(self, args, output):
        self.args, self.output = args, output
        self.prefix = [args.adb, '-s', args.serial]
        self.number = 0

    def run(self, *command, binary=False, missing=False):
        self.number += 1
        result = subprocess.run(self.prefix + list(command), capture_output=True, timeout=25)
        stderr = result.stderr.decode(errors='replace')
        safe = list(command)
        for index, token in enumerate(safe):
            if token == 'rb_input_json' and index + 1 < len(safe):
                safe[index + 1] = '<private-input-sha256:' + sha(safe[index + 1].encode()) + '>'
        with (self.output / 'commands.jsonl').open('a') as stream:
            stream.write(json.dumps({'number': self.number, 'at': now(), 'command': safe,
                                     'exitCode': result.returncode, 'stderr': stderr[-1200:]}) + '\n')
        if result.returncode:
            if missing and 'No such file' in stderr + result.stdout.decode(errors='replace'):
                return b'' if binary else ''
            raise AssertionError('ADB command failed: ' + ' '.join(safe[:5]))
        require(len(result.stdout) <= 20_971_520, 'ADB output size limit')
        return result.stdout if binary else result.stdout.decode()

    def start(self, action=None, quiet=False, input_value=None, request_id=None):
        command = ['shell', 'am', 'start', '--user', str(self.args.user), '-W', '-f', '0x14000000', '-n', COMPONENT,
                   '--es', 'rb_namespace', 'validation']
        if action:
            require(re.fullmatch('[a-z_]+', action), 'Invalid test action')
            command += ['--es', 'rb_action', action]
        if quiet:
            command += ['--ez', 'confirm_quiet_test', 'true']
        if input_value is not None:
            command += ['--es', 'rb_input_json', shlex.quote(canonical(input_value).decode())]
        if request_id:
            require(str(uuid.UUID(request_id)) == request_id, 'Invalid restore UUID')
            command += ['--es', 'rb_request_id', request_id]
        value = self.run(*command)
        require('Error:' not in value and 'Exception' not in value, 'Activity launch failed')

    def screenshot(self, name):
        directory = self.output / 'screenshots'
        directory.mkdir(exist_ok=True)
        data = self.run('exec-out', 'screencap', '-p', binary=True)
        require(data.startswith(b'\x89PNG\r\n\x1a\n'), 'Screenshot is not PNG')
        path = directory / (name + '.png')
        path.write_bytes(data)
        return {'file': str(path.relative_to(self.output)), 'sha256': sha(data), 'pixelInspection': 'NOT_PERFORMED'}

    def private(self, path, missing=False, binary=False):
        require(path.startswith('files/route-birth-validation') or path == EVENT_FILE, 'Non-validation private path refused')
        return self.run('exec-out', 'run-as', PACKAGE, '--user', str(self.args.user), 'cat', path,
                        missing=missing, binary=binary)


class Events:
    def __init__(self, device, output):
        self.device, self.output = device, output
        self.lines = self.read_lines()
        self.values = []
        (output / 'events-before-run.jsonl').write_text('\n'.join(self.lines) + ('\n' if self.lines else ''))

    def read_lines(self):
        value = self.device.private(EVENT_FILE, missing=True)
        lines = value.splitlines()
        if lines and not value.endswith('\n'):
            lines.pop()
        return [line for line in lines if line.strip()]

    def pull(self):
        lines = self.read_lines()
        require(lines[:len(self.lines)] == self.lines, 'Event file rotated or truncated; cursor invalid')
        fresh = []
        for line in lines[len(self.lines):]:
            value = json.loads(line)
            if value.get('namespace') == NAMESPACE:
                require(isinstance(value.get('kind'), str) and isinstance(value.get('at'), str), 'Malformed event')
                datetime.fromisoformat(value['at'].replace('Z', '+00:00'))
                fresh.append(value)
        self.lines = lines
        self.values.extend(fresh)
        with (self.output / 'runtime-events.jsonl').open('a') as stream:
            for value in fresh:
                stream.write(json.dumps(value, ensure_ascii=True, separators=(',', ':')) + '\n')
        errors = [v for v in fresh if v['kind'] == 'RB_ERROR']
        require(not errors, 'Host RB_ERROR: ' + str(errors[-1].get('reason')) if errors else '')
        return fresh

    def cursor(self):
        self.pull()
        return len(self.values)

    def wait(self, offset, predicate, label, timeout=40):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.pull()
            values = [v for v in self.values[offset:] if predicate(v)]
            if values:
                return values[-1]
            time.sleep(.12)
        raise AssertionError('Timed out: ' + label)

    def silent(self, offset, seconds=2):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.pull()
            require(not any(v['kind'] == 'RB_SPEECH_REQUEST' or (v['kind'] == 'RB_SPEECH' and v.get('status') in {'QUEUED', 'STARTED'})
                            for v in self.values[offset:]), 'Automatic speech observed')
            time.sleep(.15)
        return {'secondsAtLeast': seconds, 'fromCursor': offset, 'toCursor': len(self.values)}


class Audit:
    def __init__(self, args, out):
        self.args, self.out = args, out
        self.device, self.events = Device(args, out), None
        self.checks, self.screenshots = [], []

    def record(self, label, **detail):
        self.checks.append({'check': label, 'ok': True, **detail})
        print(json.dumps({'state': 'PASS', 'check': label}), flush=True)

    def preflight(self):
        require(re.fullmatch('emulator-[0-9]+', self.args.serial), 'Explicit emulator serial required')
        hardware = self.device.run('shell', 'getprop', 'ro.hardware').strip()
        require('ranchu' in hardware or 'goldfish' in hardware, 'Only emulator test hooks allowed')
        actual_user = int(self.device.run('shell', 'am', 'get-current-user').strip())
        require(actual_user == self.args.user, 'Wrong actual foreground Android user')
        self.events = Events(self.device, self.out)
        self.device.run('shell', 'am', 'force-stop', '--user', str(self.args.user), PACKAGE)
        offset = self.events.cursor()
        self.device.start()
        self.parked(offset)
        self.events.silent(offset)
        self.screenshots.append(self.device.screenshot('input-or-restored-initial'))
        self.record('isolated native emulator entry and silent startup', hardware=hardware, user=actual_user)

    def parked(self, offset=0, quiet=False):
        end = time.monotonic() + 40
        while time.monotonic() < end:
            self.events.pull()
            gates = [v for v in self.events.values if v['kind'] == 'RB_GATE']
            if gates:
                value = gates[-1]
                if (value.get('source') == 'ACTUAL_CAR_SERVICE' and value.get('foreground') is True
                        and value.get('visible') is True and value.get('parked') is True
                        and value.get('knownUX') is True and value.get('requiresDO') is False
                        and (not quiet or value.get('quietAccepted') is True)):
                    return value
            time.sleep(.12)
        raise AssertionError('Timed out: latest actual parked/known-UX/foreground/quiet gate')

    def load_artifact(self, request_id):
        value = json.loads(self.device.private('files/' + NAMESPACE + '/' + request_id + '/artifact.json'))
        require(value['journeyId'] == request_id, 'Private artifact journey mismatch')
        proof = validate_visual(value['visual'])
        clips = value['voiceManifest']['clips']
        require(len(clips) == 3, 'Missing local voice clips')
        for clip in clips:
            path = 'files/' + NAMESPACE + '/' + request_id + '/voice/' + clip['audioPath']
            data = self.device.private(path, binary=True)
            require(sha(data) == clip['audioSha256'], 'Installed audio bytes differ from manifest')
            require(clip['characterId'] == value['characterId'] and clip['profileId'] == value['voice']['profileId']
                    and clip['source']['bindingId'] == value['voice']['bindingId'], 'Installed visual/voice binding mismatch')
        proof['nativeSerializedVisualSha256'] = sha(json.dumps(value['visual'], ensure_ascii=False, separators=(',', ':')).encode())
        return value, proof

    def submission(self, input_value, index):
        offset = self.events.cursor()
        request_id = input_value['requestId']
        self.device.start('submit', input_value=input_value)
        submitted = self.events.wait(offset, lambda v: v['kind'] == 'RB_SUBMITTED' and v['requestId'] == request_id, 'fresh native POST')
        require(submitted['pointCount'] == len(input_value['route']['points']), 'Native route point count differs')
        visual = self.events.wait(offset, lambda v: v['kind'] == 'RB_VISUAL' and v['requestId'] == request_id, 'actual generated visual', self.args.timeout)
        for stage in ('ROUTE_TRACE', 'ROUTE_TO_BODY', 'FACE_REVEAL', 'COMPLETE'):
            value = self.events.wait(offset, lambda v: v['kind'] == 'RB_ANIMATION' and v['requestId'] == request_id
                                     and v.get('stage') == stage, 'native animation ' + stage, self.args.timeout)
            self.screenshots.append({'requestId': request_id, 'observedStageEvent': value,
                                     **self.device.screenshot('case-' + str(index) + '-' + stage.lower())})
        ready = self.events.wait(offset, lambda v: v['kind'] == 'RB_READY' and v['requestId'] == request_id,
                                 'exact native downloaded voice ready', self.args.timeout)
        artifact, proof = self.load_artifact(request_id)
        require(visual['characterId'] == ready['characterId'] == artifact['characterId']
                and ready['bindingId'] == artifact['voice']['bindingId']
                and visual['visualSha256'] == ready['visualSha256'] == proof['nativeSerializedVisualSha256'],
                'Native visual/ready artifact identity mismatch')
        # Compare exact request canonicalization without importing generator.
        normalized = json.loads(json.dumps(input_value))
        normalized['route']['points'] = [[float(p[0]) + 0.0, float(p[1]) + 0.0] for p in normalized['route']['points']]
        require(sha(canonical(normalized)) == artifact['inputSha256'], 'Actual input-to-artifact digest mismatch')
        require(artifact['destinationName'] == input_value['destination']['name'] and artifact['purpose'] == input_value['purpose'],
                'Native destination/purpose artifact mismatch')
        self.events.silent(offset)
        (self.out / ('artifact-' + request_id + '.json')).write_bytes(canonical(artifact) + b'\n')
        self.record('fresh input route/animation/voice runtime join ' + str(index), requestId=request_id,
                    submitted=submitted, visual=visual, ready=ready, **proof)
        return artifact

    def speak(self, artifact, category, terminal='COMPLETED', quiet=True):
        # AudioManager can report the previous player tail briefly; wait for a
        # fresh quiet accepted gate rather than changing queue eligibility.
        offset = self.events.cursor()
        self.device.start('poll', quiet=quiet)
        self.parked(offset if quiet else 0, quiet=quiet)
        offset = self.events.cursor()
        self.device.start(category, quiet=quiet)
        request = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH_REQUEST', 'fresh ' + category + ' request')
        clip = next(c for c in artifact['voiceManifest']['clips'] if c['clipId'] == artifact['characterId'] + '-' + category)
        require(request['tripId'] == artifact['journeyId'] and request['clipId'] == clip['clipId']
                and all(request[k] == clip[k] for k in ('characterId', 'profileId', 'audioSha256')), 'Speech request identity differs')
        started = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH' and v['requestId'] == request['requestId']
                                   and v.get('status') in {'STARTED', 'REJECTED', 'FAILED'}, 'same-request speech STARTED')
        require(started['status'] == 'STARTED' and started['providerId'] == PROVIDER and started['profileId'] == clip['profileId'],
                'Playback did not use exact local voice: ' + str(started))
        if terminal:
            finished = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH' and v['requestId'] == request['requestId']
                                        and v.get('status') in {'COMPLETED', 'CANCELLED', 'FAILED', 'REJECTED'},
                                        'same-request speech terminal', 45)
            require(finished['status'] == terminal, 'Speech terminal differs: ' + str(finished))
        else:
            finished = None
        return {'request': request, 'started': started, 'terminal': finished, 'fromCursor': offset}

    def save_restore(self, artifact):
        request_id = artifact['journeyId']
        offset = self.events.cursor()
        self.device.start('arrive')
        self.events.wait(offset, lambda v: v['kind'] == 'RB_ARRIVED' and v['requestId'] == request_id, 'actual arrival')
        arrival = self.speak(artifact, 'arrival')
        offset = self.events.cursor()
        self.device.start('save')
        saved = self.events.wait(offset, lambda v: v['kind'] == 'RB_SAVED' and v['requestId'] == request_id, 'local collection save')
        before = self.device.private('files/' + NAMESPACE + '/state.json')
        self.device.run('shell', 'am', 'force-stop', '--user', str(self.args.user), PACKAGE)
        offset = self.events.cursor()
        self.device.start()
        restored = self.events.wait(offset, lambda v: v['kind'] == 'RB_RESTORED' and v['requestId'] == request_id, 'cold-process exact identity restore')
        ready = self.events.wait(offset, lambda v: v['kind'] == 'RB_READY' and v['requestId'] == request_id, 'restored local voice ready')
        require(restored['arrived'] is True and restored['automaticSpeech'] is False
                and restored['characterId'] == artifact['characterId'] and ready['bindingId'] == artifact['voice']['bindingId'],
                'Restored selected/arrived/voice identity differs')
        require(before == self.device.private('files/' + NAMESPACE + '/state.json'), 'Restoration changed saved state')
        self.events.silent(offset)
        self.record('arrival, collection and cold-process identity restore', saved=saved, restored=restored, arrival=arrival,
                    stateSha256=sha(before.encode()))

    def stop_background(self, artifact):
        offset = self.events.cursor()
        self.device.start('restore', request_id=artifact['journeyId'])
        self.events.wait(offset, lambda v: v['kind'] == 'RB_READY' and v['requestId'] == artifact['journeyId'], 'voice bind after explicit restore')
        playing = self.speak(artifact, 'common', terminal=None)
        offset = self.events.cursor()
        self.device.start('stop')
        stopped = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH' and v['requestId'] == playing['request']['requestId']
                                   and v.get('status') in {'COMPLETED', 'CANCELLED', 'FAILED'}, 'native stop terminal')
        require(stopped['status'] == 'CANCELLED' and stopped.get('reason') == 'USER_CANCELLED', 'Stop did not cancel active request')
        self.events.silent(offset)
        self.record('explicit user stop cancels active voice without replay', playing=playing, stopped=stopped)
        # Create an independent runtime session by a real force-stop, not a
        # synthetic queue reset. A different greeting remains a user action.
        self.device.run('shell', 'am', 'force-stop', '--user', str(self.args.user), PACKAGE)
        offset = self.events.cursor()
        self.device.start()
        self.events.wait(offset, lambda v: v['kind'] == 'RB_READY' and v['requestId'] == artifact['journeyId'], 'cold restore ready')
        playing = self.speak(artifact, 'greeting', terminal=None)
        offset = self.events.cursor()
        opened = self.device.run('shell', 'am', 'start', '--user', str(self.args.user), '-a', 'android.settings.SETTINGS')
        require('Error:' not in opened, 'Settings did not open')
        background = self.events.wait(offset, lambda v: v['kind'] == 'RB_GATE' and v.get('foreground') is False, 'actual foreground=false')
        terminal = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH' and v['requestId'] == playing['request']['requestId']
                                    and v.get('status') in {'COMPLETED', 'CANCELLED', 'FAILED'}, 'actual background cancellation')
        require(terminal['status'] == 'CANCELLED' and terminal.get('reason') in {'BACKGROUND', 'SPEECH_NOT_ALLOWED', 'INACTIVE'},
                'Foreground loss did not cancel active request')
        offset = self.events.cursor()
        self.device.start()
        self.events.wait(offset, lambda v: v['kind'] == 'RB_GATE' and v.get('foreground') is True and v.get('quietConfirmed') is False,
                         'silent return with quiet consent reset')
        self.events.silent(offset)
        self.record('real background cancels and return stays silent', playing=playing, background=background, terminal=terminal)

    def queue_stop_and_block(self, artifacts):
        artifact = max(artifacts, key=lambda value: max(c['durationMs'] for c in value['voiceManifest']['clips']
                                                        if c['clipId'].endswith('-greeting')))
        offset = self.events.cursor()
        self.device.start('restore', request_id=artifact['journeyId'])
        self.events.wait(offset, lambda v: v['kind'] == 'RB_READY' and v['requestId'] == artifact['journeyId'], 'independent queue session ready')
        playing = self.speak(artifact, 'greeting', terminal=None)
        offset = self.events.cursor()
        self.device.start('greeting', quiet=True)
        duplicate = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH_REQUEST', 'duplicate user submission')
        rejected = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH' and v['requestId'] == duplicate['requestId'],
                                    'duplicate text rejection')
        require(rejected['status'] == 'REJECTED' and rejected.get('reason') == 'DUPLICATE_TEXT', 'Duplicate did not reject')
        offset = self.events.cursor()
        self.device.start('common', quiet=True)
        pending = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH_REQUEST', 'second distinct queued user submission')
        queued = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH' and v['requestId'] == pending['requestId'], 'pending common queued')
        require(queued['status'] == 'QUEUED', 'Second clip did not queue')
        self.events.pull()
        require([v['status'] for v in self.events.values if v['kind'] == 'RB_SPEECH'
                 and v['requestId'] == playing['request']['requestId']] == ['QUEUED', 'STARTED'], 'Greeting no longer active before stop')
        require([v['status'] for v in self.events.values if v['kind'] == 'RB_SPEECH'
                 and v['requestId'] == pending['requestId']] == ['QUEUED'], 'Common no longer pending before stop')
        offset = self.events.cursor()
        self.device.start('stop')
        terminals = []
        for value in (playing['request'], pending):
            terminal = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH' and v['requestId'] == value['requestId']
                                        and v.get('status') in {'COMPLETED', 'CANCELLED', 'FAILED'}, 'active/pending stop terminal')
            require(terminal['status'] == 'CANCELLED' and terminal.get('reason') == 'USER_CANCELLED', 'Stop did not cancel active and pending')
            terminals.append(terminal)
        self.events.silent(offset)
        self.record('duplicate suppression and stop cancels active plus pending voice', playing=playing, duplicate=duplicate,
                    rejected=rejected, pending=pending, queued=queued, terminals=terminals)
        offset = self.events.cursor()
        self.device.start('restore', request_id=artifact['journeyId'])
        self.events.wait(offset, lambda v: v['kind'] == 'RB_READY' and v['requestId'] == artifact['journeyId'], 'independent policy session ready')
        playing = self.speak(artifact, 'greeting', terminal=None)
        offset = self.events.cursor()
        self.device.start('block')
        blocked = self.events.wait(offset, lambda v: v['kind'] == 'RB_GATE' and v.get('visible') is False, 'additional policy block')
        terminal = self.events.wait(offset, lambda v: v['kind'] == 'RB_SPEECH' and v['requestId'] == playing['request']['requestId']
                                    and v.get('status') in {'COMPLETED', 'CANCELLED', 'FAILED'}, 'policy cancellation')
        require(terminal['status'] == 'CANCELLED' and terminal.get('reason') == 'SPEECH_NOT_ALLOWED', 'Policy did not cancel active voice')
        rejected_offset = self.events.cursor()
        self.device.start('greeting', quiet=True)
        self.events.silent(rejected_offset)
        offset = self.events.cursor()
        self.device.start('unblock')
        self.parked(offset)
        self.events.silent(offset)
        self.record('policy block cancels, prevents new requests, and returns silently', playing=playing, gate=blocked, terminal=terminal)

    def run_policies(self, inputs):
        self.preflight()
        value = inputs[0]
        offset = self.events.cursor()
        self.device.start('submit', input_value=value)
        stage = self.events.wait(offset, lambda v: v['kind'] == 'RB_ANIMATION' and v['requestId'] == value['requestId']
                                 and v.get('stage') == 'ROUTE_TO_BODY', 'cached replay morph stage')
        time.sleep(.9)
        screenshot = self.device.screenshot('cached-animation-900ms-into-route-to-body')
        self.screenshots.append({'requestId': value['requestId'], 'observedStageEvent': stage,
                                 'delayAfterStageObservedSeconds': .9, **screenshot})
        self.events.wait(offset, lambda v: v['kind'] == 'RB_READY' and v['requestId'] == value['requestId'], 'cached replay voice ready')
        self.events.wait(offset, lambda v: v['kind'] == 'RB_ANIMATION' and v['requestId'] == value['requestId']
                         and v.get('stage') == 'COMPLETE', 'cached replay animation complete')
        self.record('cached replay native intermediate morph capture', screenshot=screenshot, freshGeneration=False,
                    requestId=value['requestId'], stage=stage)
        artifacts = [self.load_artifact(value['requestId'])[0] for value in inputs]
        self.stop_background(artifacts[-1])
        self.queue_stop_and_block(artifacts)
        self.screenshots.append(self.device.screenshot('queue-policy-final-no-auto-speech'))

    def run(self, inputs):
        self.preflight()
        artifacts = []
        for index, value in enumerate(inputs):
            artifact = self.submission(value, index)
            if index == 0:
                boundary_offset = self.events.cursor()
                self.device.start('verify_boundaries')
                boundaries = self.events.wait(boundary_offset, lambda v: v['kind'] == 'RB_BOUNDARIES', 'real Android parser/storage negative checks')
                require(boundaries.get('passed') == len(boundaries.get('checks', [])) and boundaries.get('passed', 0) >= 9,
                        'Android boundary check failed')
                self.record('actual Android parser and immutable storage boundary checks', event=boundaries)
            greeting = self.speak(artifact, 'greeting')
            self.record('new native character greeting playback ' + str(index), **greeting)
            self.save_restore(artifact)
            artifacts.append(artifact)
        require(len({a['characterId'] for a in artifacts}) == len(artifacts), 'Native cases reused character identity')
        require(len({sha(canonical(a['visual']['outline'])) for a in artifacts}) == len(artifacts), 'Native cases reused exact outline')
        self.stop_background(artifacts[-1])
        self.queue_stop_and_block(artifacts)
        self.screenshots.append(self.device.screenshot('final-restored-no-auto-speech'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default=str(ROOT / '.local/pm-tools/sdk/platform-tools/adb'))
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--user', type=int, default=10)
    parser.add_argument('--input', action='append', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=900)
    parser.add_argument('--policies-only', action='store_true', help='Existing validation artifacts only; no new model jobs')
    args = parser.parse_args()
    if not 0 <= args.user <= 1000 or not 5 <= args.timeout <= 1800:
        parser.error('Invalid user or timeout')
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'startedAt': now(), 'status': 'FAIL', 'namespace': NAMESPACE,
              'scope': 'Actual native input POST, route-born rendering stages, installed WAV identity, local playback and lifecycle',
              'vehicleStateChangedByTool': False, 'notVerified': ['Human screenshot review', 'Acoustic PCM capture or human listening',
              'Physical vehicle behavior', 'Actual D/P transition', 'Perceptual uniqueness, cuteness, collectibility or naturalness']}
    audit = Audit(args, out)
    try:
        values = [json.loads(path.read_text()) for path in args.input]
        require(len(values) >= 1 and len({v['requestId'] for v in values}) == len(values), 'Distinct inputs required')
        if args.policies_only:
            audit.run_policies(values)
            report['status'] = 'PASS_NATIVE_ROUTE_BIRTH_QUEUE_AND_POLICY'
        else:
            audit.run(values)
            report['status'] = 'PASS_NATIVE_ROUTE_BIRTH_INPUT_VISUAL_VOICE_AND_RESTORE'
    except (AssertionError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        report['error'] = str(error)
    finally:
        report.update(finishedAt=now(), checks=audit.checks, screenshots=audit.screenshots)
        if audit.events:
            report['freshEventCount'] = len(audit.events.values)
        (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'error': report.get('error'), 'report': str(out / 'verification.json')}, ensure_ascii=False), flush=True)
    return 0 if report['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
