#!/usr/bin/env python3
"""Measure a source WAV's best normalized correlation inside captured PCM.

Read-only file comparison. No pass threshold, speech recognition, or listening
claim. Uses NumPy from .local/journey-voice/venv. PCM timing is not wall time.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import wave

import numpy as np


def load(path):
    raw = path.read_bytes()
    with wave.open(io.BytesIO(raw), "rb") as sound:
        if sound.getsampwidth() != 2 or sound.getcomptype() != "NONE":
            raise ValueError("Only uncompressed PCM16 WAV is supported: " + str(path))
        channels, rate, frames = sound.getnchannels(), sound.getframerate(), sound.getnframes()
        samples = np.frombuffer(sound.readframes(frames), dtype="<i2").astype(np.float64)
    if not frames or len(samples) != frames * channels:
        raise ValueError("Empty or truncated PCM: " + str(path))
    mono = samples.reshape(frames, channels).mean(axis=1)
    return mono, {
        "path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
        "sampleRateHz": rate, "channels": channels, "frames": frames,
        "pcmDurationSeconds": frames / rate,
        "sampleWidthBytes": 2, "peak": float(np.max(np.abs(samples))),
        "rms": float(np.sqrt(np.mean(samples * samples))),
        "monoDownmixPeak": float(np.max(np.abs(mono))),
        "monoDownmixRms": float(np.sqrt(np.mean(mono * mono))),
    }


def linear_resample(samples, source_rate, target_rate):
    if source_rate == target_rate:
        return samples
    count = round(len(samples) * target_rate / source_rate)
    positions = np.arange(count, dtype=np.float64) * source_rate / target_rate
    return np.interp(positions, np.arange(len(samples)), samples)


def feature_ncc(source, captured):
    """Per-feature temporal Pearson correlation at each valid shared offset."""
    n = source.shape[0]
    values = []
    for column in range(source.shape[1]):
        x, y = source[:, column], captured[:, column]
        centered = x - np.mean(x)
        energy = np.dot(centered, centered)
        if energy <= 0:
            continue
        sums = np.concatenate(([0.0], np.cumsum(y)))
        squares = np.concatenate(([0.0], np.cumsum(y * y)))
        window_energy = np.maximum(squares[n:] - squares[:-n] - (sums[n:] - sums[:-n]) ** 2 / n, 0)
        denominator = np.sqrt(energy * window_energy)
        correlation = np.zeros(len(y) - n + 1)
        np.divide(np.correlate(y, centered, mode="valid"), denominator, out=correlation, where=denominator > 0)
        values.append(np.clip(correlation, -1, 1))
    if not values:
        raise ValueError("No varying source analysis features")
    values = np.array(values)
    mean = np.mean(values, axis=0)
    index = int(np.argmax(mean))
    return index, float(mean[index]), [float(row[index]) for row in values]


def phase_robust_metrics(source, captured, rate):
    # Fixed before examining pair scores. No time stretching, rate optimization,
    # dynamic warping or selection of source subsegments.
    window, hop = round(rate * .032), round(rate * .010)
    bands = ((100, 300), (300, 800), (800, 1600), (1600, 3200), (3200, 8000))
    frequencies = np.fft.rfftfreq(window, 1 / rate)
    taper = np.hanning(window)

    def features(samples):
        frames = np.lib.stride_tricks.sliding_window_view(samples, window)[::hop]
        envelope = np.sqrt(np.mean(frames * frames, axis=1))[:, None]
        spectrum = np.abs(np.fft.rfft(frames * taper, axis=1)) ** 2
        band_amplitude = np.stack([np.sqrt(np.mean(spectrum[:, (frequencies >= low) & (frequencies < high)], axis=1)) for low, high in bands], axis=1)
        return envelope, band_amplitude

    x_envelope, x_bands = features(source)
    y_envelope, y_bands = features(captured)
    envelope_index, envelope_score, _ = feature_ncc(x_envelope, y_envelope)
    band_index, band_score, per_band = feature_ncc(x_bands, y_bands)
    return {
        "method": "Full-source amplitude envelope and per-band temporal amplitude NCC, fixed windows; maximum mean of band correlations at one shared offset",
        "windowMilliseconds": 32, "hopMilliseconds": 10, "windowFunctionForSpectrum": "Hann",
        "bandsHz": [list(band) for band in bands],
        "rmsEnvelope": {"normalizedCrossCorrelation": envelope_score, "captureStartAnalysisFrame": envelope_index, "capturePcmStartSeconds": envelope_index * hop / rate},
        "fiveBandAmplitude": {"meanNormalizedCrossCorrelation": band_score, "perBandNormalizedCrossCorrelation": per_band, "captureStartAnalysisFrame": band_index, "capturePcmStartSeconds": band_index * hop / rate},
        "limits": "Phase-insensitive features support comparison of temporal energy patterns. Same-text different-speaker controls can also correlate. No identity/quality/pass verdict or wall-clock onset claim.",
    }


def compare(source_path, capture_path, include_phase_robust=False):
    source, source_info = load(source_path)
    captured, capture_info = load(capture_path)
    source = linear_resample(source, source_info["sampleRateHz"], capture_info["sampleRateHz"])
    n, m = len(source), len(captured)
    if m < n:
        raise ValueError("Capture PCM is shorter than the entire resampled source; full-source comparison unavailable")
    centered = source - np.mean(source)
    source_energy = float(np.dot(centered, centered))
    if source_energy <= 0:
        raise ValueError("Source PCM has no varying signal")
    fft_size = 1 << (m + n - 2).bit_length()
    convolution = np.fft.irfft(
        np.fft.rfft(captured, fft_size) * np.fft.rfft(centered[::-1], fft_size), fft_size
    )
    covariance = convolution[n - 1:m]
    sums = np.concatenate(([0.0], np.cumsum(captured)))
    squares = np.concatenate(([0.0], np.cumsum(captured * captured)))
    window_sum = sums[n:] - sums[:-n]
    window_energy = np.maximum(squares[n:] - squares[:-n] - window_sum * window_sum / n, 0)
    denominator = np.sqrt(source_energy * window_energy)
    scores = np.full(len(covariance), -np.inf)
    np.divide(covariance, denominator, out=scores, where=denominator > 0)
    if not np.isfinite(scores).any():
        raise ValueError("Capture PCM contains no varying window for normalized comparison")
    index = int(np.argmax(scores))
    score = float(np.clip(scores[index], -1, 1))
    matched = captured[index:index + n]
    gain = float(covariance[index] / source_energy)
    offset = float(np.mean(matched) - gain * np.mean(source))
    residual = matched - (gain * source + offset)
    rate = capture_info["sampleRateHz"]
    result = {
        "schemaVersion": 1, "source": source_info, "capture": capture_info,
        "method": "Full source, mono channel mean, source linear resample to capture rate, FFT cross-correlation normalized by each capture window's centered energy",
        "numpyVersion": np.__version__, "comparisonSampleRateHz": rate,
        "sourceFramesAfterResample": n, "candidateWindowCount": len(scores),
        "bestMatch": {
            "normalizedCrossCorrelation": score, "captureStartFrame": index,
            "captureEndFrameExclusive": index + n, "capturePcmStartSeconds": index / rate,
            "capturePcmEndSeconds": (index + n) / rate, "windowDurationSeconds": n / rate,
            "positiveGainExpected": True, "fittedGain": gain, "fittedDcOffset": offset,
            "windowPeak": float(np.max(np.abs(matched))),
            "windowRms": float(np.sqrt(np.mean(matched * matched))),
            "residualRmsAfterGainAndDcFit": float(np.sqrt(np.mean(residual * residual))),
        },
        "acceptance": "MEASUREMENT_ONLY_NO_PASS_THRESHOLD_OR_ATTRIBUTION_VERDICT",
        "humanListeningPerformed": False, "speechQualityEvaluated": False,
        "limits": [
            "The maximum correlation is a measurement among searched windows, not proof of unique attribution or a calibrated statistical significance.",
            "Linear resampling is an analysis approximation; runtime resampling/filtering, dropped frames and clock drift may reduce correlation.",
            "Emulator stream may omit empty time. PCM frame position is not wall-clock audible onset or cancellation latency.",
        ],
    }
    if include_phase_robust:
        result["phaseRobustMetrics"] = phase_robust_metrics(source, captured, rate)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Optional new JSON result, refuses existing file")
    parser.add_argument("--phase-robust", action="store_true", help="Also measure fixed32ms/10ms-hop RMS envelope and five-band amplitude NCC without changing raw NCC")
    args = parser.parse_args()
    try:
        result = compare(args.source, args.capture, args.phase_robust)
        payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x") as destination:
                destination.write(payload)
        print(payload, end="")
        return 0
    except (ValueError, OSError, wave.Error) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
