#!/usr/bin/env python3
"""macOS Yuna listening reference only. NOT Pleos output and NOT a production audio asset."""
from pathlib import Path
import subprocess
import tempfile
import wave

module = Path(__file__).resolve().parents[1]
lines = (module / 'demo/approved-ko.txt').read_text().splitlines()
output = module / 'demo/reference-ko.wav'
with tempfile.TemporaryDirectory(prefix='nunti-reference-') as directory:
    chunks = []
    parameters = None
    for index, line in enumerate(lines):
        aiff = Path(directory) / f'{index}.aiff'
        wav = Path(directory) / f'{index}.wav'
        subprocess.run(['/usr/bin/say', '-v', 'Yuna', '-o', str(aiff), line], check=True)
        subprocess.run(['/usr/bin/afconvert', str(aiff), str(wav), '-f', 'WAVE', '-d', 'LEI16'], check=True)
        with wave.open(str(wav), 'rb') as source:
            fmt = (source.getnchannels(), source.getsampwidth(), source.getframerate())
            if source.getnframes() == 0:
                raise SystemExit('Speech service returned no audio; do not publish an empty reference.')
            if parameters is not None and parameters != fmt:
                raise SystemExit('Inconsistent PCM format')
            parameters = fmt
            silence = bytes(round(fmt[2] * .180) * fmt[0] * fmt[1])
            chunks += [silence, source.readframes(source.getnframes())]
    with wave.open(str(output), 'wb') as target:
        target.setnchannels(parameters[0]); target.setsampwidth(parameters[1]); target.setframerate(parameters[2])
        target.writeframes(b''.join(chunks))
with wave.open(str(output), 'rb') as result:
    print(f'{output}: {result.getnframes()/result.getframerate():.2f}s; macOS reference, not Pleos')
