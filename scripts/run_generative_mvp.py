#!/usr/bin/env python3
"""Run the v2 native MVP. The default uses explicitly labelled existing sample media."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import signal
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local/generative-mvp'
SDK = ROOT / '.local/pm-tools/sdk'
ADB = SDK / 'platform-tools/adb'
APK = WORK / 'Nunti-Generative-MVP-debug.apk'
PACKAGE = 'ai.nunti.avatar.demo'
ACTIVITY = PACKAGE + '/ai.nunti.app.generated.GeneratedCompanionActivity'
BASE = 'http://127.0.0.1:8767'
PYTHONS = [ROOT / '.worktrees/server/backend/.venv/bin/python', ROOT / 'backend/.venv/bin/python']


def run(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.pending')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write('\n')
    temporary.replace(path)
    path.chmod(0o600)


def configuration(mode):
    path = WORK / f'connection-{mode.lower()}.json'
    if path.exists():
        result = json.loads(path.read_text())
        if result.get('baseUrl') != BASE or result.get('mode') != mode or len(result.get('token', '')) < 32:
            raise RuntimeError('로컬 연결 설정이 올바르지 않습니다.')
    else:
        result = {'baseUrl': BASE, 'token': secrets.token_urlsafe(32), 'mode': mode}
        private_json(path, result)
    return path, result


def python_runtime():
    for path in PYTHONS:
        if path.exists():
            result = subprocess.run([str(path), '-c', 'import fastapi, uvicorn, pydantic'], capture_output=True)
            if result.returncode == 0:
                return path
    raise RuntimeError('backend Python 환경이 없습니다. backend의 uv.lock 환경을 복원해 주세요.')


def request(config, path):
    req = urllib.request.Request(BASE + path, headers={'Authorization': 'Bearer ' + config['token']})
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.loads(response.read(262144))['data']


def environment(config):
    env = dict(os.environ)
    if config['mode'] == 'OFFLINE_FIXTURE':
        for name in ('OPENAI_API_KEY', 'ELEVENLABS_API_KEY', 'GOOGLE_API_KEY', 'RECRAFT_API_KEY', 'RECRAFT_API_TOKEN'):
            env.pop(name, None)
    env.update(PYTHONPATH=str(ROOT / 'backend'), PYTHONUNBUFFERED='1',
        NUNTI_AUTH_TOKENS=json.dumps({config['token']: 'generative-mvp-local'}),
        NUNTI_REQUIRE_HTTPS='false', NUNTI_SYNC_ENABLED='false', NUNTI_ENABLE_MOCKS='false',
        NUNTI_DB_PATH=str(WORK / 'sync.sqlite3'),
        NUNTI_CHARACTER_DB_PATH=str(WORK / f"characters-{config['mode'].lower()}.sqlite3"),
        NUNTI_CHARACTER_MEDIA_PATH=str(WORK / f"media-{config['mode'].lower()}"),
        NUNTI_GENERATION_MODE=config['mode'],
        NUNTI_FIXTURE_PNG=str(ROOT / 'docs/design/journey-characters/concepts/recipe-coastal-001.png'),
        NUNTI_FIXTURE_MANIFEST=str(ROOT / 'android/app/src/debug/assets/journey-dynamic/manifest.json'))
    return env


def start_server(config):
    try:
        existing = request(config, '/v2/generation-capabilities')
    except urllib.error.HTTPError as exc:
        raise RuntimeError('8767 포트의 인증 설정이 다릅니다. 기존 로컬 실행을 확인해 주세요.') from exc
    except (urllib.error.URLError, TimeoutError):
        existing = None
    if existing is not None:
        if existing['mode'] != config['mode']:
            raise RuntimeError('실행 중인 서버의 모드가 다릅니다. 기존 서버를 먼저 종료해 주세요.')
        pid_file = WORK / 'worker.pid'
        pid = int(pid_file.read_text().strip()) if pid_file.is_file() else None
        command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout if pid else ''
        if 'nunti.characters.worker' not in command:
            with (WORK / 'worker.log').open('ab') as log:
                worker = subprocess.Popen([str(python_runtime()), '-m', 'nunti.characters.worker'],
                    cwd=ROOT / 'backend', env=environment(config), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            pid_file.write_text(str(worker.pid) + '\n')
            time.sleep(.2)
            if worker.poll() is not None:
                raise RuntimeError('생성 작업자가 종료됐습니다. worker.log를 확인하세요.')
        return existing
    runtime = python_runtime()
    env = environment(config)
    processes = []
    for name, arguments in (
        ('server', ['-m', 'uvicorn', 'nunti.api:create_app', '--factory', '--host', '127.0.0.1', '--port', '8767']),
        ('worker', ['-m', 'nunti.characters.worker']),
    ):
        with (WORK / f'{name}.log').open('ab') as log:
            process = subprocess.Popen([str(runtime), *arguments], cwd=ROOT / 'backend', env=env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        (WORK / f'{name}.pid').write_text(str(process.pid) + '\n')
        processes.append(process)
    for _ in range(30):
        if any(process.poll() is not None for process in processes):
            raise RuntimeError('서버 또는 작업자가 종료됐습니다. .local/generative-mvp의 로그를 확인하세요.')
        try:
            return request(config, '/v2/generation-capabilities')
        except (urllib.error.URLError, TimeoutError):
            time.sleep(.5)
    raise RuntimeError('생성 서버의 준비 시간이 초과됐습니다.')


def stop_owned_server():
    for name, expected in (('worker', 'nunti.characters.worker'), ('server', 'uvicorn nunti.api:create_app')):
        path = WORK / f'{name}.pid'
        if not path.is_file():
            continue
        pid = int(path.read_text().strip())
        command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout
        if not command.strip():
            continue
        if expected not in command:
            raise RuntimeError('PID가 다른 프로세스로 바뀌었습니다. 자동 종료하지 않습니다.')
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if subprocess.run(['ps', '-p', str(pid)], capture_output=True).returncode != 0:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('작업자가 종료 중입니다. 잠시 후 다시 실행해 주세요.')


def build():
    env = dict(os.environ,
        JAVA_HOME=str(ROOT / '.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home'),
        ANDROID_HOME=str(SDK), ANDROID_USER_HOME=str(ROOT / '.worktrees/tts/.local/android-user'),
        GRADLE_USER_HOME=str(ROOT / '.worktrees/tts/.local/gradle-user'))
    with (WORK / 'build.log').open('w') as log:
        run([ROOT / 'android/gradlew', '--offline', '--no-daemon', ':app:assembleDebug'],
            cwd=ROOT / 'android', env=env, stdout=log, stderr=subprocess.STDOUT)
    shutil.copy2(ROOT / 'android/build/app/outputs/apk/debug/app-debug.apk', APK)


def check_apk():
    if not APK.is_file():
        raise RuntimeError('APK가 없습니다. --build로 빌드해 주세요.')
    with zipfile.ZipFile(APK) as archive:
        if not any(b'GeneratedCompanionActivity' in archive.read(name) for name in archive.namelist() if name.endswith('.dex')):
            raise RuntimeError('v2 생성 화면이 없는 APK입니다.')
    return {'apk': str(APK), 'sha256': hashlib.sha256(APK.read_bytes()).hexdigest()}


def emulator():
    # Reuse the restored Pleos AVD and its known device configuration.
    import run_route_birth
    return run_route_birth.emulator()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--check', action='store_true', help='APK와 환경만 확인합니다. 서버·에뮬레이터를 실행하지 않습니다.')
    parser.add_argument('--server-only', action='store_true')
    parser.add_argument('--restart-server', action='store_true', help='이 도구가 시작한 v2 서버·작업자만 다시 시작합니다.')
    parser.add_argument('--mode', choices=['offline-fixture', 'api'], default='offline-fixture')
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    mode = args.mode.upper().replace('-', '_')
    config_path, config = configuration(mode)
    if args.build:
        build()
    if args.check:
        proof = check_apk()
        proof.update(mode=mode, runtime=str(python_runtime()), connectionFile=str(config_path), credentialsDisplayed=False)
        print(json.dumps(proof, ensure_ascii=False, indent=2))
        return
    if args.restart_server:
        stop_owned_server()
    capabilities = start_server(config)
    if args.server_only:
        print(json.dumps({'baseUrl': BASE, 'mode': capabilities['mode'], 'connectionFile': str(config_path)}, ensure_ascii=False))
        return
    proof = check_apk()
    serial = emulator()
    adb = [ADB, '-s', serial]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = subprocess.run([str(arg) for arg in adb + ['shell', 'getprop', 'sys.boot_completed']], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip() == '1':
            break
        time.sleep(1)
    else:
        raise RuntimeError('에뮬레이터 부팅이 완료되지 않았습니다.')
    user = run(adb + ['shell', 'am', 'get-current-user'], capture_output=True, text=True).stdout.strip()
    if not user.isdigit():
        raise RuntimeError('Android 사용자를 확인할 수 없습니다.')
    run(adb + ['reverse', 'tcp:8767', 'tcp:8767'], capture_output=True)
    run(adb + ['install', '-r', '--user', user, APK], capture_output=True)
    provision = 'run-as ' + PACKAGE + ' --user ' + user + ' sh -c ' + shlex.quote('umask 077; mkdir -p files; cat > files/generative-connection.json')
    run(adb + ['shell', provision],
        input=json.dumps(config).encode(), capture_output=True)
    run(adb + ['shell', 'am', 'force-stop', '--user', user, PACKAGE], capture_output=True)
    run(adb + ['shell', 'am', 'start', '-W', '--user', user, '-n', ACTIVITY], capture_output=True)
    proof.update(mode=mode, serial=serial, androidUser=int(user), baseUrl=BASE,
        fixtureFollowupText=capabilities.get('fixtureFollowupText'), providerKeysInApk=False,
        actualGenerationQualityVerified=False)
    private_json(WORK / 'delivery.json', proof)
    print('Nunti 생성 MVP를 열었습니다. 목적지와 경로를 입력해 시험하세요.')
    print('샘플 미디어 모드입니다. 새 이미지·음색 생성과 API 비용은 아직 검증하지 않았습니다.' if mode == 'OFFLINE_FIXTURE'
          else 'API 모드입니다. 키·모델 접근·가격·슬롯 검증을 통과해야 생성할 수 있습니다.')
    print('실행 안내: docs/design/generative-mvp/TESTING.ko.md')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print('실행 실패: ' + str(exc), file=sys.stderr)
        raise SystemExit(1) from None
