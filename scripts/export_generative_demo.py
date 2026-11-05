#!/usr/bin/env python3
"""Mux an actual fixture UI recording with its timestamped emulator speaker PCM."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import wave

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path, help='Successful touch-* evidence directory with --record-speaker --record-video')
    parser.add_argument('--output', type=Path, required=True, help='New .mp4 file; existing files are never replaced')
    args = parser.parse_args()
    run = args.run.resolve()
    output = args.output.resolve()
    assert output.suffix == '.mp4' and not output.exists(), 'Choose a new .mp4 output path'
    output.parent.mkdir(parents=True, exist_ok=True)
    proof = json.loads((run / 'verification.json').read_text())
    assert proof['status'] == 'PASS_REAL_FIELDS_GESTURE_BUTTON_AND_AUDIO'
    assert proof['mode'] == 'OFFLINE_FIXTURE' and proof['providerApiCalls'] == 0
    recording = proof['screenRecording']
    video = run / 'screen-silent.mp4'
    assert recording['source'] == 'ACTUAL_ANDROID_SCREENRECORD' and sha(video) == recording['sha256']
    source_wav = run / 'speaker.wav'
    assert sha(source_wav) == proof['speakerCapture']['sha256']
    assert proof['speakerCapture']['source'] == 'AUTHENTICATED_EMULATOR_SPEAKER_STREAM'
    packets = [json.loads(line) for line in (run / 'speaker.packets.jsonl').read_text().splitlines() if line]
    assert 0 < len(packets) <= 100000
    first_us = packets[0]['captureTimestampEpochUs']
    offset = (first_us * 1000 - recording['startedEpochNs']) / 1e9
    assert 0 <= offset <= 90, 'Speaker stream did not begin within the recording'
    with wave.open(str(source_wav), 'rb') as source:
        channels, width, rate, frames = source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes()
        assert (channels, width, rate) == (2, 2, 48000) and source.getcomptype() == 'NONE'
        pcm = source.readframes(frames)
    assert len(pcm) == frames * 4
    aligned = output.with_suffix('.wallclock.wav')
    report_path = output.with_suffix('.verification.json')
    assert not aligned.exists() and not report_path.exists(), 'Output sidecar already exists'
    source_cursor = output_cursor = gaps = overlaps = 0
    last_us = first_us
    # The installed emulator proto defines timestamp as capture epoch microseconds.
    # Keep every received PCM frame. Fill absent wall-clock intervals with silence.
    # Jitter that overlaps a previous packet is appended without dropping samples.
    with wave.open(str(aligned), 'wb') as dest:
        dest.setnchannels(channels); dest.setsampwidth(width); dest.setframerate(rate)
        for index, packet in enumerate(packets):
            timestamp = packet['captureTimestampEpochUs']
            count = packet['frames']
            assert packet['index'] == index and packet['pcmStartFrame'] == source_cursor
            assert timestamp >= last_us and 0 <= timestamp - first_us <= 300_000_000
            assert 0 <= count <= rate * 5 and packet['bytes'] == count * 4
            target = round((timestamp - first_us) * rate / 1_000_000)
            if target > output_cursor:
                gap = target - output_cursor
                dest.writeframesraw(bytes(gap * 4))
                gaps += gap; output_cursor = target
            elif target < output_cursor:
                overlaps += 1
            end = source_cursor + count
            assert end <= frames
            dest.writeframesraw(pcm[source_cursor * 4:end * 4])
            source_cursor = end; output_cursor += count; last_us = timestamp
    assert source_cursor == frames, 'Packet index did not cover the complete original WAV'
    cache = ROOT / '.local/generative-mvp/swift-cache'
    cache.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(cache), SWIFT_MODULECACHE_PATH=str(cache))
    result = subprocess.run(['/usr/bin/xcrun', 'swift', str(ROOT / 'scripts/mux_emulator_demo.swift'),
        str(video), str(aligned), str(offset), str(output)], env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Local media export failed: ' + result.stdout.strip()[:1500])
    mux = json.loads(result.stdout)
    assert output.is_file() and output.stat().st_size > 1000
    report = {'status': 'PASS_ACTUAL_FIXTURE_DEMO_WITH_SPEAKER_AUDIO',
        'at': datetime.now(timezone.utc).isoformat(), 'run': str(run.relative_to(ROOT)),
        'requestId': proof['requestId'], 'mode': 'OFFLINE_FIXTURE',
        'newImageOrTimbreGenerated': False, 'providerApiCalls': 0, 'humanQualityVerified': False,
        'videoSource': recording['source'], 'audioSource': proof['speakerCapture']['source'],
        'sourceVideoSha256': sha(video), 'sourceWavSha256': sha(source_wav),
        'allOriginalPcmFramesPreserved': True, 'insertedSilenceFrames': gaps,
        'overlappingTimestampPacketsAppended': overlaps, 'audioOffsetSeconds': offset,
        'syncLimit': 'Packet capture timestamps plus approximate host screenrecord start; not a latency measurement.',
        'mux': mux, 'output': str(output), 'sha256': sha(output), 'bytes': output.stat().st_size}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'video': str(output), 'verification': str(report_path),
        'bytes': report['bytes']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
