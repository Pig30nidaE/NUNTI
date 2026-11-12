"""Loopback-only v3 avatar studio. Start with nunti.avatar_studio.api:app on port 8768."""

import base64
import hmac
import io
import ipaddress
import json
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError

from .conversation import DEFAULT_MODEL, ConversationInput, generate_reply
from .models import (
    AvatarInput,
    ExtractionInput,
    Route,
    RoutePlanInput,
    SessionInput,
    canonical,
    digest,
)
from .storage import StudioError, StudioStore
from .voice_render import voice_available
from .wardrobe import WardrobeInput

ROOT = Path(__file__).resolve().parents[3]
COOKIE = "nunti_studio_session"
MAX_BYTES = 8_388_608
MAX_BODY = 11_200_000


@dataclass
class Settings:
    token: str = field(repr=False)
    workspace: Path
    web_root: Path = ROOT / "prototypes/avatar_generator"
    port: int = 8768
    image_enabled: bool = False
    paid_api_approved: bool = False
    image_key: str = field(default="", repr=False)
    image_model: str = "gpt-image-2.5-flare"
    image_prices_verified: bool = False
    image_reservation_micros: int = 0
    image_job_cap_micros: int = 300_000
    image_total_cap_micros: int = 6_000_000
    image_request_limit: int = 20
    style_asset_dir: Path = ROOT / "docs/design/avatar-v6/assets"
    style_reference: Path | None = None
    local_model_enabled: bool = False
    local_model_binary: Path | None = None
    local_model_weights: Path | None = None
    local_model_timeout: int = 150
    route_api_enabled: bool = False
    wardrobe_enabled: bool = False
    chat_enabled: bool = False
    chat_key: str = field(default="", repr=False)
    chat_model: str = DEFAULT_MODEL

    @property
    def wardrobe_available(self):
        return self.paid_api_approved and self.wardrobe_enabled and bool(self.image_key)

    @property
    def chat_available(self):
        return self.chat_enabled and bool(self.chat_key)

    def __post_init__(self):
        if not 32 <= len(self.token) <= 256 or not all(33 <= ord(c) <= 126 for c in self.token):
            raise ValueError("NUNTI_STUDIO_TOKEN_REQUIRED")
        self.workspace = Path(self.workspace)
        self.web_root = Path(self.web_root)
        self.style_asset_dir = Path(self.style_asset_dir).resolve()
        if self.style_reference is not None:
            self.style_reference = Path(self.style_reference).resolve()
            if not self.style_reference.is_relative_to(self.style_asset_dir):
                raise ValueError("STYLE_REFERENCE_OUTSIDE_ASSET_DIR")
        if not 1024 <= self.port <= 65535:
            raise ValueError("INVALID_STUDIO_PORT")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", self.image_model):
            raise ValueError("INVALID_IMAGE_MODEL")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", self.chat_model):
            raise ValueError("INVALID_CHAT_MODEL")
        for name in ("local_model_binary", "local_model_weights"):
            configured = getattr(self, name)
            if configured is not None:
                configured = Path(configured).resolve()
                if not configured.is_relative_to(ROOT):
                    raise ValueError("LOCAL_MODEL_OUTSIDE_WORKSPACE")
                setattr(self, name, configured)
        if not 10 <= self.local_model_timeout <= 300:
            raise ValueError("INVALID_LOCAL_MODEL_TIMEOUT")
        if (
            not 0 < self.image_job_cap_micros <= 300_000
            or not 0 < self.image_total_cap_micros <= 100_000_000
            or not 1 <= self.image_request_limit <= 100
        ):
            raise ValueError("INVALID_IMAGE_BUDGET")

    @property
    def owner(self):
        return digest(self.token.encode())

    @property
    def session_cookie(self):
        return hmac.new(self.token.encode(), b"nunti-studio-session-v1", "sha256").hexdigest()

    @property
    def image_available(self):
        return (
            self.paid_api_approved
            and self.image_enabled
            and bool(self.image_key)
            and self.image_prices_verified
            and 0 < self.image_reservation_micros <= self.image_job_cap_micros
        )

    @property
    def local_model_available(self):
        from .local_model import local_model_available

        return local_model_available(self)

    @classmethod
    def from_env(cls):
        approved = os.getenv("NUNTI_STUDIO_PAID_API_APPROVED") == "true"
        enabled = os.getenv("NUNTI_STUDIO_IMAGE_API_ENABLED") == "true"
        style_reference = os.getenv("NUNTI_STUDIO_STYLE_REFERENCE")
        local_binary = os.getenv("NUNTI_STUDIO_LOCAL_MODEL_BINARY")
        local_weights = os.getenv("NUNTI_STUDIO_LOCAL_MODEL_WEIGHTS")
        chat_enabled = os.getenv("NUNTI_STUDIO_CHAT_API_ENABLED") == "true"
        return cls(
            token=os.getenv("NUNTI_STUDIO_TOKEN", ""),
            workspace=Path(os.getenv("NUNTI_STUDIO_WORKSPACE", ROOT / ".local/avatar-generator")),
            port=int(os.getenv("NUNTI_STUDIO_PORT", "8768")),
            image_enabled=enabled,
            paid_api_approved=approved,
            image_key=os.getenv("OPENAI_API_KEY", "") if approved else "",
            wardrobe_enabled=os.getenv("NUNTI_STUDIO_WARDROBE_ENABLED") == "true",
            chat_enabled=chat_enabled,
            chat_key=(os.getenv("NUNTI_STUDIO_CHAT_API_KEY") or os.getenv("OPENAI_API_KEY", "")) if chat_enabled else "",
            chat_model=os.getenv("NUNTI_STUDIO_CHAT_MODEL", DEFAULT_MODEL),
            image_model=os.getenv("NUNTI_STUDIO_IMAGE_MODEL", "gpt-image-2.5-flare"),
            image_prices_verified=os.getenv("NUNTI_STUDIO_IMAGE_PRICES_VERIFIED") == "true",
            image_reservation_micros=int(os.getenv("NUNTI_STUDIO_IMAGE_RESERVATION_MICROS", "0")),
            image_job_cap_micros=int(os.getenv("NUNTI_STUDIO_IMAGE_JOB_CAP_MICROS", "300000")),
            image_total_cap_micros=int(os.getenv("NUNTI_STUDIO_IMAGE_TOTAL_CAP_MICROS", "6000000")),
            image_request_limit=int(os.getenv("NUNTI_STUDIO_IMAGE_REQUEST_LIMIT", "20")),
            style_reference=(
                Path(style_reference)
                if style_reference
                else ROOT / "docs/design/avatar-v6/assets/style-face-technique.png"
            ),
            local_model_enabled=os.getenv("NUNTI_STUDIO_LOCAL_MODEL_ENABLED") == "true",
            local_model_binary=Path(local_binary) if local_binary else None,
            local_model_weights=Path(local_weights) if local_weights else None,
            local_model_timeout=int(os.getenv("NUNTI_STUDIO_LOCAL_MODEL_TIMEOUT_SECONDS", "150")),
            route_api_enabled=os.getenv("NUNTI_STUDIO_ROUTE_API_ENABLED") == "true",
        )


