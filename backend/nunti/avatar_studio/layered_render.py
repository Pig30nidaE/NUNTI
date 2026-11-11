"""Compose fixed local Nunti layers, without inference or network access."""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .variant_spec import ASSET_VERSION, VariantContext, build_avatar_spec

ASSET_ROOT = Path(__file__).parent / "assets" / ASSET_VERSION
CANVAS = (768, 768)


class LayerAssetError(ValueError):
    """A packaged layer failed its immutable media boundary."""


def _manifest(root: Path) -> dict:
    try:
        value = json.loads((root / "manifest.json").read_text())
        if value["assetVersion"] != ASSET_VERSION or value["canvas"] != list(CANVAS):
            raise LayerAssetError("ASSET_VERSION_MISMATCH")
        if not isinstance(value["files"], dict) or not isinstance(value["fixedFaceAnchors"], dict):
            raise LayerAssetError("ASSET_MANIFEST_INVALID")
        for name in ("leftEye", "rightEye", "mouth"):
            anchor = value["fixedFaceAnchors"][name]
            if (
                not isinstance(anchor, list)
                or len(anchor) != 2
                or any(
                    isinstance(n, bool)
                    or not isinstance(n, (int, float))
                    or not math.isfinite(n)
                    or not 0 <= n < 768
                    for n in anchor
                )
            ):
                raise LayerAssetError("ASSET_ANCHOR_INVALID")
        return value
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise LayerAssetError("ASSET_MANIFEST_UNAVAILABLE") from exc


def _read_layer(root: Path, relative: str, manifest: dict) -> tuple[Image.Image, str]:
    try:
        # Paths originate in the typed mapper, but the on-disk manifest is also
        # checked before resolving a filesystem path.
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or relative not in manifest["files"]:
            raise LayerAssetError("ASSET_PATH_INVALID")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest["files"][relative]["sha256"]:
            raise LayerAssetError("ASSET_HASH_MISMATCH")
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG" or image.mode != "RGBA" or image.size != CANVAS:
                raise LayerAssetError("ASSET_FORMAT_INVALID")
            image.load()
            return image.copy(), digest
    except (OSError, KeyError, TypeError, UnidentifiedImageError) as exc:
        raise LayerAssetError("ASSET_UNAVAILABLE") from exc


def render_layered_avatar(
    context: VariantContext | None = None,
    route=None,
    *,
    asset_root: Path | None = None,
) -> tuple[bytes, dict]:
    """Keep the v3 renderer's PNG/design return contract.

    ``asset_root`` is an internal testing/deployment hook, never a request field.
    Any missing, corrupt or incompatible active layer falls back atomically to
    the separate bundled base copy. A partial face or partial outfit is not shown.
    """
    context = context or VariantContext()
    spec = build_avatar_spec(context, route)
    root = Path(asset_root) if asset_root is not None else ASSET_ROOT
    hashes = {}
    status = "COMPOSITED"
    try:
        manifest = _manifest(root)
        composed = Image.new("RGBA", CANVAS)
        for layer in spec["layers"]:
            image, digest = _read_layer(root, layer["path"], manifest)
            hashes[layer["path"]] = digest
            composed = Image.alpha_composite(composed, image)
    except LayerAssetError as exc:
        # Separate immutable copy protects against a missing active base/layer.
        # If the fallback bundle itself is damaged, fail explicitly at the media
        # boundary; never invent a replacement mascot.
        fallback_root = ASSET_ROOT / "fallback"
        manifest = _manifest(fallback_root)
        composed, digest = _read_layer(fallback_root, "base.png", manifest)
        hashes = {"fallback/base.png": digest}
        spec.update(
            variantId="nunti-a-fallback-" + digest[:24],
            expression="base",
            destinationMotif="none",
            roadMotif="none",
            routeVariant=0,
            layers=[{"id": "fallback-base", "path": "fallback/base.png"}],
            accessibilityLabel="기본 친근한 눈티",
            fallbackReasons=[*spec["fallbackReasons"], str(exc)],
        )
        spec["palette"]["accent"] = "#ACDABF"
        status = "BASE_FALLBACK"
    buffer = io.BytesIO()
    composed.save(buffer, "PNG", optimize=False)
    png = buffer.getvalue()
    motifs = []
    details = {
        "destinationMotif": {
            "coast": "푸른 스카프와 포켓의 물결에 바다를 담았어요.",
            "mountain": "초록 스카프와 작은 능선에 산의 풍경을 담았어요.",
            "city": "연보라 스카프와 작은 창문에 도시의 풍경을 담았어요.",
        },
        "roadMotif": {
            "urban": "도심길의 꺾임을 스카프의 작은 선으로 담았어요.",
            "highway": "길게 이어지는 길을 스카프의 작은 선으로 담았어요.",
            "rural": "완만한 시골길을 스카프의 작은 곡선으로 담았어요.",
            "mixed": "여러 길의 흐름을 스카프의 작은 선으로 담았어요.",
        },
        "expression": {
            "calm": "직접 고른 차분함을 감은 눈과 작은 미소로 표현했어요.",
            "curious": "직접 고른 호기심을 올라간 눈썹과 미소로 표현했어요.",
            "adventurous": "직접 고른 씩씩함을 또렷한 눈썹과 밝은 미소로 표현했어요.",
        },
    }
    for name, key, target in (
        ("목적지 장식", "destinationMotif", "pocket-and-scarf-accent"),
        ("경로 무늬", "roadMotif", "scarf-stitch"),
        ("명시적으로 선택한 표정", "expression", "fixed-face-anchors"),
    ):
        if spec[key] not in {"none", "base"}:
            motifs.append(
                {
                    "label": name,
                    "source": "NORMALIZED_VARIANT_CONTEXT",
                    "target": target,
                    "detail": details[key][spec[key]],
                }
            )
    if not motifs:
        motifs.append(
            {
                "label": "함께할 기본 눈티",
                "source": "USER_APPROVED_A_MASTER",
                "target": "core",
                "detail": "여행 정보가 준비되기 전에도 익숙한 기본 눈티로 함께해요.",
            }
        )
    design = {
        "displayName": "눈티",
        "personality": "여행의 풍경과 사용자가 고른 기분을 담는 같은 동반자",
        "palette": list(spec["palette"].values()),
        "motifs": motifs,
        "voice": {"description": "따뜻하고 절제된 눈티의 목소리", "rate": 0.96, "pitch": 1.08},
        "renderVersion": ASSET_VERSION,
        "designVersion": spec["mappingVersion"],
        "mediaOrigin": "LOCAL_LAYERS",
        "staticOnly": True,
        "avatarSpec": spec,
        "layerAssets": hashes,
        "renderStatus": status,
        "imageSha256": hashlib.sha256(png).hexdigest(),
        "faceAnchors": manifest["fixedFaceAnchors"],
    }
    return png, design
