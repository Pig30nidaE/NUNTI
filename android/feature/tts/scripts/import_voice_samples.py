#!/usr/bin/env python3
"""Validate a six-clip experiment and copy its exact bytes/provenance into debug assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=Path, required=True)
    args = parser.parse_args()
    source = args.samples.resolve()
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    clips = manifest['clips']
    assert manifest['schemaVersion'] == 1 and len(clips) == 6
    assert len({clip['clipId'] for clip in clips}) == 6
    assert len({clip['speakerId'] for clip in clips}) == 3
    for clip in clips:
        name = clip['audioPath']
        assert Path(name).name == name and name.endswith('.wav')
        data = (source / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == clip['audioSha256']
        assert hashlib.sha256(clip['text'].encode('utf-8')).hexdigest() == clip['textSha256']
        with wave.open(str(source / name), 'rb') as wav:
            assert wav.getcomptype() == 'NONE' and wav.getsampwidth() == clip['sampleWidthBytes'] == 2
            assert wav.getframerate() == clip['sampleRateHz'] and wav.getnchannels() == clip['channels']
            assert abs(wav.getnframes() * 1000 / wav.getframerate() - clip['durationMs']) <= 1
        for key in ('providerId', 'characterId', 'profileId', 'speakerId', 'locale', 'bindingId', 'sourceModelRevision'):
            assert clip[key] == clip['binding'][key]
        assert clip['preset'] == clip['binding']['preset']
    provenance = source.parent
    licenses = provenance / 'licenses'
    references = provenance / 'source-references.json'
    assert references.is_file()
    assert (licenses / 'supertonic-code-MIT.txt').is_file()
    assert (licenses / 'supertonic-3-model-license.txt').is_file()
    target = Path(__file__).resolve().parents[3] / 'app/src/debug/assets/journey-voice'
    target.mkdir(parents=True, exist_ok=True)
    for name in ['manifest.json'] + [clip['audioPath'] for clip in clips]:
        temporary = target / (name + '.pending')
        shutil.copyfile(source / name, temporary)
        temporary.replace(target / name)
    shutil.copytree(licenses, target / 'licenses', dirs_exist_ok=True)
    shutil.copyfile(references, target / references.name)
    print(json.dumps({'source': str(source), 'target': str(target), 'clips': len(clips),
                      'manifestSha256': hashlib.sha256((target / 'manifest.json').read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
