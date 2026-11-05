#!/usr/bin/env python3
"""Independent loopback route-born API/schema and committed artifact verifier.

Default mode sends only deliberately invalid inputs and reads health. --submit
explicitly adds real synthesis jobs; --inspect ID reads an existing job without
creating one. Standard library only; never imports generator code or weakens
vehicle, identity or voice policies. Each run needs a new evidence directory.
"""
from __future__ import annotations

import argparse
import bisect
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import uuid
import wave

ROOT = Path(__file__).resolve().parents[2]
PROVIDER = 'qwen3-tts-sohee-local'
HEX64 = re.compile(r'[0-9a-f]{64}')


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class API:
    def __init__(self, origin, out):
        self.origin, self.out = origin.rstrip('/'), out
        self.calls = []

    def request(self, method, path, data=None, raw=None):
        require(path.startswith('/'), 'API path must be absolute')
        body = raw if raw is not None else (canonical(data) if data is not None else None)
        request = Request(self.origin + path, data=body, method=method,
                          headers={'Content-Type': 'application/json'} if body is not None else {})
        started = now()
        try:
            with urlopen(request, timeout=12) as response:
                status, response_body = response.status, response.read(8_388_609)
        except HTTPError as error:
            status, response_body = error.code, error.read(8_388_609)
        require(len(response_body) <= 8_388_608, 'API response exceeds evidence limit')
        record = {'at': started, 'method': method, 'path': path, 'status': status,
                  'requestSha256': sha(body) if body is not None else None,
                  'responseSha256': sha(response_body), 'responseBytes': len(response_body)}
        self.calls.append(record)
        with (self.out / 'calls.jsonl').open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=True) + '\n')
        return status, response_body

    def json(self, method, path, data=None, raw=None):
        status, body = self.request(method, path, data=data, raw=raw)
        try:
            value = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise AssertionError('Non-JSON API response for ' + path) from None
        require(isinstance(value, dict), 'API response must be an object')
        return status, value


def request_input(points=None, destination='QA 호숫가', purpose='차분한 산책'):
    return {'requestId': str(uuid.uuid4()), 'destination': {'name': destination, 'traits': '물빛과 산책길'},
            'purpose': purpose, 'route': {'points': points or [[.10, .80], [.3, .6], [.55, .65], [.8, .2]]}}


def invalid_inputs():
    values = []
    def add(label, change):
        value = request_input()
        change(value)
        values.append((label, value))
    add('missing_route', lambda v: v.pop('route'))
    add('extra_root_field', lambda v: v.update(ignored='must reject'))
    add('missing_uuid', lambda v: v.pop('requestId'))
    add('invalid_uuid', lambda v: v.update(requestId='not-a-uuid'))
    add('empty_name', lambda v: v['destination'].update(name=''))
    add('whitespace_name', lambda v: v['destination'].update(name='   '))
    add('name_utf16_62', lambda v: v['destination'].update(name='🌙' * 31))
    add('traits_utf16_242', lambda v: v['destination'].update(traits='🌙' * 121))
    add('purpose_utf16_122', lambda v: v.update(purpose='🌙' * 61))
    add('name_wrong_type', lambda v: v['destination'].update(name=3))
    add('extra_destination_field', lambda v: v['destination'].update(lat=37))
    add('one_point', lambda v: v['route'].update(points=[[.1, .1]]))
    add('repeated_nonzero_absent', lambda v: v['route'].update(points=[[.5, .5], [.5, .5]]))
    add('too_many_points', lambda v: v['route'].update(points=[[i / 512, i / 512] for i in range(513)]))
    add('out_of_bounds', lambda v: v['route'].update(points=[[.1, .1], [1.001, .5]]))
    add('negative_coordinate', lambda v: v['route'].update(points=[[-.001, .1], [.5, .5]]))
    add('boolean_coordinate', lambda v: v['route'].update(points=[[False, .1], [.5, .5]]))
    add('string_coordinate', lambda v: v['route'].update(points=[['0.1', .1], [.5, .5]]))
    add('wrong_point_dimension', lambda v: v['route'].update(points=[[.1, .1, .2], [.5, .5]]))
    add('extra_route_field', lambda v: v['route'].update(seed=0))
    add('unpaired_unicode_surrogate', lambda v: v['destination'].update(name='\ud800'))
    return values


