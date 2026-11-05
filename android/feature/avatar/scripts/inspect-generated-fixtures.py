#!/usr/bin/env python3
"""Inspect existing PNG source bytes without Pillow or editing the images."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def paeth(left: int, up: int, corner: int) -> int:
    prediction = left + up - corner
    distances = abs(prediction - left), abs(prediction - up), abs(prediction - corner)
    return (left, up, corner)[distances.index(min(distances))]


def inspect(path: Path, root: Path) -> dict:
    source = path.read_bytes()
    if source[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not PNG: {path}")
    offset = 8
    compressed = bytearray()
    transparency = None
    while offset < len(source):
        count = struct.unpack(">I", source[offset:offset + 4])[0]
        kind = source[offset + 4:offset + 8]
        content = source[offset + 8:offset + 8 + count]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", content)
        elif kind == b"IDAT":
            compressed.extend(content)
        elif kind == b"tRNS":
            transparency = list(content)
        offset += count + 12
        if kind == b"IEND":
            break
    if depth != 8 or color not in (2, 6) or interlace != 0 or transparency is not None:
        raise ValueError(f"Unsupported PNG layout in fixture inspector: {path}")
    channels = 4 if color == 6 else 3
    stride = width * channels
    pixels = zlib.decompress(compressed)
    if len(pixels) != height * (stride + 1):
        raise ValueError(f"Unexpected PNG data size: {path}")
    previous = bytearray(stride)
    alpha = [0] * 256
    for y in range(height):
        start = y * (stride + 1)
        filtering = pixels[start]
        if filtering not in range(5):
            raise ValueError(f"Unknown PNG filter: {filtering}")
        row = bytearray(pixels[start + 1:start + stride + 1])
        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up = previous[x]
            corner = previous[x - channels] if x >= channels else 0
            predictor = (0, left, up, (left + up) // 2, paeth(left, up, corner))[filtering]
            row[x] = (row[x] + predictor) & 255
        if color == 6:
            for value in row[3::4]:
                alpha[value] += 1
        else:
            alpha[255] += width
        previous = row
    return {
        "path": str(path.relative_to(root)), "sha256": hashlib.sha256(source).hexdigest(),
        "mimeType": "image/png", "width": width, "height": height, "byteSize": len(source),
        "colorType": color, "fullyTransparentPixels": alpha[0],
        "partialAlphaPixels": sum(alpha[1:255]), "fullyOpaquePixels": alpha[255],
        "nativeAlphaCutout": color == 6 and alpha[0] > 0 and sum(alpha[1:]) > 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    results = [inspect(path, root) for path in sorted((root / "docs/design/journey-characters/concepts").glob("*.png"))]
    report = {"status": "SOURCE_PNG_BYTES_AND_NATIVE_ALPHA_INSPECTED", "assetsEdited": False,
              "scope": "Source file format and alpha only. Edge quality and visual appeal are not approved.",
              "assets": results}
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
