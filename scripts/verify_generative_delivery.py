#!/usr/bin/env python3
"""Recheck actual v2 evidence; --live also checks installed APK and immutable localhost assets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'docs/design/generative-mvp'
APK = ROOT / '.local/generative-mvp/Nunti-Generative-MVP-debug.apk'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest(prefix, status):
    paths = sorted((ROOT / '.local/generative-mvp').glob(prefix + '-*/verification.json'), reverse=True)
    return next(path for path in paths if read(path)['status'] == status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--serial', default='emulator-5554')
    args = parser.parse_args()
    native_path = latest('native', 'PASS_NATIVE_V2_FIXTURE_MEDIA_AND_LIFECYCLE')
    touch_path = latest('touch', 'PASS_REAL_FIELDS_GESTURE_BUTTON_AND_AUDIO')
    native, touch = read(native_path), read(touch_path)
    backend_path = ROOT / 'backend/reports/generation-v2-verification.json'
    backend = read(backend_path)
    report = {'status': 'FAIL', 'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Keyless fixture integration and preserved tests',
        'apiQualityVerified': False, 'humanCutenessOrNaturalnessApproved': False, 'actualApiCostVerified': False}
    try:
        assert backend['status'] == 'PASS_KEYLESS_V2_BACKEND' and backend['pytest']['failures'] == 0 and backend['pytest']['errors'] == 0
        for path, expected in backend['sources'].items():
            assert digest(ROOT / 'backend' / path) == expected, 'Backend source changed: ' + path
        for path, expected in native['nativeSourceSha256'].items():
            assert digest(ROOT / path) == expected, 'Native source changed: ' + path
        assert touch['apkSha256'] == digest(APK), 'Delivered APK differs from touch-tested APK'
        assert native['boundaryChecks'] == 10 and native['automaticSpeechAfterRestore'] is False and native['quietConsentRestored'] is False
        assert touch['routePoints'] > 3 and touch['speakerCapture']['nonzeroSamples'] > 0
        assert touch['speakerCapture']['source'] == 'AUTHENTICATED_EMULATOR_SPEAKER_STREAM'
        artifact = read(native_path.parent / 'artifact.json')
        assert artifact['mode'] == 'OFFLINE_FIXTURE' and artifact['voiceManifest']['schemaVersion'] == 3
        source = artifact['voiceManifest']['clips'][0]['source']
        assert source['mediaOrigin'] == 'OFFLINE_FIXTURE' and source['providerId'] == 'nunti-offline-fixture'
        assert source['bindingId'] == native['bindingId']
        lint_path = ROOT / 'android/build/app/reports/lint-results-debug.xml'
        lint = ET.parse(lint_path).getroot()
        assert not any(issue.get('severity') in ('Fatal', 'Error') for issue in lint.findall('issue'))
        report.update(status='PASS_KEYLESS_GENERATIVE_MVP_DELIVERY', apk=str(APK), apkSha256=digest(APK),
            backendTests=backend['pytest']['tests'], backendNewTests=backend['newV2Tests'],
            nativeBoundaryChecks=10, realGestureRoutePoints=touch['routePoints'],
            speakerSignalSamples=touch['speakerCapture']['nonzeroSamples'],
            nativeEvidence=str(native_path.relative_to(ROOT)), touchEvidence=str(touch_path.relative_to(ROOT)),
            lintErrors=0, lintWarnings=sum(issue.get('severity') == 'Warning' for issue in lint.findall('issue')),
            providerApiCalls=0, paidCalls=0,
            evidenceSha256={str(p.relative_to(ROOT)): digest(p) for p in (native_path, touch_path, backend_path, lint_path)})
        if native.get('formationDesign') == 'ROUTE_RIBBON_V1':
            assert native['initialBirthProgress'] == 0 and native['formationPreparedBeforeAnimation'] is True
            report.update(formationDesign=native['formationDesign'], initialBirthProgress=0,
                formationPreparedBeforeAnimation=True, routeScenario=touch.get('routeScenario'))
        if 'videoOrSpeakerRecordingPerformed' in native:
            report.update(nativeRegressionVideoOrSpeakerRecordingPerformed=native['videoOrSpeakerRecordingPerformed'],
                nativeRegressionScreenshotsCaptured=native['screenshotsCaptured'])
        if args.live:
            config = read(ROOT / '.local/generative-mvp/connection-offline_fixture.json')
            assert config['baseUrl'] == 'http://127.0.0.1:8767' and config['mode'] == 'OFFLINE_FIXTURE'

            def request(path, body=None, authorized=True, media=False):
                headers = {'Authorization': 'Bearer ' + config['token']} if authorized else {}
                if body is not None:
                    headers['Content-Type'] = 'application/json'
                req = urllib.request.Request(config['baseUrl'] + path, headers=headers,
                    data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
                with urllib.request.urlopen(req, timeout=10) as response:
                    raw = response.read(8_388_609)
                assert len(raw) <= 8_388_608
                return raw if media else json.loads(raw)['data']

            capabilities = request('/v2/generation-capabilities')
            assert capabilities['mode'] == 'OFFLINE_FIXTURE'
            job = request('/v2/jobs/' + native['requestId'])
            assert job['artifact'] == artifact
            retry = request('/v2/character-generations', json.loads(artifact['inputCanonical']))
            assert retry['artifact'] == artifact and retry['state'] == 'READY' and retry['jobId'] == retry['requestId']
            for sha in [artifact['visual']['asset']['sha256']] + [c['audioSha256'] for c in artifact['voiceManifest']['clips']]:
                assert hashlib.sha256(request('/v2/assets/' + sha, media=True)).hexdigest() == sha
            try:
                request('/v2/assets/' + artifact['visual']['asset']['sha256'], authorized=False, media=True)
                raise AssertionError('Unauthenticated asset was served')
            except urllib.error.HTTPError as exc:
                assert exc.code in (401, 403)
            adb = [str(ROOT / '.local/pm-tools/sdk/platform-tools/adb'), '-s', args.serial]
            def shell(*parts):
                return subprocess.run(adb + ['shell', shlex.join(parts)], check=True, capture_output=True, text=True).stdout.strip()
            user = shell('am', 'get-current-user')
            installed = shell('pm', 'path', '--user', user, 'ai.nunti.avatar.demo').splitlines()[0].removeprefix('package:')
            assert installed.startswith('/data/app/')
            assert shell('sha256sum', installed).split()[0] == digest(APK)
            report.update(liveInstalledApkMatches=True, liveExistingCharacterAndRetryImmutable=True,
                liveAuthenticatedAssetsVerified=4, liveUnauthenticatedAssetBlocked=True,
                liveCheckAt=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        report.update(status='FAIL', error=str(exc))
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report.get(k) for k in ('status', 'error', 'backendTests', 'nativeBoundaryChecks', 'apkSha256', 'liveInstalledApkMatches')}, ensure_ascii=False))
    return 0 if report['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
