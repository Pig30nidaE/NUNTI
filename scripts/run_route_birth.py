#!/usr/bin/env python3
"""Open native route-born MVP with offline PC synthesis and no APK rebuild per trip."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local/route-birth'
SDK = ROOT / '.local/pm-tools/sdk'
ADB = SDK / 'platform-tools/adb'
PYTHON = ROOT / '.local/journey-voice-v3/venv/bin/python'
APK = WORK / 'Nunti-Route-Birth-debug.apk'
PACKAGE = 'ai.nunti.avatar.demo'
ACTIVITY = PACKAGE + '/ai.nunti.app.routebirth.RouteBirthActivity'
AVD = 'Nunti_Restore_2_1'


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def health():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=2) as response:
            value = json.loads(response.read(8192))
        if value.get('status') != 'ok' or value.get('version') != 'route-born-1':
            raise RuntimeError('8766 포트를 다른 프로그램이 사용하고 있습니다.')
        return True
    except urllib.error.URLError:
        return False


def server():
    if health():
        return
    with (WORK / 'launcher-worker.log').open('ab') as log:
        process = subprocess.Popen([str(PYTHON), str(ROOT / 'prototypes/route_birth/worker.py'), 'serve',
            '--workspace', str(WORK), '--port', '8766'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    (WORK / 'launcher-worker.pid').write_text(str(process.pid) + '\n')
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError('PC 생성기를 시작하지 못했습니다. .local/route-birth/launcher-worker.log를 확인하세요.')
        if health():
            return
        time.sleep(.5)
    raise RuntimeError('PC 생성기의 준비 시간이 초과됐습니다.')


def emulator():
    result = run([ADB, 'devices'], text=True, capture_output=True).stdout
    devices = [line.split()[0] for line in result.splitlines()[1:] if len(line.split()) >= 2]
    for serial in devices:
        if serial.startswith('emulator-'):
            name = run([ADB, '-s', serial, 'emu', 'avd', 'name'], text=True, capture_output=True).stdout
            if name.splitlines()[:1] == [AVD]:
                return serial
    port = next(p for p in range(5554, 5585, 2) if f'emulator-{p}' not in devices)
    env = dict(os.environ, ANDROID_HOME=str(SDK), ANDROID_USER_HOME=str(ROOT / '.local/pm-tools/android-user'), ANDROID_AVD_HOME=str(ROOT / '.local/pm-tools/avd'))
    with (WORK / 'launcher-emulator.log').open('ab') as log:
        subprocess.Popen([str(SDK / 'emulator/emulator'), '-avd', AVD, '-port', str(port), '-no-snapshot-load',
            '-no-snapshot-save', '-no-boot-anim', '-memory', '4096'], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return f'emulator-{port}'


def build():
    env = dict(os.environ, JAVA_HOME=str(ROOT / '.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home'),
        ANDROID_HOME=str(SDK), ANDROID_USER_HOME=str(ROOT / '.worktrees/tts/.local/android-user'), GRADLE_USER_HOME=str(ROOT / '.worktrees/tts/.local/gradle-user'))
    with (WORK / 'launcher-build.log').open('w') as log:
        run([ROOT / 'android/gradlew', '--offline', '--no-daemon', ':app:assembleDebug'], cwd=ROOT / 'android', env=env, stdout=log, stderr=subprocess.STDOUT)
    import shutil
    shutil.copy2(ROOT / 'android/build/app/outputs/apk/debug/app-debug.apk', APK)


def check():
    if not APK.exists():
        raise RuntimeError('준비된 APK가 없습니다. --build로 기존 로컬 도구로 빌드하세요.')
    with zipfile.ZipFile(APK) as archive:
        if not any(b'RouteBirthActivity' in archive.read(name) for name in archive.namelist() if name.endswith('.dex')):
            raise RuntimeError('새 여정 생성 화면이 없는 APK입니다.')
    return {'apk': str(APK), 'sha256': hashlib.sha256(APK.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--check', action='store_true', help='파일만 확인하고 서버·앱을 실행하지 않습니다.')
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.build:
        build()
    proof = check()
    if args.check:
        print(json.dumps(proof, ensure_ascii=False, indent=2)); return
    server()
    serial = emulator()
    adb = [ADB, '-s', serial]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = subprocess.run([str(x) for x in adb + ['shell', 'getprop', 'sys.boot_completed']], text=True, capture_output=True)
        if result.returncode == 0 and result.stdout.strip() == '1':
            break
        time.sleep(1)
    else:
        raise RuntimeError('에뮬레이터의 부팅이 완료되지 않았습니다.')
    user = run(adb + ['shell', 'am', 'get-current-user'], capture_output=True, text=True).stdout.strip()
    if not user.isdigit():
        raise RuntimeError('Android 사용자를 확인할 수 없습니다.')
    run(adb + ['reverse', 'tcp:8766', 'tcp:8766'])
    run(adb + ['install', '-r', '--user', user, APK])
    run(adb + ['shell', 'am', 'force-stop', '--user', user, PACKAGE])
    run(adb + ['shell', 'am', 'start', '-W', '--user', user, '-n', ACTIVITY])
    proof.update({'serial': serial, 'androidUser': int(user), 'workerHealth': True, 'perTripApkRebuild': False})
    (WORK / 'launcher-delivery.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    print('목적지와 경로를 입력하는 Nunti 화면을 열었습니다. 새 여행마다 재설치하지 않습니다.')
    print('PC 생성기와 에뮬레이터는 계속 실행됩니다. 외부 API·계정·다운로드는 사용하지 않습니다.')

if __name__ == '__main__':
    main()
