"""The v2 boundary. Provider JSON never becomes trusted domain state directly."""

import hashlib
import json
import math
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def bounded_text(value, maximum, required=False):
    if not isinstance(value, str) or len(value.encode("utf-16-le")) // 2 > maximum:
        raise ValueError("INVALID_TEXT_LENGTH")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError("INVALID_TEXT_CONTROL")
    if required and not value.strip():
        raise ValueError("EMPTY_TEXT")
    return value.strip()


class Destination(Strict):
    name: str
    traits: str

    @field_validator("name")
    @classmethod
    def name_length(cls, value):
        return bounded_text(value, 60, True)

    @field_validator("traits")
    @classmethod
    def traits_length(cls, value):
        return bounded_text(value, 240)


class Route(Strict):
    points: list[list[float | int]] = Field(min_length=2, max_length=512)

    @field_validator("points")
    @classmethod
    def normalized_polyline(cls, value):
        for p in value:
            if len(p) != 2 or any(
                isinstance(n, bool) or not math.isfinite(n) or not 0 <= n <= 1 for n in p
            ):
                raise ValueError("INVALID_ROUTE_POINT")
        if sum(math.dist(a, b) for a, b in zip(value, value[1:], strict=False)) <= 0.0001:
            raise ValueError("EMPTY_ROUTE")
        return value


class GenerationInput(Strict):
    requestId: str
    destination: Destination
    purpose: str
    route: Route

    @field_validator("requestId")
    @classmethod
    def uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("NON_CANONICAL_UUID")
        return value

    @field_validator("purpose")
    @classmethod
    def purpose_length(cls, value):
        return bounded_text(value, 120)


class SpeechInput(Strict):
    requestId: str
    text: str

    _uuid = field_validator("requestId")(GenerationInput.uuid.__func__)

    @field_validator("text")
    @classmethod
    def text_length(cls, value):
        return bounded_text(value, 500, True)


class InitialTexts(Strict):
    greeting: str = Field(min_length=1, max_length=200)
    common: str = Field(min_length=1, max_length=200)
    arrival: str = Field(min_length=1, max_length=200)

    @field_validator("greeting", "common", "arrival")
    @classmethod
    def normalized_text(cls, value):
        return bounded_text(value, 200, True)

    @model_validator(mode="after")
    def categories_have_distinct_text(self):
        if len({self.greeting, self.common, self.arrival}) != 3:
            raise ValueError("INITIAL_SPEECH_TEXTS_MUST_BE_DISTINCT")
        return self


class Concept(Strict):
    displayName: str = Field(min_length=1, max_length=60)
    personality: str = Field(min_length=1, max_length=500)
    imagePrompt: str = Field(min_length=20, max_length=4000)
    voiceDescription: str = Field(min_length=20, max_length=1000)
    previewText: str = Field(min_length=100, max_length=1000)
    texts: InitialTexts


Mode = Literal["OFFLINE_FIXTURE", "API", "DISABLED"]
State = Literal["QUEUED", "RUNNING", "READY", "FAILED", "RESULT_UNKNOWN"]
Stage = Literal["PLANNING", "MEDIA", "SELECTING", "SPEECH", "VALIDATING", "COMPLETE"]


class JobView(Strict):
    jobId: str
    requestId: str
    state: State
    stage: Stage
    mode: Mode
    error: str | None = None
    artifact: dict | None = None
    speechManifest: dict | None = None
    cost: dict | None = None


Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Asset(Strict):
    sha256: Sha
    path: str
    mimeType: Literal["image/png"]
    byteLength: int = Field(ge=1, le=8388608)
    width: int = Field(ge=64, le=2048)
    height: int = Field(ge=64, le=2048)


class Visual(Strict):
    version: Literal["generated-rgba-1"]
    asset: Asset
    route: list[list[float | int]]


class VoiceBinding(Strict):
    description: str
    bindingId: str
    profileId: str


class DesignedVoiceSource(Strict):
    kind: Literal["designed-voice-v1"]
    providerId: Literal["elevenlabs-designed", "gemini-designed", "nunti-offline-fixture"]
    designModel: str
    synthesisModel: str
    voiceId: str
    bindingId: str
    specSha256: Sha
    settingsSha256: Sha
    mediaOrigin: Literal["PROVIDER_GENERATED", "OFFLINE_FIXTURE"]

    @model_validator(mode="after")
    def origin_matches_provider(self):
        if (self.providerId == "nunti-offline-fixture") != (self.mediaOrigin == "OFFLINE_FIXTURE"):
            raise ValueError("MEDIA_ORIGIN_MISMATCH")
        return self


class VoiceClip(Strict):
    clipId: str
    characterId: str
    profileId: str
    speakerId: str
    locale: Literal["ko-KR"]
    text: str
    textSha256: Sha
    audioPath: str
    audioSha256: Sha
    sampleRateHz: Literal[24000]
    channels: Literal[1]
    sampleWidthBytes: Literal[2]
    durationMs: int = Field(ge=1, le=30000)
    source: DesignedVoiceSource
    rawAudioSha256: Sha | None = None
    fixtureProvenance: dict | None = None

    @model_validator(mode="after")
    def voice_and_text_match(self):
        if self.speakerId != self.source.voiceId or sha(self.text.encode()) != self.textSha256:
            raise ValueError("VOICE_CLIP_IDENTITY_MISMATCH")
        return self


class VoiceManifest3(Strict):
    schemaVersion: Literal[3]
    providerId: str
    characters: list[dict]
    scope: str
    clips: list[VoiceClip] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def source_matches_provider(self):
        if any(c.source.providerId != self.providerId for c in self.clips):
            raise ValueError("PROVIDER_SOURCE_MISMATCH")
        if len({(c.characterId, c.textSha256) for c in self.clips}) != len(self.clips):
            raise ValueError("AMBIGUOUS_CLIP")
        return self


class CharacterArtifact(Strict):
    schemaVersion: Literal[2]
    characterId: str
    journeyId: str
    inputSha256: Sha
    inputCanonical: str
    specHash: Sha
    displayName: str
    destinationName: str
    purpose: str
    mode: Mode
    visual: Visual
    voice: VoiceBinding
    voiceManifest: VoiceManifest3
    fixtureProvenance: dict | None = None

    @model_validator(mode="after")
    def joined_identity(self):
        if sha(self.inputCanonical.encode()) != self.inputSha256:
            raise ValueError("INPUT_DIGEST_MISMATCH")
        if self.visual.asset.path != "/v2/assets/" + self.visual.asset.sha256:
            raise ValueError("IMAGE_PATH_MISMATCH")
        for clip in self.voiceManifest.clips:
            if (
                clip.characterId,
                clip.profileId,
                clip.source.bindingId,
                clip.source.specSha256,
            ) != (self.characterId, self.voice.profileId, self.voice.bindingId, self.specHash):
                raise ValueError("CHARACTER_VOICE_JOIN_MISMATCH")
        return self