def inside_polygon(point, polygon):
    x, y = point
    inside = False
    for index, a in enumerate(polygon):
        b = polygon[(index + 1) % len(polygon)]
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def assert_face_containment(outline, face):
    # Same explicit normalized ellipse promised by the native renderer. This
    # independent edge-distance check covers the entire ellipse, not samples.
    cx, cy, scale = face['cx'], face['cy'], face['scale']
    require(inside_polygon((cx, cy), outline), 'Face center is outside body')
    transformed = [((p[0] - cx) / (.22 * scale), (p[1] - cy) / (.145 * scale)) for p in outline]
    minimum = float('inf')
    for index, a in enumerate(transformed):
        b = transformed[(index + 1) % len(transformed)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        denominator = dx * dx + dy * dy
        require(denominator > 0, 'Degenerate outline edge')
        position = max(0.0, min(1.0, -(a[0] * dx + a[1] * dy) / denominator))
        minimum = min(minimum, math.hypot(a[0] + position * dx, a[1] + position * dy))
    require(minimum >= 1 - 1e-7, 'Body edge crosses complete face ellipse')
    return minimum


def validate_visual(visual):
    require(visual['version'] == 'route-born-1', 'Unexpected visual version')
    require(not any(key in visual for key in ('bodyFamily', 'shapeId')), 'Preset body/shape found in route artifact')
    for name in ('outline', 'route'):
        points = visual[name]
        require(isinstance(points, list) and len(points) == 72, 'Expected 72 ' + name + ' points')
        low, high = (.05 - 1e-7, .95 + 1e-7) if name == 'outline' else (0, 1)
        require(all(isinstance(p, list) and len(p) == 2 and all(finite_number(v) and low <= v <= high for v in p)
                    for p in points), 'Invalid normalized ' + name + ' coordinates')
    outline = visual['outline']
    area = abs(sum(outline[i][0] * outline[(i + 1) % 72][1]
                   - outline[(i + 1) % 72][0] * outline[i][1] for i in range(72))) / 2
    require(area > .025, 'Degenerate outline area')
    require(len({tuple(p) for p in outline}) == 72, 'Outline point repetition')
    palette = visual['palette']
    require(len(palette) == 3 and all(isinstance(c, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', c) for c in palette),
            'Expected three RGB palette colors')
    face = visual['face']
    require(face['cx'] == .5 and face['cy'] == .43 and .8 <= face['scale'] <= 1.1
            and .85 <= face['eyeSpacing'] <= 1.15, 'Invalid face geometry')
    face_margin = assert_face_containment(outline, face)
    return {'faceEllipseEdgeDistanceMinimum': face_margin, 'outlineSha256': sha(canonical(outline)), 'routeSha256': sha(canonical(visual['route'])),
            'visualSha256': sha(canonical(visual)), 'polygonArea': area,
            'outlineBounds': [min(p[0] for p in outline), min(p[1] for p in outline),
                              max(p[0] for p in outline), max(p[1] for p in outline)]}


def validate_audio(data, clip):
    require(sha(data) == clip['audioSha256'], 'Audio SHA differs from manifest')
    with wave.open(io.BytesIO(data), 'rb') as wav:
        rate, channels, width, frames = wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()
        require(wav.getcomptype() == 'NONE' and channels == 1 and width == 2 and rate == 24000,
                'Expected original mono 24 kHz PCM16 WAV')
        samples = wav.readframes(frames)
    require(rate == clip['sampleRateHz'] and channels == clip['channels'] and width == clip['sampleWidthBytes'],
            'Audio format differs from manifest')
    duration_ms = round(frames / rate * 1000)
    require(abs(duration_ms - clip['durationMs']) <= 1 and frames > 0, 'Audio duration differs')
    values = struct.unpack('<' + 'h' * (len(samples) // 2), samples)
    rms = math.sqrt(sum(s * s for s in values) / len(values))
    require(rms > 0, 'Source audio is silent')
    return {'sha256': sha(data), 'bytes': len(data), 'durationMs': duration_ms, 'rmsPcm16': rms,
            'humanNaturalnessOrCuteness': 'NOT_VERIFIED'}


def resample_independent(points, count=72):
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    require(lengths[-1] > 1e-6, 'Artifact canonical route has zero length')
    result = []
    for i in range(count):
        target = lengths[-1] * i / (count - 1)
        j = max(1, min(len(points) - 1, bisect.bisect_left(lengths, target)))
        span = lengths[j] - lengths[j - 1]
        ratio = (target - lengths[j - 1]) / span if span else 0.0
        result.append([points[j - 1][k] * (1 - ratio) + points[j][k] * ratio for k in (0, 1)])
    return result


def validate_artifact(api, artifact, expected_request, out):
    require(artifact['schemaVersion'] == 1, 'Wrong artifact schema')
    request_id = expected_request or artifact['journeyId']
    require(artifact['journeyId'] == request_id and str(uuid.UUID(request_id)) == request_id, 'Journey UUID mismatch')
    require(re.fullmatch(r'route-[0-9a-f]{24}', artifact['characterId']), 'Invalid character identifier')
    require(HEX64.fullmatch(artifact['inputSha256']), 'Invalid input digest')
    input_canonical = artifact['inputCanonical']
    require(isinstance(input_canonical, str) and sha(input_canonical.encode()) == artifact['inputSha256'],
            'Canonical input SHA mismatch')
    input_value = json.loads(input_canonical)
    require(canonical(input_value).decode() == input_canonical and input_value['requestId'] == request_id,
            'Artifact canonical input serialization/UUID mismatch')
    require(artifact['destinationName'] == input_value['destination']['name'] and artifact['purpose'] == input_value['purpose'],
            'Artifact destination/purpose differs from canonical input')
    original_route = resample_independent(input_value['route']['points'])
    require(all(abs(a - b) <= 1.1e-8 for p, q in zip(original_route, artifact['visual']['route']) for a, b in zip(p, q)),
            'Visual trace is not the supplied route resampled by arc length')
    require(isinstance(artifact['displayName'], str) and artifact['displayName'].strip(), 'Missing display name')
    visual_proof = validate_visual(artifact['visual'])
    voice = artifact['voice']
    require(voice['speaker'] == 'Sohee' and isinstance(voice['description'], str) and voice['description'].strip(),
            'Voice description/speaker missing')
    require(isinstance(voice['direction'], str) and voice['direction'].strip(), 'Voice direction missing')
    manifest = artifact['voiceManifest']
    require(manifest['schemaVersion'] == 2 and manifest['providerId'] == PROVIDER, 'Wrong local voice provider')
    clips = manifest['clips']
    require(len(clips) == 3 and len({clip['clipId'] for clip in clips}) == 3, 'Expected exactly three unique clips')
    categories = set()
    proofs = []
    for clip in clips:
        category = clip['clipId'].removeprefix(artifact['characterId'] + '-')
        require(category in {'greeting', 'common', 'arrival'}, 'Unexpected clip category/identity')
        categories.add(category)
        require(clip['characterId'] == artifact['characterId'] and clip['profileId'] == voice['profileId']
                and clip['speakerId'] == voice['speaker'] and clip['locale'] == 'ko-KR', 'Visual/voice identity mismatch')
        source = clip['source']
        require(set(source) == {'kind', 'sourceModelRevision', 'bindingId', 'engineFingerprint', 'directionSha256', 'seed'}
                and source['kind'] == 'directed-sohee-v1' and source['bindingId'] == voice['bindingId']
                and source['directionSha256'] == sha(voice['direction'].encode())
                and source['sourceModelRevision'] == '41d3337e8b7f2843a75841595fc14e4b9a7a4b96'
                and HEX64.fullmatch(source['engineFingerprint']) and type(source['seed']) is int
                and 0 <= source['seed'] <= 0xffffffff, 'Voice sealed source mismatch')
        require(sha(clip['text'].encode()) == clip['textSha256'], 'Text digest mismatch')
        path = clip['audioPath']
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.wav', path), 'Unsafe WAV basename')
        status, data = api.request('GET', '/v1/journeys/' + request_id + '/audio/' + quote(path, safe=''))
        require(status == 200, 'Committed audio endpoint unavailable')
        proof = validate_audio(data, clip)
        (out / path).write_bytes(data)
        proofs.append({'clipId': clip['clipId'], 'profileId': clip['profileId'], 'bindingId': source['bindingId'], **proof})
    require(categories == {'greeting', 'common', 'arrival'}, 'Missing clip category')
    for bad_path in ('unknown.wav', '%2e%2e%2finput.json', '%2fetc%2fpasswd'):
        status, body = api.request('GET', '/v1/journeys/' + request_id + '/audio/' + bad_path)
        require(status != 200, 'Uncommitted/traversal audio path accepted')
    return {'requestId': request_id, 'characterId': artifact['characterId'], 'inputSha256': artifact['inputSha256'],
            'artifactSha256': sha(canonical(artifact)), 'voiceProfileId': voice['profileId'],
            'bindingId': voice['bindingId'], 'directionSha256': sha(voice['direction'].encode()),
            **visual_proof, 'clips': proofs}


def wait_ready(api, request_id, timeout, out):
    end, states, intermediate = time.monotonic() + timeout, [], None
    while time.monotonic() < end:
        status, value = api.json('GET', '/v1/journeys/' + request_id)
        require(status == 200 and value['requestId'] == request_id, 'Read job returned different request')
        state = value['state']
        require(state in {'GENERATING', 'READY', 'FAILED'}, 'Unknown generation state')
        if not states or states[-1] != state:
            states.append(state)
        if 'artifact' in value and value['artifact'] is not None:
            artifact = value['artifact']
            signature = (artifact['characterId'], artifact['inputSha256'], sha(canonical(artifact['visual'])),
                         sha(canonical(artifact['voice'])))
            require(intermediate in (None, signature), 'Identity/visual/voice direction changed during generation')
            intermediate = signature
        if state == 'FAILED':
            raise AssertionError('Actual worker failed job: ' + str(value.get('error')))
        if state == 'READY':
            require('artifact' in value and 'voiceManifest' in value['artifact'], 'READY lacks final voice manifest')
            (out / 'response.json').write_bytes(canonical(value) + b'\n')
            proof = validate_artifact(api, value['artifact'], request_id, out)
            return value, {'observedStates': states, **proof}
        time.sleep(.5)
    raise AssertionError('Timed out waiting for real generation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', default='http://127.0.0.1:8766')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--inspect', action='append', default=[], metavar='UUID')
    parser.add_argument('--submit', action='append', default=[], type=Path, metavar='INPUT_JSON')
    parser.add_argument('--skip-invalid', action='store_true')
    parser.add_argument('--timeout', type=float, default=900)
    args = parser.parse_args()
    origin = urlsplit(args.origin)
    if origin.scheme != 'http' or origin.hostname != '127.0.0.1' or origin.path not in ('', '/') or origin.query or origin.fragment or origin.username or origin.password:
        parser.error('Only unauthenticated loopback HTTP origin is permitted')
    if not 5 <= args.timeout <= 1800:
        parser.error('Timeout must be 5..1800 seconds')
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'startedAt': now(), 'status': 'FAIL', 'scope': 'Independent HTTP/schema, geometry and exact local audio identity checks',
              'postRequests': len(args.submit), 'newJobsObservedGenerating': 0, 'notVerified': ['Human visual quality, uniqueness perception, cuteness or collectibility',
              'Human Korean pronunciation or naturalness', 'Native Android rendering/playback/lifecycle', 'Worker crash recovery']}
    api = API(args.origin, out)
    try:
        status, health = api.json('GET', '/health')
        require(status == 200 and health.get('status') == 'ok' and health.get('version') == 'route-born-1', 'Bridge health/version mismatch')
        report['health'] = health
        checks = []
        if not args.skip_invalid:
            for label, value in invalid_inputs():
                raw = json.dumps(value, ensure_ascii=True).encode()
                status, response = api.json('POST', '/v1/journeys', raw=raw)
                require(400 <= status < 500 and not response.get('artifact'), 'Invalid input accepted: ' + label)
                if re.fullmatch(r'[0-9a-f-]{36}', value.get('requestId', '')):
                    get_status, get_response = api.json('GET', '/v1/journeys/' + value['requestId'])
                    require(get_status == 404, 'Invalid input allocated a persisted job: ' + label)
                checks.append({'case': label, 'httpStatus': status, 'response': response})
            for label, raw in [('malformed_json', b'{'), ('not_object', b'[]'), ('duplicate_json_key', b'{"requestId":"a","requestId":"b"}'),
                               ('body_too_large', b' ' * 65537),
                               ('nan_coordinate', json.dumps(request_input(points=[[0, 0], [float('nan'), .5]])).encode()),
                               ('infinite_coordinate', json.dumps(request_input(points=[[0, 0], [float('inf'), .5]])).encode())]:
                status, response = api.json('POST', '/v1/journeys', raw=raw)
                require(400 <= status < 500 and not response.get('artifact'), 'Malformed/nonfinite input accepted: ' + label)
                checks.append({'case': label, 'httpStatus': status, 'response': response})
            report['invalidInputs'] = checks
        jobs = []
        identifiers = list(args.inspect)
        for index, path in enumerate(args.submit):
            value = json.loads(path.read_text())
            status, response = api.json('POST', '/v1/journeys', data=value)
            require(status in {200, 202} and response.get('requestId') == value['requestId'], 'Submission returned different identity')
            report['newJobsObservedGenerating'] += int(response.get('state') == 'GENERATING')
            initial_state = response.get('state')
            directory = out / ('submitted-' + str(index))
            directory.mkdir()
            (directory / 'input.json').write_bytes(canonical(value) + b'\n')
            final, proof = wait_ready(api, value['requestId'], args.timeout, directory)
            normalized = json.loads(json.dumps(value))
            normalized['route']['points'] = [[float(x) + 0.0, float(y) + 0.0] for x, y in normalized['route']['points']]
            require(canonical(normalized).decode() == final['artifact']['inputCanonical'],
                    'Submitted input differs from committed artifact canonical input')
            status, repeated = api.json('POST', '/v1/journeys', data=value)
            require(status in {200, 202} and repeated['state'] == 'READY'
                    and canonical(repeated['artifact']) == canonical(final['artifact']), 'Exact retry changed immutable artifact')
            conflict = json.loads(json.dumps(value))
            conflict['purpose'] += ' / conflicting retry'
            conflict_status, conflict_response = api.json('POST', '/v1/journeys', data=conflict)
            require(conflict_status == 409, 'Conflicting request ID did not reject with 409')
            read_status, unchanged = api.json('GET', '/v1/journeys/' + value['requestId'])
            require(read_status == 200 and canonical(unchanged['artifact']) == canonical(final['artifact']), 'Conflict altered committed artifact')
            jobs.append({'directory': directory.name, 'initialPostState': initial_state, 'retryImmutable': True, 'conflictHttpStatus': conflict_status, **proof})
        for index, request_id in enumerate(identifiers):
            require(str(uuid.UUID(request_id)) == request_id, 'Inspect expects canonical UUID')
            directory = out / ('inspected-' + str(index))
            directory.mkdir()
            final, proof = wait_ready(api, request_id, args.timeout, directory)
            jobs.append({'directory': directory.name, **proof})
        report['jobs'] = jobs
        if len(jobs) > 1:
            require(len({p['characterId'] for p in jobs}) == len(jobs), 'Distinct requests reused character identity')
            require(len({p['outlineSha256'] for p in jobs}) == len(jobs), 'Distinct sampled requests reused exact outline')
        report['status'] = 'PASS_INDEPENDENT_ROUTE_BIRTH_HTTP_AND_ARTIFACTS'
    except (AssertionError, OSError, ValueError, KeyError, TypeError, URLError) as error:
        report['error'] = str(error)
    finally:
        report['finishedAt'] = now()
        report['httpCallCount'] = len(api.calls)
        (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'error': report.get('error'), 'report': str(out / 'verification.json')}, ensure_ascii=False), flush=True)
    return 0 if report['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
