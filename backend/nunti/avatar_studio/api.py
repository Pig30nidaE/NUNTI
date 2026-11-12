"""Loopback-only v3 avatar studio. Start with nunti.avatar_studio.api:app on port 8768."""

import base64
import hmac
import io
import ipaddress
import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError

from .conversation import DEFAULT_MODEL, ConversationInput, generate_reply
from .models import AvatarInput, ExtractionInput, Route, RoutePlanInput, SessionInput, digest
from .storage import StudioError, StudioStore
from .wardrobe import WardrobeInput

ROOT = Path(__file__).resolve().parents[3]
COOKIE = "nunti_studio_session"
MAX_BYTES = 8_388_608
MAX_BODY = 11_200_000
ENV_FILES = (ROOT / ".env.local", ROOT / ".env", ROOT / "backend/.env")


def env_value(name: str, default: str = "") -> str:
    """Read an environment variable from os.environ or project .env files without logging it."""
    val = os.getenv(name, "").strip()
    if val:
        return val
    for path in (*ENV_FILES, Path.cwd() / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, sep, raw = line.partition("=")
            if sep and key.strip() == name:
                raw = raw.strip()
                if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
                    raw = raw[1:-1]
                if raw:
                    return raw
    return default


def _default_token(workspace: Path) -> str:
    token = env_value("NUNTI_STUDIO_TOKEN")
    if token:
        return token
    conn = workspace / "connection.json"
    if conn.is_file():
        try:
            saved = json.loads(conn.read_text()).get("token", "")
            if 32 <= len(saved) <= 256:
                return saved
        except Exception:
            pass
    token = secrets.token_urlsafe(36)
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        payload = {"baseUrl": "http://127.0.0.1:8768", "token": token}
        conn.write_text(json.dumps(payload, indent=2) + "\n")
        conn.chmod(0o600)
    except OSError:
        pass
    return token


@dataclass
class Settings:
    token: str = field(repr=False)
    workspace: Path
    web_root: Path = ROOT / "prototypes/avatar_generator"
    port: int = 8768
    paid_api_approved: bool = False
    image_key: str = field(default="", repr=False)
    route_api_enabled: bool = False
    wardrobe_enabled: bool = False
    chat_enabled: bool = False
    chat_key: str = field(default="", repr=False)
    chat_model: str = DEFAULT_MODEL

    @property
    def wardrobe_available(self) -> bool:
        return self.paid_api_approved and self.wardrobe_enabled and bool(self.image_key)

    @property
    def chat_available(self) -> bool:
        return self.chat_enabled and bool(self.chat_key)

    def __post_init__(self):
        if not 32 <= len(self.token) <= 256 or not all(33 <= ord(c) <= 126 for c in self.token):
            raise ValueError("NUNTI_STUDIO_TOKEN_REQUIRED")
        self.workspace = Path(self.workspace)
        self.web_root = Path(self.web_root)
        if not 1024 <= self.port <= 65535:
            raise ValueError("INVALID_STUDIO_PORT")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", self.chat_model):
            raise ValueError("INVALID_CHAT_MODEL")

    @property
    def owner(self) -> str:
        return digest(self.token.encode())

    @property
    def session_cookie(self) -> str:
        return hmac.new(self.token.encode(), b"nunti-studio-session-v1", "sha256").hexdigest()

    @classmethod
    def from_env(cls):
        workspace = Path(env_value("NUNTI_STUDIO_WORKSPACE", str(ROOT / ".local/avatar-generator")))
        approved = env_value("NUNTI_STUDIO_PAID_API_APPROVED", "true").lower() != "false"
        wardrobe_enabled = env_value("NUNTI_STUDIO_WARDROBE_ENABLED", "true").lower() != "false"
        chat_enabled = env_value("NUNTI_STUDIO_CHAT_API_ENABLED", "true").lower() != "false"
        route_api_enabled = env_value("NUNTI_STUDIO_ROUTE_API_ENABLED", "true").lower() != "false"
        api_key = env_value("OPENAI_API_KEY")
        chat_key = env_value("NUNTI_STUDIO_CHAT_API_KEY") or api_key
        return cls(
            token=_default_token(workspace),
            workspace=workspace,
            port=int(env_value("NUNTI_STUDIO_PORT", "8768")),
            paid_api_approved=approved,
            image_key=api_key if approved else "",
            wardrobe_enabled=wardrobe_enabled,
            chat_enabled=chat_enabled,
            chat_key=chat_key if chat_enabled else "",
            chat_model=env_value("NUNTI_STUDIO_CHAT_MODEL", DEFAULT_MODEL),
            route_api_enabled=route_api_enabled,
        )


def image_info(content: bytes) -> dict:
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


def secure_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def create_app(
    settings: Settings | None = None,
    *,
    extractor=None,
    route_fetcher=None,
    wardrobe_renderer=None,
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

    def error_response(code: str, status: int):
        return JSONResponse({"data": None, "error": {"code": code}}, status_code=status)

    @application.exception_handler(StudioError)
    async def studio_error(request, error):
        return error_response(error.code, error.status)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response("INVALID_REQUEST", 422)

    @application.middleware("http")
    async def local_boundary(request: Request, call_next):
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
        config = request.app.state.config
        return {
            "data": {
                "schemaVersion": 3,
                "mode": "OPENAI_WARDROBE",
                "wardrobeAvailable": config.wardrobe_available,
                "conversationAvailable": config.chat_available,
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
                },
                "imageApiPaidApproved": config.paid_api_approved,
                "voice": {
                    "mode": "DEVICE_SPEECH",
                    "automaticPlayback": False,
                    "blocksVisualReady": False,
                },
                "habitImprovementEffectVerified": False,
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
        from .wardrobe import create, render

        wardrobe_input = WardrobeInput(
            destination=value.destination,
            purpose=value.purpose,
            route=value.route,
            mood=value.mood,
            scenery=value.scenery,
            road=value.road,
        )
        return {
            "data": create(
                request.app.state.config,
                request.app.state.store,
                principal,
                wardrobe_input,
                wardrobe_renderer or render,
            )
        }

    @application.post("/v3/conversation")
    def conversation(value: ConversationInput, request: Request, principal: Owner):
        config = request.app.state.config
        if not config.chat_available:
            raise StudioError("CONVERSATION_NOT_CONFIGURED", 503)
        reply = (conversation_generator or generate_reply)(
            config.chat_key, config.chat_model, value
        )
        return {"data": reply.model_dump()}

    @application.get("/v3/wardrobe/budget")
    def wardrobe_budget(request: Request, principal: Owner):
        from .wardrobe import budget

        return {"data": budget(request.app.state.store)}

    @application.post("/v3/wardrobe")
    def create_wardrobe(value: WardrobeInput, request: Request, principal: Owner):
        from .wardrobe import create, render

        return {
            "data": create(
                request.app.state.config,
                request.app.state.store,
                principal,
                value,
                wardrobe_renderer or render,
            )
        }

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

    @application.get("/{path:path}")
    def static(path: str, request: Request):
        root = request.app.state.config.web_root.resolve()
        target = (root / (path or "index.html")).resolve()
        if (
            not target.is_relative_to(root)
            or target.is_relative_to((root / "examples").resolve())
            or not target.is_file()
            or target.suffix not in {".html", ".css", ".js", ".json", ".png", ".svg", ".ttf"}
        ):
            raise StudioError("NOT_FOUND", 404)
        return FileResponse(target)

    return application


app = create_app()
