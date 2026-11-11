"""Wire models for the proposed v1 contract; checked JSON Schema is published separately."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
]
Token = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Ratio = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Revision = Annotated[int, Field(ge=1, le=2147483647)]


def valid_timestamp(value: str) -> str:
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


Timestamp = Annotated[
    str,
    Field(
        max_length=40,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$",
        json_schema_extra={"format": "date-time"},
    ),
    AfterValidator(valid_timestamp),
]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Contract(WireModel):
    schemaVersion: Literal["1.0"]


class Source(WireModel):
    kind: Literal["MOCK", "ANDROID_ADAPTER", "EXTERNAL_MODULE", "USER_INPUT"]
    provider: Token
    version: Token | None = None


class Evidence(WireModel):
    source: Source
    verificationStatus: Literal["VERIFIED", "UNVERIFIED", "UNAVAILABLE"]
    confidence: Ratio | None
    validity: Literal["VALID", "STALE", "UNKNOWN"]
    observedAt: Timestamp
    validUntil: Timestamp | None = None

    @model_validator(mode="after")
    def time_order(self):
        if self.validUntil and instant(self.validUntil) < instant(self.observedAt):
            raise ValueError("validUntil must not precede observedAt")
        return self


class RoadTypeRatios(WireModel):
    highway: Ratio = 0.0
    urban: Ratio = 0.0
    rural: Ratio = 0.0
    unknown: Ratio = 0.0

    @model_validator(mode="after")
    def bounded_total(self):
        if sum((self.highway, self.urban, self.rural, self.unknown)) > 1.000001:
            raise ValueError("road type ratios must sum to at most one")
        return self


class RouteSnapshot(Contract):
    routeId: Identifier
    routeRevision: Revision
    collectedAt: Timestamp
    source: Source
    routeOption: Token | None = None
    distanceMeters: Annotated[float, Field(ge=0, le=100_000_000)] | None = None
    estimatedDurationSeconds: Annotated[int, Field(ge=0, le=31_536_000)] | None = None
    roadTypeRatios: RoadTypeRatios | None = None
    regionTags: Annotated[list[Token], Field(max_length=30)] = []
    scenicTags: Annotated[list[Token], Field(max_length=30)] = []
    featureEvidence: Annotated[dict[Token, Evidence], Field(max_length=64)] = {}


class AvatarSpec(Contract):
    avatarId: Identifier
    baseCharacterId: Identifier
    routeId: Identifier
    routeRevision: Revision
    generationSeed: Annotated[str, Field(min_length=1, max_length=128)]
    ruleVersion: Token
    assetVersion: Token
    paletteId: Identifier
    outfitId: Identifier
    accessoryIds: Annotated[list[Identifier], Field(max_length=30)]
    themeId: Identifier
    voiceProfileId: Identifier
    generationExplanation: Text


class DrivingEvent(Contract):
    eventId: Identifier
    tripId: Identifier
    eventType: Token
    occurredAt: Timestamp
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    confidence: Ratio | None
    verificationStatus: Literal["VERIFIED", "UNVERIFIED", "UNAVAILABLE"]
    source: Source
    correlationId: Identifier | None = None
    recoveryOfEventId: Identifier | None = None

    @model_validator(mode="after")
    def not_self_recovery(self):
        if self.eventId == self.recoveryOfEventId:
            raise ValueError("event must not recover itself")
        return self


class EmotionSnapshot(Contract):
    # Proposed extension: a durable id is needed to deduplicate offline retries.
    emotionId: Identifier
    tripId: Identifier
    avatarId: Identifier
    emotion: Token
    intensity: Ratio
    triggeredByEventId: Identifier | None
    occurredAt: Timestamp
    confidence: Ratio | None


class VoiceProfile(Contract):
    voiceProfileId: Identifier
    locale: Annotated[str, Field(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")]
    persona: Token
    speakingStyle: Token
    preferredVoiceId: Identifier | None
    supportedControls: Annotated[list[Token], Field(max_length=20)]


class SpeechRequest(Contract):
    requestId: Identifier
    tripId: Identifier
    avatarId: Identifier
    text: Text
    voiceProfileId: Identifier
    emotion: Token
    tripPhase: Literal["PRE_TRIP", "DRIVING", "STOPPED", "POST_TRIP"]
    priority: Literal["LOW", "NORMAL", "HIGH"]
    requestedAt: Timestamp
    expiresAt: Timestamp
    contentSource: Literal["MOCK", "TEMPLATE", "EXTERNAL_REPORT"]
    speechPurpose: (
        Literal[
            "PRE_DRIVE_GREETING", "VERIFIED_EVENT_RESPONSE", "USER_INITIATED", "POST_DRIVE_REPORT"
        ]
        | None
    ) = None
    sourceEventId: Identifier | None = None
    emotionId: Identifier | None = None

    @model_validator(mode="after")
    def expiry_order(self):
        if instant(self.expiresAt) <= instant(self.requestedAt):
            raise ValueError("expiresAt must be after requestedAt")
        return self


class DataCoverage(WireModel):
    status: Literal["SUFFICIENT", "PARTIAL", "INSUFFICIENT", "UNAVAILABLE"]
    evaluatedSeconds: Annotated[float, Field(ge=0, le=31_536_000)]
    totalSeconds: Annotated[float, Field(ge=0, le=31_536_000)]
    ratio: Ratio | None
    # The external producer defines sufficiency and evaluation rules.
    unavailableSignals: Annotated[list[Token], Field(max_length=100)] = []

    @model_validator(mode="after")
    def bounded_duration(self):
        if self.evaluatedSeconds > self.totalSeconds:
            raise ValueError("evaluatedSeconds must not exceed totalSeconds")
        return self


class TripReport(Contract):
    tripId: Identifier
    overallScore: Annotated[float, Field(ge=0, le=100)] | None
    dataCoverage: DataCoverage
    finalText: Text
    evidenceEventIds: Annotated[list[Identifier], Field(max_length=500)]
    generatedAt: Timestamp


Score = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
OffsetMs = Annotated[int, Field(ge=0, le=31_536_000_000)]


class SeatSample(WireModel):
    """null means the signal was not received. It is neither "empty" nor "unbuckled"."""

    occupied: bool | None = None
    buckled: bool | None = None


class TelemetrySample(WireModel):
    """One vehicle sample as the Android app read it (about once per second).

    Every signal is nullable: null = not received, which is different from a normal or zero value.
    tMs is the app's session clock (what its score engine used); occurredAt is the wall clock.
    """

    sampleId: Identifier
    tMs: OffsetMs
    occurredAt: Timestamp
    speedKmh: Annotated[float, Field(ge=0, le=400, allow_inf_nan=False)] | None = None
    brakePressed: bool | None = None
    gear: Literal["P", "R", "N", "D"] | None = None
    turnSignal: Literal["NONE", "LEFT", "RIGHT"] | None = None
    driverSeat: SeatSample | None = None
    passengerSeat: SeatSample | None = None
    doorOpen: bool | None = None
    headlightOn: bool | None = None
    isNight: bool | None = None
    leadDistanceM: Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False)] | None = None
    speedLimitKmh: Annotated[int, Field(ge=0, le=300)] | None = None
    roadType: Literal["HIGHWAY", "GENERAL"] = "GENERAL"
    # Steering wheel angle in degrees (+ right / - left); input to the app's curve-speed score.
    steeringDeg: Annotated[float, Field(ge=-1080, le=1080, allow_inf_nan=False)] | None = None
    # Optional in requests: the server fills it from the batch so demo (MOCK) data stays
    # distinguishable from real vehicle data after storage.
    source: Source | None = None


class SampleBatch(Contract):
    tripId: Identifier
    source: Source
    samples: Annotated[list[TelemetrySample], Field(min_length=1, max_length=100)]


class ScoreAreaResult(WireModel):
    area: Token
    score: Score | None
    points: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None


class ScoreItemResult(WireModel):
    item: Token
    score: Score | None
    basis: Annotated[str, Field(max_length=64)]


class ScoreEventRecord(WireModel):
    tMs: OffsetMs
    kind: Token


class ScoreSnapshot(WireModel):
    """One result of the app's score engine. The app computes; the server only stores it.

    score/points are null when the area or item could not be evaluated (not enough signals).
    newEvents holds only the events found since the previous snapshot, so snapshots do not grow.
    engineVersion names the rule set that produced the numbers; thresholds are still drafts.
    """

    scoreId: Identifier
    computedAt: Timestamp
    tMs: OffsetMs
    sampleCount: Annotated[int, Field(ge=0, le=100_000_000)]
    total: Score | None
    coverage: Ratio
    final: bool
    engineVersion: Token
    areas: Annotated[list[ScoreAreaResult], Field(max_length=16)]
    items: Annotated[list[ScoreItemResult], Field(max_length=32)]
    windowOverall: Annotated[list[Score | None], Field(max_length=1500)]
    newEvents: Annotated[list[ScoreEventRecord], Field(max_length=100)] = []
    source: Source | None = None  # filled from the batch when omitted


class ScoreBatch(Contract):
    tripId: Identifier
    source: Source
    scores: Annotated[list[ScoreSnapshot], Field(min_length=1, max_length=100)]


class TripCreate(Contract):
    tripId: Identifier
    startedAt: Timestamp
    syncConsent: Literal[True]

    @field_validator("syncConsent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("syncConsent must be explicitly true")
        return value


class EventBatch(Contract):
    events: Annotated[list[DrivingEvent], Field(min_length=1, max_length=100)]


class EmotionBatch(Contract):
    emotions: Annotated[list[EmotionSnapshot], Field(min_length=1, max_length=100)]


class Receipt(WireModel):
    id: str
    status: Literal["stored", "duplicate"]
    receivedAt: Timestamp


class StoredRoute(WireModel):
    value: RouteSnapshot
    receivedAt: Timestamp


class StoredAvatar(WireModel):
    value: AvatarSpec
    receivedAt: Timestamp


class StoredEvent(WireModel):
    value: DrivingEvent
    receivedAt: Timestamp


class StoredEmotion(WireModel):
    value: EmotionSnapshot
    receivedAt: Timestamp


class StoredSample(WireModel):
    value: TelemetrySample
    receivedAt: Timestamp


class StoredScore(WireModel):
    value: ScoreSnapshot
    receivedAt: Timestamp


class StoredReport(WireModel):
    value: TripReport
    receivedAt: Timestamp
    unresolvedEvidenceEventIds: list[str]


class TripView(WireModel):
    trip: TripCreate
    createdAt: Timestamp
    expiresAt: Timestamp
    route: StoredRoute | None
    avatar: StoredAvatar | None
    eventCount: int
    emotionCount: int
    reportAvailable: bool
    sampleCount: int = 0
    scoreCount: int = 0


class Capabilities(WireModel):
    apiVersion: Literal["v1"] = "v1"
    schemaVersions: list[str] = ["1.0"]
    contractStatus: Literal["DRAFT"] = "DRAFT"
    syncEnabled: bool
    mockEnabled: bool
    maxBatchSize: int = 100
    retentionDays: int
    localRealtimeRequired: bool = True


class Page[T](WireModel):
    items: list[T]
    nextOffset: int | None


class Meta(WireModel):
    requestId: str
    serverTime: str


class Envelope[T](WireModel):
    data: T
    meta: Meta


class ErrorDetail(WireModel):
    field: str
    type: str


class Error(WireModel):
    code: str
    message: str
    details: list[ErrorDetail] = []


class ErrorEnvelope(WireModel):
    error: Error
    meta: Meta


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


CONTRACTS = (
    RouteSnapshot,
    AvatarSpec,
    DrivingEvent,
    EmotionSnapshot,
    VoiceProfile,
    SpeechRequest,
    TripReport,
    TripCreate,
    EventBatch,
    EmotionBatch,
    SampleBatch,
    ScoreBatch,
)
