"""Deterministic, local layer selection for the opt-in Nunti A renderer.

This contract is separate from the compact v1 server AvatarSpec. SDK-looking
labels supplied by a client never establish supported or verified SDK fields.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAPPING_VERSION = "nunti-layers-v1"
ASSET_VERSION = "nunti-a-layers-v1"
CHARACTER_ID = "nunti-a-v1"

DestinationCategory = Literal["coast", "mountain", "city", "nature", "general", "unknown"]
RoadType = Literal["urban", "highway", "rural", "mixed", "unknown"]
Mood = Literal["calm", "curious", "adventurous", "bright", "unset"]
ProvenanceKind = Literal[
    "direct-sdk",
    "app-derived",
    "user-selected",
    "explicit-user-choice",
    "mock",
    "fallback",
    "unknown",
]
Expression = Literal["base", "calm", "curious", "adventurous"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class VariantContext(_Strict):
    routeId: str | None = Field(default=None, min_length=1, max_length=128)
    routeRevision: int = Field(default=1, ge=1, le=2_147_483_647)
    mappingVersion: Literal["nunti-layers-v1"] = MAPPING_VERSION
    seed: str = Field(default="0", min_length=1, max_length=128)
    destinationCategory: DestinationCategory = "unknown"
    roadType: RoadType = "unknown"
    userSelectedMood: Mood = "unset"
    displayMode: Literal["day", "night"] = "day"
    provenance: dict[str, ProvenanceKind] = Field(default_factory=dict, max_length=6)

    @field_validator("routeId", "seed")
    @classmethod
    def bounded_identifier(cls, value):
        if value is None:
            return value
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("INVALID_VARIANT_IDENTIFIER")
        return value.strip()

    @field_validator("provenance")
    @classmethod
    def known_provenance_fields(cls, value):
        allowed = {
            "routeId",
            "routeRevision",
            "routeGeometry",
            "destinationCategory",
            "roadType",
            "userSelectedMood",
        }
        if set(value) - allowed:
            raise ValueError("UNKNOWN_VARIANT_PROVENANCE_FIELD")
        return value


class RouteInput(Protocol):
    points: list[list[float | int]]
    inputOrigin: str


class LayerRef(_Strict):
    id: str
    path: str


class NormalizedContext(_Strict):
    routeId: str | None
    routeRevision: int
    mappingVersion: Literal["nunti-layers-v1"]
    seed: str
    destinationCategory: DestinationCategory
    roadType: RoadType
    userSelectedMood: Mood
    displayMode: Literal["day", "night"]
    routePointCount: int
    routeGeometrySource: str


class LayeredAvatarSpec(_Strict):
    schemaVersion: Literal["nunti.avatar.layers/1"] = "nunti.avatar.layers/1"
    characterId: Literal["nunti-a-v1"] = CHARACTER_ID
    variantId: str
    mappingVersion: Literal["nunti-layers-v1"] = MAPPING_VERSION
    assetVersion: Literal["nunti-a-layers-v1"] = ASSET_VERSION
    seed: str
    routeId: str | None
    routeFingerprint: str
    expression: Expression
    destinationMotif: Literal["none", "coast", "mountain", "city"]
    roadMotif: Literal["none", "urban", "highway", "rural", "mixed"]
    routeVariant: int = Field(ge=0, le=2)
    displayMode: Literal["day", "night"]
    normalizedContext: NormalizedContext
    provenance: dict[str, str]
    baseAsset: Literal["base.png"] = "base.png"
    layers: list[LayerRef]
    palette: dict[str, str]
    accessibilityLabel: str
    fallbackReasons: list[str]
    motion: Literal["none"] = "none"


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_avatar_spec(context: VariantContext, route: RouteInput | None) -> dict:
    """Map validated inputs to constant asset paths without I/O or inference.

    Request IDs, timestamps, destination text, purpose and vehicle events are
    deliberately absent. A path update changes the fingerprint while the master
    geometry and face anchors remain fixed. Three decorative stripe alternatives
    may legitimately collide for different routes. An explicit userSelectedMood
    field is a user selection unless supplied provenance says otherwise; this
    function never interprets purpose text or driving telemetry as user mood.
    """
    reasons = []
    points = [[float(x), float(y)] for x, y in route.points] if route is not None else []
    route_fingerprint = _digest(points)
    route_id = context.routeId or ("route-" + route_fingerprint[:20] if points else None)
    geometry_source = route.inputOrigin if route is not None else "UNAVAILABLE"
    geometry_provenance = {
        "TEST_ROUTE": "mock",
        "ROUTE_FILE": "user-selected",
        "NAVIGATION_SCREENSHOT": "app-derived",
        "API_ROUTE": "app-derived",
        "UNAVAILABLE": "fallback",
    }[geometry_source]

    destination = context.destinationCategory
    road = context.roadType
    mood = context.userSelectedMood
    route_id_source = "app-derived" if points else "fallback"
    if context.routeId:
        route_id_source = context.provenance.get("routeId", "user-selected")
        if route_id_source == "direct-sdk":
            route_id_source = "app-derived"
            reasons.append("ROUTE_ID_SDK_PROVENANCE_NOT_VERIFIED")
        elif route_id_source == "explicit-user-choice":
            route_id_source = "user-selected"
    revision_source = context.provenance.get("routeRevision", "app-derived")
    if revision_source == "direct-sdk":
        revision_source = "app-derived"
        reasons.append("ROUTE_REVISION_SDK_PROVENANCE_NOT_VERIFIED")
    elif revision_source == "explicit-user-choice":
        revision_source = "user-selected"
    provenance = {
        "routeId": route_id_source,
        "routeRevision": revision_source,
        "routeGeometry": geometry_provenance,
    }
    for name, value, unknown in (
        ("destinationCategory", destination, "unknown"),
        ("roadType", road, "unknown"),
    ):
        source = context.provenance.get(name, "app-derived")
        if source in {"direct-sdk", "fallback", "unknown"}:
            if value != unknown:
                reasons.append(
                    "UNVERIFIED_"
                    + ("DESTINATION" if name == "destinationCategory" else "ROAD_TYPE")
                )
            if name == "destinationCategory":
                destination = "unknown"
            else:
                road = "unknown"
            source = "unknown"
        elif source == "explicit-user-choice":
            source = "user-selected"
        provenance[name] = source if value != unknown else "fallback"

    mood_source = context.provenance.get("userSelectedMood", "user-selected")
    if mood != "unset" and mood_source not in {"user-selected", "explicit-user-choice", "mock"}:
        mood = "unset"
        reasons.append("MOOD_NOT_USER_SELECTED")
    provenance["userSelectedMood"] = (
        "fallback" if mood == "unset" else "mock" if mood_source == "mock" else "user-selected"
    )

    if destination in {"unknown", "general"}:
        reasons.append("UNKNOWN_DESTINATION")
    elif destination == "nature":
        reasons.append("UNSUPPORTED_DESTINATION")
    if road == "unknown":
        reasons.append("UNKNOWN_ROAD_TYPE")
    if mood == "unset":
        reasons.append("MISSING_MOOD")
    elif mood == "bright":
        reasons.append("UNSUPPORTED_MOOD")

    normalized = NormalizedContext(
        routeId=route_id,
        routeRevision=context.routeRevision,
        mappingVersion=context.mappingVersion,
        seed=context.seed,
        destinationCategory=destination,
        roadType=road,
        userSelectedMood=mood,
        displayMode=context.displayMode,
        routePointCount=len(points),
        routeGeometrySource=geometry_source,
    )
    identity = {
        "context": normalized.model_dump(),
        "routeFingerprint": route_fingerprint,
        "provenance": provenance,
        "assetVersion": ASSET_VERSION,
        "characterId": CHARACTER_ID,
    }
    fingerprint = _digest(identity)
    route_variant = (
        int(
            _digest(
                {
                    "routeId": route_id,
                    "routeFingerprint": route_fingerprint,
                    "mappingVersion": MAPPING_VERSION,
                    "seed": context.seed,
                }
            )[:16],
            16,
        )
        % 3
    )

    expression = mood if mood in {"calm", "curious", "adventurous"} else "base"
    destination_motif = destination if destination in {"coast", "mountain", "city"} else "none"
    road_motif = road if road != "unknown" else "none"
    if not points:
        reasons.insert(0, "MISSING_ROUTE")
        expression, destination_motif, road_motif, route_variant = "base", "none", "none", 0

    layers = [
        LayerRef(id="core-" + name, path="core/" + name + ".png")
        for name in (
            "body",
            "head",
            "sprout",
            "scarf",
            "bag",
            "badge",
        )
    ]
    layers.append(
        LayerRef(id="expression-" + expression, path="expressions/" + expression + ".png")
    )
    if destination_motif != "none":
        layers.append(
            LayerRef(
                id="destination-" + destination_motif,
                path="destinations/" + destination_motif + ".png",
            )
        )
    if road_motif != "none":
        layers.append(
            LayerRef(id="road-" + road_motif, path=f"roads/{road_motif}-{route_variant}.png")
        )

    destination_label = {
        "none": "기본",
        "coast": "바다의 물결을 담은",
        "mountain": "산의 능선을 담은",
        "city": "도시의 창문을 담은",
    }[destination_motif]
    mood_label = {
        "base": "친근한",
        "calm": "차분한",
        "curious": "호기심 많은",
        "adventurous": "씩씩한",
    }[expression]
    palette = {
        "body": "#F5E6D8",
        "mint": "#ACDABF",
        "blue": "#B6D1E4",
        "face": "#FED7C6",
        "ink": "#51362C",
        "accent": {"none": "#ACDABF", "coast": "#5595B0", "mountain": "#709260", "city": "#9780B1"}[
            destination_motif
        ],
        "background": "#F6F4EF" if context.displayMode == "day" else "#263C38",
    }
    return LayeredAvatarSpec(
        variantId="nunti-a-" + fingerprint[:24],
        seed=context.seed,
        routeId=route_id,
        routeFingerprint=route_fingerprint,
        expression=expression,
        destinationMotif=destination_motif,
        roadMotif=road_motif,
        routeVariant=route_variant,
        displayMode=context.displayMode,
        normalizedContext=normalized,
        provenance=provenance,
        layers=layers,
        palette=palette,
        accessibilityLabel=f"{destination_label} {mood_label} 눈티",
        fallbackReasons=list(dict.fromkeys(reasons)),
    ).model_dump()