def image_info(content, require_rgba=False):
    if not content or len(content) > MAX_BYTES:
        raise StudioError("INVALID_IMAGE_SIZE", 413)
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG"} or getattr(image, "n_frames", 1) != 1:
                raise StudioError("UNSUPPORTED_IMAGE_FORMAT")
            width, height = image.size
            if min(width, height) < 32 or max(width, height) > 4096 or width * height > 8_388_608:
                raise StudioError("INVALID_IMAGE_DIMENSIONS")
            image.load()
            if require_rgba:
                if image.format != "PNG" or image.mode != "RGBA":
                    raise StudioError("RENDERED_RGBA_REQUIRED", 502)
                low, high = image.getchannel("A").getextrema()
                if low == 255 or high == 0:
                    raise StudioError("RENDERED_ALPHA_REQUIRED", 502)
            if not require_rgba:
                width, height = ImageOps.exif_transpose(image).size
            return {
                "width": width,
                "height": height,
                "mime": "image/png" if image.format == "PNG" else "image/jpeg",
            }
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        if isinstance(exc, StudioError):
            raise
        raise StudioError("INVALID_IMAGE") from exc


def validate_design(design):
    """Renderer output crosses the media boundary before an artifact can become ready."""
    required = {"displayName", "personality", "palette", "motifs", "voice"}
    if not isinstance(design, dict) or not required.issubset(design):
        raise StudioError("INVALID_RENDER_DESIGN", 502)
    if not isinstance(design["displayName"], str) or not 1 <= len(design["displayName"]) <= 60:
        raise StudioError("INVALID_RENDER_DESIGN", 502)
    if not isinstance(design["personality"], str) or not design["personality"]:
        raise StudioError("INVALID_RENDER_DESIGN", 502)
    motifs = design["motifs"]
    if (
        not isinstance(motifs, list)
        or not 1 <= len(motifs) <= 16
        or any(
            not isinstance(m, dict)
            or any(
                not isinstance(m.get(k), str) or not m[k]
                for k in ("label", "source", "target", "detail")
            )
            for m in motifs
        )
    ):
        raise StudioError("INVALID_RENDER_MOTIFS", 502)
    voice = design["voice"]
    if (
        not isinstance(voice, dict)
        or not isinstance(voice.get("description"), str)
        or not isinstance(voice.get("rate"), (int, float))
        or not isinstance(voice.get("pitch"), (int, float))
        or not 0.5 <= voice["rate"] <= 2
        or not 0.5 <= voice["pitch"] <= 2
    ):
        raise StudioError("INVALID_VOICE_RECIPE", 502)
    return json.loads(canonical(design))


