"""Bounded native RGBA and PCM validation, without image/model dependencies."""

import io
import struct
import subprocess
import wave
import zlib

from .models import sha


def inspect_png(data, require_alpha=True):
    if not 1 <= len(data) <= 8 * 1024 * 1024 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("INVALID_PNG")
    cursor, payload, dims, ended = 8, bytearray(), None, False
    while cursor + 12 <= len(data):
        length = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor + 4 : cursor + 8]
        end = cursor + 12 + length
        if end > len(data):
            raise ValueError("INVALID_PNG_CHUNKS")
        block = data[cursor + 8 : cursor + 8 + length]
        crc = struct.unpack_from(">I", data, cursor + 8 + length)[0]
        if zlib.crc32(kind + block) & 0xFFFFFFFF != crc:
            raise ValueError("PNG_CRC_MISMATCH")
        if kind == b"IHDR":
            if dims is not None or cursor != 8 or length != 13:
                raise ValueError("INVALID_PNG_HEADER")
            width, height, bits, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", block
            )
            if not 64 <= width <= 2048 or not 64 <= height <= 2048 or width * height > 4194304:
                raise ValueError("PNG_DIMENSIONS_EXCEEDED")
            if bits != 8 or color not in (2, 6) or (compression, filtering, interlace) != (0, 0, 0):
                raise ValueError("NATIVE_RGBA_REQUIRED")
            if require_alpha and color != 6:
                raise ValueError("NATIVE_RGBA_REQUIRED")
            bytes_per_pixel = 4 if color == 6 else 3
            dims = (width, height)
        elif kind == b"IDAT":
            payload.extend(block)
        elif kind == b"IEND":
            ended = True
            cursor = end
            break
        cursor = end
    if not dims or not ended or cursor != len(data):
        raise ValueError("INVALID_PNG_STRUCTURE")
    width, height = dims
    maximum = (width * bytes_per_pixel + 1) * height
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(payload, maximum + 1)
    if len(raw) != maximum or not decompressor.eof or decompressor.unused_data:
        raise ValueError("PNG_PIXEL_SIZE_MISMATCH")
    if not require_alpha:
        return {
            "width": width,
            "height": height,
            "byteLength": len(data),
            "sha256": sha(data),
            "mimeType": "image/png",
        }
    # Reconstruct pixels to prove transparency is real, not just an RGBA header.
    prior, transparent, visible = bytearray(width * 4), False, False
    stride = width * 4 + 1
    for row_index in range(height):
        method = raw[row_index * stride]
        row = bytearray(raw[row_index * stride + 1 : (row_index + 1) * stride])
        if method > 4:
            raise ValueError("INVALID_PNG_FILTER")
        for i in range(len(row)):
            left = row[i - 4] if i >= 4 else 0
            above = prior[i]
            corner = prior[i - 4] if i >= 4 else 0
            if method == 1:
                predictor = left
            elif method == 2:
                predictor = above
            elif method == 3:
                predictor = (left + above) // 2
            elif method == 4:
                p = left + above - corner
                distances = (abs(p - left), abs(p - above), abs(p - corner))
                predictor = (left, above, corner)[distances.index(min(distances))]
            else:
                predictor = 0
            row[i] = (row[i] + predictor) & 255
        alpha = row[3::4]
        transparent |= min(alpha) == 0
        visible |= max(alpha) > 0
        prior = row
    if not transparent or not visible:
        raise ValueError("TRANSPARENT_VISIBLE_CHARACTER_REQUIRED")
    return {
        "width": width,
        "height": height,
        "byteLength": len(data),
        "sha256": sha(data),
        "mimeType": "image/png",
    }


