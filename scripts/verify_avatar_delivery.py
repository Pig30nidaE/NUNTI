#!/usr/bin/env python3
"""Collect the actual generator test artifacts and inspect both APKs. No UI or recording."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local/avatar-generator'
OUTPUT = ROOT / 'docs/design/avatar-generator/verification'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tests = ET.parse(ROOT / 'docs/design/avatar-generator/backend-tests.xml').getroot()
    suites = list(tests.iter('testsuite'))
    assert suites and all(int(s.get('errors', 0)) == int(s.get('failures', 0)) == 0 for s in suites)
    reports = {}
    for source, name, status in (
        ('browser-verification/verification.json', 'browser', 'PASS_AVATAR_GENERATOR_UI'),
        ('native-verification/verification.json', 'android', 'PASS_AVATAR_GENERATOR_UI'),
        ('input-edge-verification/verification.json', 'input-edges', 'PASS_AVATAR_INPUT_EDGES'),
    ):
        value = json.loads((WORK / source).read_text())
        assert value['status'] == status and value['providerApiCalls'] == 0
        assert not value.get('videoRecorded', False) and not value.get('speakerRecorded', False)
        shutil.copy2(WORK / source, OUTPUT / (name + '.json'))
        reports[name] = {'status': value['status'], 'checks': len(value['checks'])}
    lint = (ROOT / 'android/build/app/reports/lint-results-debug.txt').read_text()
    errors, warnings = map(int, re.search(r'(\d+) errors, (\d+) warnings', lint).groups())
    assert errors == 0
    assert 'BUILD SUCCESSFUL' in (WORK / 'build.log').read_text()
    apks = []
    for name in ('Nunti-Avatar-Generator-debug.apk', 'Nunti-Avatar-Generator-release-unsigned.apk'):
        file = WORK / name
        with zipfile.ZipFile(file) as archive:
            assert any(b'AvatarStudioActivity' in archive.read(n) for n in archive.namelist() if n.endswith('.dex'))
        apks.append({'file': str(file.relative_to(ROOT)), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                     'avatarStudioHostPresent': True, 'signedForSubmission': False})
    for source, name in (('browser-verification/03-screenshot-avatar.png', 'preview.png'),
                         ('park-restored.png', 'android-parked.png'),
                         ('drive-blocked.png', 'android-drive-blocked.png')):
        shutil.copy2(WORK / source, OUTPUT / name)
    result = {'status': 'PASS_AVATAR_GENERATOR_DELIVERY',
              'scope': 'Collected actual test reports, zero lint errors, successful build and inspected APK classes. Does not exercise the UI again.',
              'backendCasesIncludingSubtests': sum(int(s.get('tests', 0)) for s in suites),
              'surfaces': reports, 'androidLint': {'errors': errors, 'warnings': warnings},
              'providerApiCalls': 0, 'newVoiceGenerated': False,
              'videoRecorded': False, 'speakerRecorded': False, 'apks': apks}
    (OUTPUT / 'delivery.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('apks', 'scope')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
