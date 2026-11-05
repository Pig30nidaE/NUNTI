#!/usr/bin/env python3
"""Compile and execute the production manifest parser using only pinned cached JVM artifacts.

Unlike the core fixture projections, this runs LocalVoiceManifest with real org.json.
This is a host test, not an Android runtime, listening test, or provider API call.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools-dir', type=Path)
    parser.add_argument('--json-jar', type=Path)
    parser.add_argument('--voice-manifest', type=Path)
    parser.add_argument('--audio-directory', type=Path)
    args = parser.parse_args()
    voice = Path(__file__).resolve().parents[1]
    repository = voice.parents[2]
    tts = voice.parent / 'tts'
    cache = args.tools_dir or repository / '.local/tts-tools/artifacts'
    lock = json.loads((tts / 'scripts/toolchain-lock.json').read_text())
    artifacts = [item for item in lock if item['group'] == 'compiler']
    for artifact in artifacts:
        path = cache / artifact['name']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
            raise SystemExit(f'Missing or changed pinned compiler artifact: {path}. No download attempted.')
    json_jar = args.json_jar or repository / '.worktrees/tts/.local/gradle-user/caches/modules-2/files-2.1/org.json/json/20250517/d67181bbd819ccceb929b580a4e2fcb0c8b17cd8/json-20250517.jar'
    if not json_jar.is_file() or hashlib.sha256(json_jar.read_bytes()).hexdigest() != '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796':
        raise SystemExit(f'Missing or changed pinned org.json 20250517: {json_jar}. No download attempted.')
    java = os.environ.get('NUNTI_JAVA', 'java')
    compiler_cp = os.pathsep.join(str(cache / item['name']) for item in artifacts)
    stdlib = cache / 'kotlin-stdlib-2.2.20.jar'
    classpath = os.pathsep.join(map(str, [stdlib, json_jar]))
    out = voice / 'build/manifest-verification'
    out.mkdir(parents=True, exist_ok=True)
    jar = out / 'tests.jar'
    sources = sorted((tts / 'src/main/kotlin').rglob('*.kt')) + [voice / 'src/main/kotlin/ai/nunti/voice/LocalVoiceManifest.kt'] + sorted((voice / 'src/test/kotlin').rglob('*.kt'))
    subprocess.run([java, '-cp', compiler_cp, 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-no-stdlib', '-no-reflect',
                    '-jvm-target', '17', '-classpath', classpath, '-d', str(jar)] + list(map(str, sources)), check=True)
    command = [java, '-cp', os.pathsep.join([str(jar), classpath]), 'ai.nunti.voice.LocalVoiceManifestTestKt', str(repository)]
    if args.voice_manifest:
        command.append(str(args.voice_manifest.resolve()))
        if args.audio_directory:
            command.append(str(args.audio_directory.resolve()))
    elif args.audio_directory:
        raise SystemExit('--audio-directory requires --voice-manifest')
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / 'tests.txt').write_text(result.stdout)
    print(result.stdout, end='')
    result.check_returncode()
    print(f'Evidence: {out}; cached JVM org.json implementation; Android runtime NOT tested.')


if __name__ == '__main__':
    main()