def secure_equal(left, right):
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def create_app(
    settings=None,
    *,
    renderer=None,
    extractor=None,
    api_renderer=None,
    local_renderer=None,
    route_fetcher=None,
    layered_renderer=None,
    conversation_generator=None,
):
    @asynccontextmanager
    async def lifespan(application):
        config = settings or Settings.from_env()
        application.state.config = config
        application.state.store = StudioStore(config.workspace)
        yield

    application = FastAPI(
        title="Nunti avatar generator v3",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def error_response(code, status):
        return JSONResponse({"data": None, "error": {"code": code}}, status_code=status)

    @application.exception_handler(StudioError)
    async def studio_error(request, error):
        return error_response(error.code, error.status)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Never echo request contents (including session credentials or navigation screenshots).
        return error_response("INVALID_REQUEST", 422)

    @application.middleware("http")
    async def local_boundary(request, call_next):
        config = request.app.state.config
        host = request.headers.get("host", "")
        allowed_hosts = {f"127.0.0.1:{config.port}", f"localhost:{config.port}"}
        try:
            local = ipaddress.ip_address(request.client.host).is_loopback
        except ValueError:
            local = False
        if not local or host not in allowed_hosts:
            return error_response("LOOPBACK_ONLY", 403)
        origin = request.headers.get("origin")
        if origin is not None and origin != "http://" + host:
            return error_response("CROSS_ORIGIN_DENIED", 403)
        if request.headers.get("sec-fetch-site", "none") not in {"none", "same-origin"}:
            return error_response("CROSS_ORIGIN_DENIED", 403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return error_response("JSON_REQUIRED", 415)
            if (
                COOKIE in request.cookies
                and origin is None
                and not request.headers.get("authorization")
            ):
                return error_response("SAME_ORIGIN_REQUIRED", 403)
            # Enforce the streamed body bound as well as Content-Length.
            body = bytearray()
            async for part in request.stream():
                body.extend(part)
                if len(body) > MAX_BODY:
                    return error_response("REQUEST_TOO_LARGE", 413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    def owner(request: Request):
        config = request.app.state.config
        authorization = request.headers.get("authorization")
        if authorization is not None:
            if not authorization.startswith("Bearer ") or not secure_equal(
                authorization[7:], config.token
            ):
                raise StudioError("AUTHENTICATION_REQUIRED", 401)
        elif not secure_equal(request.cookies.get(COOKIE, ""), config.session_cookie):
            raise StudioError("AUTHENTICATION_REQUIRED", 401)
        return config.owner

    Owner = Annotated[str, Depends(owner)]

    @application.post("/session")
    def session(value: SessionInput, request: Request):
        config = request.app.state.config
        if not secure_equal(value.token, config.token):
            raise StudioError("AUTHENTICATION_REQUIRED", 401)
        response = JSONResponse({"data": {"authenticated": True}})
        response.set_cookie(
            COOKIE,
            config.session_cookie,
            httponly=True,
            samesite="strict",
            path="/",
            max_age=8 * 3600,
            secure=False,
        )
        return response

    @application.get("/v3/capabilities")
    def capabilities(request: Request, principal: Owner):
        from .image_api import PROMPT_VERSION

        config = request.app.state.config
        return {
            "data": {
                "schemaVersion": 3,
                "wardrobeAvailable": config.wardrobe_available,
                "conversationAvailable": config.chat_available,
                "mode": "LOCAL_RENDER",
                "layeredRenderAvailable": True,
                "layeredRenderInfo": {
                    "renderMode": "LOCAL_LAYERS",
                    "mappingVersion": "nunti-layers-v1",
                    "assetVersion": "nunti-a-layers-v1",
                    "offline": True,
                    "paidApiCalls": 0,
                    "requiresExplicitMood": True,
                    "missingRouteBehavior": "STATIC_BASE",
                    "motion": "none",
                },
                "inputOrigins": ["TEST_ROUTE", "NAVIGATION_SCREENSHOT", "ROUTE_FILE", "API_ROUTE"],
                "routeApiAvailable": config.route_api_enabled,
                "routeApiInfo": {
                    "provider": "OSRM_FOSSGIS",
                    "mode": "EXTERNAL_DEVELOPMENT_ROUTING",
                    "geometryOrigin": "OSRM_ROUTE_SERVICE",
                    "apiKeyRequired": False,
                    "paidApiCalls": 0,
                    "geometryMatchesHyundaiRoute": False,
                    "rawCoordinateSystem": "WGS84",
                    "rawCoordinateOrder": "LONGITUDE_LATITUDE",
                    "requiresUserConfirmation": True,
                    "requestLimit": 12,
                    "minimumIntervalSeconds": 1.1,
                    "notice": (
                        "OSRM / OpenStreetMap에서 자동차 경로를 조회하는 개발 시험입니다. "
                        "현대 내비가 선택한 경로와의 일치는 검증되지 않았습니다. "
                        "입력한 출발지·목적지 위경도가 외부 공개 서버에 전송됩니다."
                    ),
                },
                "imageApiAvailable": bool(config.image_available),
                "localImageModelAvailable": config.local_model_available,
                "localImageModelInfo": {
                    "engine": "mflux-mlx",
                    "model": "mlx-community/FLUX.2-Klein-4B-4bit",
                    "offline": True,
                    "observedSeconds": 45,
                    "observedRangeSeconds": [42.25, 48.63],
                    "paidApiCalls": 0,
                    "newImagesGenerated": True,
                    "routeCorrespondenceVerified": False,
                    "humanQualityApproved": False,
                    "notice": (
                        "무료 로컬 AI 시험입니다. 생성에 약 1분 걸립니다. "
                        "경로·모티브와 미적 품질은 미검증입니다."
                    ),
                },
                "imageApiPaidApprovalRequired": not config.paid_api_approved,
                "imageApiPaidApproved": config.paid_api_approved,
                "imageApiPromptVersion": PROMPT_VERSION,
                "imageApiRenderingStyle": "MATTE_ILLUSTRATED_2_5D",
                "imageApiStyleReferenceConfigured": config.style_reference is not None,
                "imageApiModel": config.image_model,
                "imageApiBudget": {
                    "reservationMicros": config.image_reservation_micros,
                    "perRequestCapMicros": config.image_job_cap_micros,
                    "totalCapMicros": config.image_total_cap_micros,
                    "requestLimit": config.image_request_limit,
                    "actualCostVerified": False,
                },
                "voice": {
                    "mode": "LOCAL_VOICE_DESIGN",
                    "available": voice_available(),
                    "newVoiceGenerated": True,
                    "notice": (
                        "캐릭터의 역할과 성격으로 한국어 목소리를 새로 만들어요. "
                        "첫 듣기는 준비 시간이 필요해요."
                    ),
                    "automaticPlayback": False,
                    "blocksVisualReady": False,
                },
                "habitImprovementEffectVerified": False,
                "localRenderNotice": (
                    "입력과 여정 ID에서 새 RGBA를 그리는 로컬 렌더입니다. AI 생성이 아닙니다."
                ),
            }
        }

    @application.get("/v3/examples")
    def examples(request: Request, principal: Owner):
        folder = request.app.state.config.web_root / "examples"
        values = []
        index = folder / "index.json"
        source = (
            json.loads(index.read_text())
            if index.exists()
            else [json.loads(path.read_text()) for path in sorted(folder.glob("*.json"))]
        )
        for example in source:
            Route.model_validate(example["route"])
            image_name = (
                example.get("imageFile") or example.get("imagePath") or example.get("image")
            )
            if image_name:
                image_path = (folder / Path(image_name).name).resolve()
                if image_path.parent != folder.resolve() or not image_path.is_file():
                    raise StudioError("EXAMPLE_IMAGE_MISSING", 503)
                content = image_path.read_bytes()
                info = image_info(content)
                sha = request.app.state.store.put_asset(principal, content, info["mime"])
                example["imagePath"] = "/v3/assets/" + sha
            values.append(example)
        return {"data": values}

    @application.post("/v3/route-plans")
    def route_plans(value: RoutePlanInput, request: Request, principal: Owner):
        from .route_api import create_plan

        if not request.app.state.config.route_api_enabled:
            raise StudioError("ROUTE_API_NOT_ENABLED", 409)
        return {"data": create_plan(request.app.state.store, principal, value, route_fetcher)}

    @application.get("/v3/route-plans/{plan_id}")
    def route_plan(plan_id: str, request: Request, principal: Owner):
        from .route_api import PlanStore, present_plan

        plan = PlanStore(request.app.state.store).read(principal, plan_id)
        return {"data": present_plan(plan)}

    @application.post("/v3/route-extractions")
    def route_extractions(value: ExtractionInput, request: Request, principal: Owner):
        try:
            content = base64.b64decode(value.imageBase64, validate=True)
        except ValueError as exc:
            raise StudioError("INVALID_IMAGE_BASE64") from exc
        info = image_info(content)
        if extractor is None:
            from .navigation import extract_route

            extract = extract_route
        else:
            extract = extractor
        try:
            extracted = (
                extract(content, color_hint=value.colorHint)
                if value.colorHint
                else extract(content)
            )
            # An extraction is a proposal, never verified GPS or road/safety evidence.
            Route.model_validate(
                {
                    "points": extracted["points"],
                    "inputOrigin": "ROUTE_FILE",
                    "sourceLabel": "extracted screen pixels",
                    "confirmed": True,
                }
            )
        except ValueError as exc:
            code = str(exc)
            raise StudioError(
                code if re.fullmatch(r"[A-Z][A-Z0-9_]{2,80}", code) else "ROUTE_EXTRACTION_FAILED"
            ) from exc
        store = request.app.state.store
        sha = store.put_asset(principal, content, info["mime"])
        result = {
            "extractionId": str(uuid4()),
            "points": extracted["points"],
            "confidence": extracted["confidence"],
            "warnings": extracted["warnings"],
            "imageWidth": info["width"],
            "imageHeight": info["height"],
            "imagePath": "/v3/assets/" + sha,
            "imageSha256": sha,
            "inputOrigin": "NAVIGATION_SCREENSHOT",
            "requiresConfirmation": True,
            "gpsVerified": False,
        }
        store.put_extraction(principal, result)
        return {"data": result}

    @application.post("/v3/avatars")
    def avatars_create(value: AvatarInput, request: Request, principal: Owner):
        config, store = request.app.state.config, request.app.state.store
        data = value.model_dump(exclude_none=True)
        previous = store.previous(principal, data)
        if previous is not None:
            return {"data": store.avatar(principal, previous["characterId"])}
        original = (
            store.extraction(principal, value.route.extractionId)
            if value.route is not None and value.route.extractionId
            else None
        )
        api_plan = None
        if value.route is not None and value.route.inputOrigin == "API_ROUTE":
            from .route_api import validate_route_plan

            api_plan = validate_route_plan(store, principal, value)
        if value.renderMode == "IMAGE_API" and not config.image_available:
            if not config.paid_api_approved:
                raise StudioError("PAID_API_APPROVAL_REQUIRED", 403)
            raise StudioError("IMAGE_API_NOT_CONFIGURED", 409)
        if value.renderMode == "LOCAL_MODEL" and not config.local_model_available:
            raise StudioError("LOCAL_MODEL_NOT_CONFIGURED", 409)
        reserved = config.image_reservation_micros if value.renderMode == "IMAGE_API" else 0
        previous = store.claim(
            principal, data, reserved, config.image_total_cap_micros, config.image_request_limit
        )
        if previous is not None:
            return {"data": store.avatar(principal, previous["characterId"])}
        try:
            if value.renderMode == "LOCAL_LAYERS":
                from .variant_spec import VariantContext

                if layered_renderer is None:
                    from .layered_render import render_layered_avatar

                    layer_render = render_layered_avatar
                else:
                    layer_render = layered_renderer
                png, design = layer_render(value.variantContext or VariantContext(), value.route)
            else:
                if renderer is None:
                    from .illustration import render_avatar

                    render = render_avatar
                else:
                    render = renderer
                png, design = render(
                    value.route.points,
                    value.destination.name,
                    value.destination.traits,
                    value.purpose,
                    value.requestId,
                )
            design = validate_design(design)
            info = image_info(png, True)
            if (info["width"], info["height"]) != (768, 768):
                raise StudioError("LOCAL_RENDER_DIMENSIONS_INVALID", 502)
            provider = None
            local_result = None
            if value.renderMode == "IMAGE_API":
                if api_renderer is None:
                    from .image_api import render_api_image

                    external_render = render_api_image
                else:
                    external_render = api_renderer
                png, provider = external_render(config, data, png, design)
                info = image_info(png, True)
                # The local sketch's coordinates have not been fitted to the provider's final PNG.
                design = {key: item for key, item in design.items() if key != "formation"}
            elif value.renderMode == "LOCAL_MODEL":
                if local_renderer is None:
                    from .local_model import render_local_image

                    model_render = render_local_image
                else:
                    model_render = local_renderer
                local_result = model_render(
                    config,
                    data,
                    design,
                    store.root / "local-model-runs" / principal / value.requestId,
                )
                png, provider = local_result.png, dict(local_result.metadata)
                info = image_info(png, True)
                if (info["width"], info["height"]) != (512, 512):
                    raise StudioError("LOCAL_MODEL_DIMENSIONS_INVALID", 502)
                design = {**design, "formation": local_result.formation}
                raw_sha = store.put_asset(principal, local_result.raw_png, "image/png")
                provider["originalRgb"] = {"path": "/v3/assets/" + raw_sha, "sha256": raw_sha}
                provider["referenceImages"] = []
                for name, content in local_result.references:
                    reference_sha = store.put_asset(principal, content, "image/png")
                    provider["referenceImages"].append(
                        {
                            "name": name,
                            "path": "/v3/assets/" + reference_sha,
                            "sha256": reference_sha,
                        }
                    )
            sha = store.put_asset(principal, png, "image/png")
            from .voice_design import build_voice_design

            voice_plan = build_voice_design(data, design)
            route = value.route.model_dump(exclude_none=True) if value.route is not None else None
            if original:
                route["sourceImagePath"] = original["imagePath"]
                route["sourceImageSha256"] = original["imageSha256"]
                route["extractedPoints"] = original["points"]
                route["extractionWarnings"] = original["warnings"]
                route["userCorrected"] = route["points"] != original["points"]
            if api_plan:
                route["apiRoute"] = {
                    key: item for key, item in api_plan.items() if key != "routePoints"
                }
            artifact = {
                "schemaVersion": 3,
                "characterId": "nunti-" + value.requestId,
                "requestId": value.requestId,
                "inputSha256": digest(canonical(data).encode()),
                "inputCanonical": canonical(data),
                "displayName": design["displayName"],
                "destination": value.destination.model_dump(),
                "purpose": value.purpose,
                "route": route,
                "visual": {
                    "path": "/v3/assets/" + sha,
                    "sha256": sha,
                    "width": info["width"],
                    "height": info["height"],
                },
                "design": design,
                "voice": {
                    "status": "PLANNED",
                    "description": voice_plan["description"],
                    "rate": voice_plan["rate"],
                    "pitch": voice_plan["pitch"],
                    "plan": voice_plan,
                    "provider": "LOCAL_QWEN_VOICE_DESIGN",
                    "newVoiceGenerated": False,
                    "automaticPlayback": False,
                },
                "mediaOrigin": (
                    "LOCAL_LAYERS"
                    if value.renderMode == "LOCAL_LAYERS"
                    else "LOCAL_MODEL"
                    if local_result is not None
                    else "PROVIDER_GENERATED"
                    if provider
                    else "LOCAL_RENDER"
                ),
                "createdAt": datetime.now(UTC).isoformat(),
                "humanQualityApproved": False,
                "habitImprovementEffectVerified": False,
            }
            if provider:
                artifact["provider"] = provider
                artifact["formationStatus"] = (
                    "MEASURED_ALPHA_GEOMETRY"
                    if local_result is not None
                    else "API_GEOMETRY_NOT_VERIFIED"
                )
                artifact["motifsVerification"] = (
                    "PROPOSED_NOT_VERIFIED_IN_LOCAL_MODEL_IMAGE"
                    if local_result is not None
                    else "PROPOSED_NOT_VERIFIED_IN_API_IMAGE"
                )
            else:
                artifact["motifsVerification"] = "LOCAL_RENDER_RECIPE"
            if value.renderMode == "LOCAL_LAYERS":
                spec = design["avatarSpec"]
                spec_sha = store.put_asset(principal, canonical(spec).encode(), "application/json")
                artifact["avatarSpec"] = {
                    "path": "/v3/assets/" + spec_sha,
                    "sha256": spec_sha,
                    "schemaVersion": spec["schemaVersion"],
                }
                artifact["formationStatus"] = "STATIC_LAYER_COMPOSITE"
                artifact["motifsVerification"] = "LOCAL_SHARED_LAYER_RECIPE"
            store.complete(principal, value.requestId, artifact)
            return {"data": artifact}
        except StudioError as exc:
            if value.renderMode == "LOCAL_MODEL" and exc.code == "LOCAL_MODEL_BUSY":
                store.release_unstarted_local(principal, value.requestId)
                raise
            store.fail(principal, value.requestId, exc.code)
            raise
        except Exception as exc:
            store.fail(principal, value.requestId, "GENERATION_FAILED")
            raise StudioError("GENERATION_FAILED", 500) from exc

    @application.post("/v3/conversation")
    def conversation(value: ConversationInput, request: Request, principal: Owner):
        config = request.app.state.config
        if not config.chat_available:
            raise StudioError("CONVERSATION_NOT_CONFIGURED", 503)
        reply = (conversation_generator or generate_reply)(config.chat_key, config.chat_model, value)
        return {"data": reply.model_dump()}

    @application.get("/v3/wardrobe/budget")
    def wardrobe_budget(request: Request, principal: Owner):
        from .wardrobe import budget
        return {"data": budget(request.app.state.store)}

    @application.post("/v3/wardrobe")
    def create_wardrobe(value: WardrobeInput, request: Request, principal: Owner):
        from .wardrobe import create
        return {"data": create(request.app.state.config, request.app.state.store, principal, value)}

    @application.get("/v3/avatars")
    def avatars(request: Request, principal: Owner):
        return {"data": request.app.state.store.avatars(principal)}

    @application.get("/v3/avatars/{character_id}")
    def avatar(character_id: str, request: Request, principal: Owner):
        if not re.fullmatch(r"nunti-[0-9a-f-]{36}", character_id):
            raise StudioError("CHARACTER_NOT_FOUND", 404)
        return {"data": request.app.state.store.avatar(principal, character_id)}

    @application.get("/v3/assets/{sha}")
    def asset(sha: str, request: Request, principal: Owner):
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise StudioError("ASSET_NOT_FOUND", 404)
        content, mime = request.app.state.store.asset(principal, sha)
        return Response(content, media_type=mime, headers={"X-Content-SHA256": sha})

    @application.post("/v3/avatars/{character_id}/voice")
    def generate_avatar_voice(character_id: str, request: Request, principal: Owner):
        if not re.fullmatch(r"nunti-[0-9a-f-]{36}", character_id):
            raise StudioError("CHARACTER_NOT_FOUND", 404)
        from .voice_service import generate_voice

        store = request.app.state.store
        artifact = store.avatar(principal, character_id)
        return {"data": generate_voice(store, principal, artifact)}

    @application.get("/v3/avatars/{character_id}/feedback-voice/{kind}")
    def avatar_feedback_voice(character_id: str, kind: str, request: Request, principal: Owner):
        if not re.fullmatch(r"nunti-[0-9a-f-]{36}", character_id):
            raise StudioError("CHARACTER_NOT_FOUND", 404)
        from .voice_service import get_feedback_voice

        store = request.app.state.store
        artifact = store.avatar(principal, character_id)
        return {"data": get_feedback_voice(store, principal, artifact, kind)}

    @application.post("/v3/avatars/{character_id}/feedback-voice/{kind}")
    def generate_avatar_feedback_voice(
        character_id: str, kind: str, request: Request, principal: Owner,
    ):
        if not re.fullmatch(r"nunti-[0-9a-f-]{36}", character_id):
            raise StudioError("CHARACTER_NOT_FOUND", 404)
        from .voice_service import generate_feedback_voice

        store = request.app.state.store
        artifact = store.avatar(principal, character_id)
        return {"data": generate_feedback_voice(store, principal, artifact, kind)}

    @application.get("/{path:path}")
    def static(path: str, request: Request):
        root = request.app.state.config.web_root.resolve()
        target = (root / (path or "index.html")).resolve()
        if (
            not target.is_relative_to(root)
            or not target.is_file()
            or target.suffix not in {".html", ".css", ".js", ".svg", ".png", ".ico", ".woff2", ".ttf"}
            or target.is_relative_to(root / "examples")
        ):
            raise StudioError("NOT_FOUND", 404)
        return FileResponse(target)

    return application


app = create_app()