def pcm_wav(data, sample_rate=24000):
    if not data or len(data) % 2 or len(data) > 24000 * 2 * 30:
        raise ValueError("INVALID_PCM_AUDIO")
    stream = io.BytesIO()
    with wave.open(stream, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(data)
    return stream.getvalue()


def inspect_wav(data):
    if not 44 <= len(data) <= 2000000:
        raise ValueError("INVALID_AUDIO_SIZE")
    if (
        data[:4] != b"RIFF"
        or data[8:12] != b"WAVE"
        or struct.unpack_from("<I", data, 4)[0] + 8 != len(data)
    ):
        raise ValueError("INVALID_AUDIO_FORMAT")
    cursor, format_seen, sample_bytes = 12, False, None
    while cursor + 8 <= len(data):
        kind = data[cursor : cursor + 4]
        size = struct.unpack_from("<I", data, cursor + 4)[0]
        start = cursor + 8
        if size > len(data) - start:
            raise ValueError("INVALID_AUDIO_FORMAT")
        if kind == b"fmt ":
            if (
                format_seen
                or size < 16
                or struct.unpack_from("<HHIIHH", data, start) != (1, 1, 24000, 48000, 2, 16)
            ):
                raise ValueError("INVALID_AUDIO_FORMAT")
            format_seen = True
        elif kind == b"data":
            if sample_bytes is not None or size <= 0 or size % 2:
                raise ValueError("INVALID_AUDIO_FORMAT")
            sample_bytes = size
        cursor = start + size + size % 2
    if cursor != len(data) or not format_seen or sample_bytes is None:
        raise ValueError("INVALID_AUDIO_FORMAT")
    frames = sample_bytes // 2
    if not 0 < frames <= 720000:
        raise ValueError("INVALID_AUDIO_LENGTH")
    return {
        "audioSha256": sha(data),
        "sampleRateHz": 24000,
        "channels": 1,
        "sampleWidthBytes": 2,
        "durationMs": max(1, round(frames / 24)),
    }


def normalize_audio(raw, format_hint, ffmpeg=None):
    raw_sha = sha(raw)
    if format_hint == "pcm_24000":
        data = pcm_wav(raw)
    else:
        try:
            inspect_wav(raw)
            return raw, raw_sha
        except ValueError:
            pass
        if not ffmpeg:
            raise ValueError("AUDIO_NORMALIZER_REQUIRED")
        completed = subprocess.run(
            [
                str(ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-protocol_whitelist",
                "pipe",
                "-i",
                "pipe:0",
                "-f",
                "wav",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-t",
                "31",
                "pipe:1",
            ],
            input=raw,
            capture_output=True,
            timeout=35,
            check=False,
        )
        if completed.returncode:
            raise ValueError("AUDIO_NORMALIZATION_FAILED")
        # One extra second bounds decoding, and one sample beyond 30s proves any
        # overlong output is REJECTED by pcm_wav, never accepted as a cut sentence.
        # ffmpeg's nonseekable WAV output uses sentinel lengths. Rewrap PCM via wave.
        try:
            with wave.open(io.BytesIO(completed.stdout), "rb") as source:
                data = pcm_wav(source.readframes(720001))
        except (wave.Error, EOFError) as exc:
            raise ValueError("AUDIO_NORMALIZATION_FAILED") from exc
    inspect_wav(data)
    return data, raw_sha


def route_guide(points, side=256):
    """An authored reference PNG of the input route, not a generated character."""
    pixels = bytearray([255, 255, 255, 255] * side * side)
    for a, b in zip(points, points[1:], strict=False):
        dx, dy = (b[0] - a[0]) * (side - 24), (b[1] - a[1]) * (side - 24)
        steps = max(1, int(max(abs(dx), abs(dy)) * 2))
        for step in range(steps + 1):
            x = round(12 + a[0] * (side - 24) + dx * step / steps)
            y = round(12 + a[1] * (side - 24) + dy * step / steps)
            for ox in range(-2, 3):
                for oy in range(-2, 3):
                    if 0 <= x + ox < side and 0 <= y + oy < side:
                        index = ((y + oy) * side + x + ox) * 4
                        pixels[index : index + 4] = bytes((57, 122, 116, 255))

    def chunk(kind, content):
        return (
            struct.pack(">I", len(content))
            + kind
            + content
            + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\0" + pixels[row * side * 4 : (row + 1) * side * 4] for row in range(side))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
