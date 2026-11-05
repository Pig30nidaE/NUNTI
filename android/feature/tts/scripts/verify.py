#!/usr/bin/env python3
"""Reproducible JVM tests plus optional compilation against real Android/Pleos binaries.
No fake SDK stubs, Gradle installation, root app modifications, or credentials required.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bootstrap', action='store_true', help='Download missing pinned official artifacts')
    parser.add_argument('--android', action='store_true', help='Also compile the Android/Pleos adapter (not a runtime test)')
    parser.add_argument('--tools-dir', type=Path, default=Path(tempfile.gettempdir()) / 'nunti-tts-tools')
    parser.add_argument('--voice-manifest', type=Path, help='Validate a schema v1/v2/v3 WAV catalog instead of the six legacy Debug assets')
    args = parser.parse_args()
    module = Path(__file__).resolve().parents[1]
    voice = module.parent / 'voice'
    cache = args.tools_dir.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    lock = json.loads(Path(__file__).with_name('toolchain-lock.json').read_text())
    required = [x for x in lock if x['group'] == 'compiler' or args.android]
    for item in required:
        path = cache / item['name']
        if not path.exists():
            if not args.bootstrap:
                raise SystemExit(f'Missing {path}; run again with --bootstrap to fetch official artifacts.')
            temporary = path.with_suffix(path.suffix + '.partial')
            with urllib.request.urlopen(item['url'], timeout=120) as response, temporary.open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != item['sha256']:
                temporary.unlink()
                raise SystemExit(f'Checksum mismatch: {item["name"]}')
            temporary.replace(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise SystemExit(f'Checksum mismatch: {path}')
    out = module / 'build' / 'verification'
    out.mkdir(parents=True, exist_ok=True)
    java = os.environ.get('NUNTI_JAVA', 'java')
    compiler_cp = os.pathsep.join(str(cache / x['name']) for x in required if x['group'] == 'compiler')
    stdlib = cache / 'kotlin-stdlib-2.2.20.jar'
    compiler = [java, '-cp', compiler_cp, 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler',
                '-no-stdlib', '-no-reflect', '-jvm-target', '17']
    main_sources = sorted((module / 'src/main/kotlin').rglob('*.kt'))
    test_sources = sorted((module / 'src/test/kotlin').rglob('*.kt'))
    test_jar = out / 'tests.jar'
    subprocess.run(compiler + ['-classpath', str(stdlib), '-d', str(test_jar)] +
                   [str(x) for x in main_sources + test_sources], check=True)
    runtime = os.pathsep.join([str(test_jar), str(stdlib)])
    for classname, logfile in [('SpeechSystemTestKt', 'tests.txt'), ('SpeechDemoKt', 'demo.txt')]:
        result = subprocess.run([java, '-cp', runtime, f'ai.nunti.tts.{classname}'], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out / logfile).write_text(result.stdout)
        print(result.stdout, end='')
        result.check_returncode()
    # JSON is decoded by the standard parser, not regex or an invented in-app serializer.
    fixture_properties = out / 'contracts.properties'
    projected = []
    for fixture in sorted((module / 'src/test/fixtures').glob('*.json')):
        for key, value in json.loads(fixture.read_text()).items():
            if isinstance(value, list):
                value = ','.join(map(str, value))
            value = '' if value is None else str(value)
            encoded = base64.b64encode(value.encode()).decode('ascii')
            projected.append(f'{fixture.stem}.{key}={encoded}')
    fixture_properties.write_text('\n'.join(projected) + '\n')
    result = subprocess.run([java, '-cp', runtime, 'ai.nunti.tts.IntegrationFixtureTestKt', str(fixture_properties)],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / 'integration.txt').write_text(result.stdout)
    print(result.stdout, end='')
    result.check_returncode()
    # Exercise real PCM files through the Kotlin binding, hash, and RIFF validation path.
    sample_manifest = args.voice_manifest.resolve() if args.voice_manifest else module.parents[1] / 'app/src/debug/assets/journey-voice/manifest.json'
    sample_dir = sample_manifest.parent
    samples = json.loads(sample_manifest.read_text(encoding='utf-8'))
    if samples['schemaVersion'] not in (1, 2, 3):
        raise SystemExit('Unsupported sample schema version')
    sample_values = {'providerId': samples['providerId'], 'schemaVersion': samples['schemaVersion'], 'count': len(samples['clips'])}
    for i, clip in enumerate(samples['clips']):
        values = {key: clip[key] for key in ('clipId', 'characterId', 'profileId', 'speakerId', 'locale', 'text',
                  'textSha256', 'audioPath', 'audioSha256', 'sampleRateHz', 'channels', 'durationMs')}
        if samples['schemaVersion'] == 1:
            values.update(sourceKind='legacy-catalog-v1', sourceModelRevision=clip['sourceModelRevision'],
                          bindingId=clip['bindingId'], speed=clip['binding']['preset']['speed'],
                          steps=clip['binding']['preset']['steps'], catalogSha256=clip['binding']['catalogSha256'])
        elif samples['schemaVersion'] == 2:
            source = clip['source']
            if source['kind'] != 'directed-sohee-v1':
                raise SystemExit('Unknown directed voice asset kind')
            values.update(sourceKind=source['kind'], sourceModelRevision=source['sourceModelRevision'],
                          bindingId=source['bindingId'], engineFingerprint=source['engineFingerprint'],
                          directionSha256=source['directionSha256'], seed=source['seed'])
        else:
            source = clip['source']
            if source['kind'] != 'designed-voice-v1':
                raise SystemExit('Unknown designed voice asset kind')
            values.update(sourceKind=source['kind'], sourceProviderId=source['providerId'],
                          designModel=source['designModel'], synthesisModel=source['synthesisModel'], voiceId=source['voiceId'],
                          bindingId=source['bindingId'], specSha256=source['specSha256'], settingsSha256=source['settingsSha256'],
                          mediaOrigin=source['mediaOrigin'], rawAudioSha256=clip.get('rawAudioSha256', ''))
        sample_values.update({f'clip.{i}.{key}': value for key, value in values.items()})
    sample_properties = out / 'local-voice.properties'
    sample_properties.write_text('\n'.join(f'{key}={base64.b64encode(str(value).encode()).decode()}'
                                          for key, value in sample_values.items()) + '\n')
    result = subprocess.run([java, '-cp', runtime, 'ai.nunti.tts.LocalVoiceSampleTestKt', str(sample_properties), str(sample_dir)],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / 'local-voice-samples.txt').write_text(result.stdout)
    print(result.stdout, end='')
    result.check_returncode()
    if args.android:
        # Extract named members only; never unpack arbitrary archive paths.
        with zipfile.ZipFile(cache / 'TextToSpeech-3.3.1.aar') as archive:
            (cache / 'pleos-tts.jar').write_bytes(archive.read('classes.jar'))
        with zipfile.ZipFile(cache / 'platform-35.zip') as archive:
            for filename in ['android.jar', 'android.car.jar']:
                members = [n for n in archive.namelist() if n.endswith('/' + filename)]
                if len(members) != 1:
                    raise SystemExit(f'Ambiguous Android artifact: {filename}')
                (cache / filename).write_bytes(archive.read(members[0]))
        dependencies = [stdlib] + [cache / n for n in ['pleos-tts.jar', 'android.jar', 'android.car.jar']]
        subprocess.run(compiler + ['-classpath', os.pathsep.join(map(str, dependencies)),
                       '-d', str(out / 'voice-compile.jar')] +
                       [str(x) for x in main_sources + sorted((voice / 'src/main/kotlin').rglob('*.kt'))], check=True)
        message = 'PASS Android 35 + android.car + Pleos TTS 3.3.1 real-binary compilation; runtime NOT tested.'
        (out / 'android-compile.txt').write_text(message + '\n')
        print(message)
    print(f'Evidence: {out}')


if __name__ == '__main__':
    main()
