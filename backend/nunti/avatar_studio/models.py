"""Validate user input at the v3 HTTP boundary."""

import hashlib
import json
import math
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .variant_spec import VariantContext


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(data):
    return hashlib.sha256(data).hexdigest()


def uuid_text(value):
    if str(UUID(value)) != value:
        raise ValueError("NON_CANONICAL_UUID")
    return value


def text(value, maximum, required=False):
    if len(value.encode("utf-16-le")) // 2 > maximum or any(
        ord(c) < 32 and c not in "\n\t" for c in value
    ):
        raise ValueError("INVALID_TEXT")
    value = value.strip()
    if required and not value:
        raise ValueError("EMPTY_TEXT")
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Destination(Strict):
    name: str
    traits: str = ""

    @field_validator("name")
    @classmethod
    def name_text(cls, value):
        return text(value, 60, True)

    @field_validator("traits")
    @classmethod
    def traits_text(cls, value):
        return text(value, 240)


class Route(Strict):
    points: list[list[float | int]] = Field(min_length=2, max_length=512)
    inputOrigin: Literal["TEST_ROUTE", "NAVIGATION_SCREENSHOT", "ROUTE_FILE", "API_ROUTE"]
    sourceLabel: str
    confirmed: Literal[True]
    extractionId: str | None = None
    apiPlanId: str | None = None

    @field_validator("points")
    @classmethod
    def polyline(cls, points):
        for point in points:
            if len(point) != 2 or any(
                isinstance(n, bool) or not math.isfinite(n) or not 0 <= n <= 1 for n in point
            ):
                raise ValueError("INVALID_ROUTE_POINT")
        if sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False)) <= 0.0001:
            raise ValueError("EMPTY_ROUTE")
        return points

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("ROUTE_CONFIRMATION_REQUIRED")
        return value

    @field_validator("sourceLabel")
    @classmethod
    def source_label(cls, value):
        return text(value, 180, True)

    @field_validator("extractionId")
    @classmethod
    def extraction_uuid(cls, value):
        return uuid_text(value) if value is not None else None

    @model_validator(mode="after")
    def screenshot_has_source(self):
        if (self.inputOrigin == "NAVIGATION_SCREENSHOT") != (self.extractionId is not None):
            raise ValueError("SCREENSHOT_SOURCE_REQUIRED")
        if (self.inputOrigin == "API_ROUTE") != (self.apiPlanId is not None):
            raise ValueError("API_ROUTE_SOURCE_REQUIRED")
        if self.apiPlanId is not None and (
            len(self.apiPlanId) != 64 or any(c not in "0123456789abcdef" for c in self.apiPlanId)
        ):
            raise ValueError("INVALID_API_PLAN_ID")
        return self


class GeographicPoint(Strict):
    latitude: float | int
    longitude: float | int
    name: str = ""

    @field_validator("latitude", "longitude")
    @classmethod
    def finite_coordinate(cls, value):
        if isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("INVALID_GEOGRAPHIC_POINT")
        return value

    @field_validator("name")
    @classmethod
    def label(cls, value):
        return text(value, 60)

    @model_validator(mode="after")
    def supported_projection(self):
        if not -85 <= self.latitude <= 85 or not -180 <= self.longitude <= 180:
            raise ValueError("INVALID_GEOGRAPHIC_POINT")
        return self


class RoutePlanInput(Strict):
    origin: GeographicPoint
    destination: GeographicPoint
    nativeSnapshot: dict | None = None

    @model_validator(mode="after")
    def bounded_snapshot_and_destination(self):
        if not self.destination.name:
            raise ValueError("DESTINATION_NAME_REQUIRED")
        if len(canonical(self.nativeSnapshot).encode()) > 65_536:
            raise ValueError("NATIVE_SNAPSHOT_TOO_LARGE")
        return self


class AvatarInput(Strict):
    requestId: str
    destination: Destination
    purpose: str = ""
    route: Route | None = None
    renderMode: Literal["LOCAL_RENDER", "IMAGE_API", "LOCAL_MODEL", "LOCAL_LAYERS"] = "LOCAL_RENDER"
    variantContext: VariantContext | None = None

    _uuid = field_validator("requestId")(uuid_text)

    @field_validator("purpose")
    @classmethod
    def purpose_text(cls, value):
        return text(value, 120)

    @model_validator(mode="after")
    def layered_context_is_opt_in(self):
        if self.renderMode != "LOCAL_LAYERS":
            if self.route is None:
                raise ValueError("ROUTE_REQUIRED")
            if self.variantContext is not None:
                raise ValueError("VARIANT_CONTEXT_REQUIRES_LOCAL_LAYERS")
        return self


class ExtractionInput(Strict):
    imageBase64: str = Field(min_length=24, max_length=11_184_812)
    colorHint: Literal["blue", "cyan", "purple", "green", "red", "orange"] | None = None


class SessionInput(Strict):
    token: str = Field(min_length=32, max_length=256)
