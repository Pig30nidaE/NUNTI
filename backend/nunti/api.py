import asyncio
import hmac
import sqlite3
from contextlib import asynccontextmanager, suppress
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException

from .config import Settings
from .errors import APIError
from .models import (
    AvatarSpec,
    Capabilities,
    EmotionBatch,
    Envelope,
    ErrorEnvelope,
    EventBatch,
    Identifier,
    Page,
    Receipt,
    RouteSnapshot,
    SampleBatch,
    ScoreBatch,
    StoredEmotion,
    StoredEvent,
    StoredReport,
    StoredSample,
    StoredScore,
    TripCreate,
    TripReport,
    TripView,
)
from .store import Store, now


def meta(request: Request):
    return {"requestId": getattr(request.state, "request_id", "unknown"), "serverTime": now()}


def envelope(request, data):
    return {"data": data, "meta": meta(request)}


def error(request, status, code, message, details=None):
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "details": details or []},
            "meta": meta(request),
        },
    )


class RequestGuard:
    """Bound JSON body memory, do not reflect input, and attach request metadata."""

    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        scope.setdefault("state", {})["request_id"] = str(uuid4())
        request = Request(scope)

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message["headers"]) + [
                    (b"cache-control", b"no-store"),
                    (b"x-request-id", scope["state"]["request_id"].encode()),
                ]
            await send(message)

        chunks = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunks.extend(message.get("body", b""))
            if len(chunks) > self.max_bytes:
                return await error(request, 413, "payload_too_large", "Request body is too large")(
                    scope, receive, safe_send
                )
            if not message.get("more_body", False):
                break
        if (
            chunks
            and request.headers.get("content-type", "").split(";")[0].strip() != "application/json"
        ):
            return await error(request, 415, "json_required", "Use application/json")(
                scope, receive, safe_send
            )
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, safe_send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.db_path, settings.retention_days)
    from .characters.worker import make_store

    character_store = make_store(settings)

    async def cleanup_loop():
        while True:
            await asyncio.sleep(3600)
            # Expired trips stay hidden if a busy database delays physical cleanup.
            with suppress(sqlite3.OperationalError):
                await asyncio.to_thread(store.purge_expired)

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        character_store.initialize()
        store.purge_expired()
        task = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="Nunti Sync API",
        version="1.0-draft",
        lifespan=lifespan,
        description=(
            "Mock-supported asynchronous storage. The server stores what the app computes; "
            "it does not score, calculate emotion or play TTS."
        ),
        responses={
            code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 413, 415, 422, 503)
        },
    )
    app.state.store = store
    app.state.character_store = character_store
    app.add_middleware(RequestGuard, max_bytes=settings.max_body_bytes)

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return error(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never expose input, error context or potentially sensitive field names/values.
        details = [
            {"field": str(e["loc"][0]) if e["loc"] else "request", "type": e["type"]}
            for e in exc.errors()[:20]
        ]
        return error(
            request, 422, "validation_error", "Request does not satisfy the v1 contract", details
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(request, exc.status_code, "http_error", "Request cannot be processed")

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        return error(
            request, 503, "storage_unavailable", "Storage is temporarily unavailable; retry later"
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return error(request, 500, "internal_error", "Unexpected server error")

    bearer = HTTPBearer(auto_error=False)

    def owner(
        request: Request, auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
    ):
        if settings.require_https and request.url.scheme != "https":
            raise APIError(403, "https_required", "HTTPS is required")
        supplied = auth.credentials if auth else ""
        if supplied.isascii():
            for token, principal in settings.tokens.items():
                if hmac.compare_digest(supplied, token):
                    return principal
        raise APIError(401, "unauthorized", "A valid bearer token is required")

    Owner = Annotated[str, Depends(owner)]
    from .characters.api import create_router

    app.include_router(create_router(character_store, settings, owner, envelope))

    def sync_enabled():
        if not settings.sync_enabled:
            raise APIError(403, "sync_disabled", "Server synchronization is disabled")

    @app.get("/health", response_model=Envelope[dict[str, str]])
    def health(request: Request):
        with store.connection() as db:
            db.execute("SELECT 1 FROM trips LIMIT 1")
        return envelope(request, {"status": "ok"})

    @app.get("/v1/capabilities", response_model=Envelope[Capabilities])
    def capabilities(request: Request, principal: Owner):
        return envelope(
            request,
            Capabilities(
                syncEnabled=settings.sync_enabled,
                mockEnabled=settings.enable_mocks,
                retentionDays=settings.retention_days,
            ),
        )

    router = APIRouter(prefix="/v1", dependencies=[Depends(sync_enabled)])

    @router.post("/trips", response_model=Envelope[Receipt])
    def create_trip(value: TripCreate, request: Request, principal: Owner):
        return envelope(request, store.create_trip(principal, value.model_dump()))

    @router.get("/trips/{trip_id}", response_model=Envelope[TripView])
    def get_trip(trip_id: Identifier, request: Request, principal: Owner):
        return envelope(request, store.get_trip(principal, trip_id))

    @router.put("/trips/{trip_id}/route", response_model=Envelope[Receipt])
    def put_route(trip_id: Identifier, value: RouteSnapshot, request: Request, principal: Owner):
        return envelope(request, store.put(principal, trip_id, "route", value.model_dump()))

    @router.put("/trips/{trip_id}/avatar", response_model=Envelope[Receipt])
    def put_avatar(trip_id: Identifier, value: AvatarSpec, request: Request, principal: Owner):
        return envelope(request, store.put(principal, trip_id, "avatar", value.model_dump()))

    @router.post("/trips/{trip_id}/events", response_model=Envelope[list[Receipt]])
    def post_events(trip_id: Identifier, value: EventBatch, request: Request, principal: Owner):
        return envelope(
            request,
            store.append(
                principal,
                trip_id,
                "event",
                [event.model_dump() for event in value.events],
            ),
        )

    @router.post("/trips/{trip_id}/emotions", response_model=Envelope[list[Receipt]])
    def post_emotions(trip_id: Identifier, value: EmotionBatch, request: Request, principal: Owner):
        return envelope(
            request,
            store.append(
                principal,
                trip_id,
                "emotion",
                [emotion.model_dump() for emotion in value.emotions],
            ),
        )

    @router.get("/trips/{trip_id}/events", response_model=Envelope[Page[StoredEvent]])
    def get_events(
        trip_id: Identifier,
        request: Request,
        principal: Owner,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ):
        return envelope(request, store.timeline(principal, trip_id, "event", offset, limit))

    @router.get("/trips/{trip_id}/emotions", response_model=Envelope[Page[StoredEmotion]])
    def get_emotions(
        trip_id: Identifier,
        request: Request,
        principal: Owner,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ):
        return envelope(request, store.timeline(principal, trip_id, "emotion", offset, limit))

    def with_source(item, batch_source):
        """Keep the batch's source on every stored record (an item's own source wins)."""
        record = item.model_dump()
        record["source"] = (item.source or batch_source).model_dump()
        return record

    @router.post("/trips/{trip_id}/samples", response_model=Envelope[list[Receipt]])
    def post_samples(trip_id: Identifier, value: SampleBatch, request: Request, principal: Owner):
        if value.tripId != trip_id:
            raise APIError(409, "trip_id_mismatch", "Payload tripId must match the URL")
        return envelope(
            request,
            store.append_telemetry(
                principal,
                trip_id,
                "sample",
                "sampleId",
                "occurredAt",
                [with_source(sample, value.source) for sample in value.samples],
            ),
        )

    @router.post("/trips/{trip_id}/scores", response_model=Envelope[list[Receipt]])
    def post_scores(trip_id: Identifier, value: ScoreBatch, request: Request, principal: Owner):
        if value.tripId != trip_id:
            raise APIError(409, "trip_id_mismatch", "Payload tripId must match the URL")
        return envelope(
            request,
            store.append_telemetry(
                principal,
                trip_id,
                "score",
                "scoreId",
                "computedAt",
                [with_source(score, value.source) for score in value.scores],
            ),
        )

    @router.get("/trips/{trip_id}/samples", response_model=Envelope[Page[StoredSample]])
    def get_samples(
        trip_id: Identifier,
        request: Request,
        principal: Owner,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ):
        return envelope(request, store.timeline(principal, trip_id, "sample", offset, limit))

    @router.get("/trips/{trip_id}/scores", response_model=Envelope[Page[StoredScore]])
    def get_scores(
        trip_id: Identifier,
        request: Request,
        principal: Owner,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ):
        return envelope(request, store.timeline(principal, trip_id, "score", offset, limit))

    @router.put("/trips/{trip_id}/report", response_model=Envelope[Receipt])
    def put_report(trip_id: Identifier, value: TripReport, request: Request, principal: Owner):
        if value.tripId != trip_id:
            raise APIError(409, "trip_id_mismatch", "Payload tripId must match the URL")
        return envelope(request, store.put(principal, trip_id, "report", value.model_dump()))

    @router.get("/trips/{trip_id}/report", response_model=Envelope[StoredReport])
    def get_report(trip_id: Identifier, request: Request, principal: Owner):
        return envelope(request, store.get_report(principal, trip_id))

    app.include_router(router)

    # Deletion stays available when synchronization is disabled or consent is withdrawn.
    @app.delete("/v1/trips/{trip_id}", response_model=Envelope[dict])
    def delete_trip(trip_id: Identifier, request: Request, principal: Owner):
        return envelope(request, store.delete_trip(principal, trip_id))

    if settings.enable_mocks:
        from .fixtures import load_scenario, scenario_names

        @app.get("/v1/mock/scenarios", response_model=Envelope[dict])
        def list_mocks(request: Request, principal: Owner):
            return envelope(request, {"mock": True, "scenarios": scenario_names()})

        @app.get("/v1/mock/scenarios/{scenario_id}", response_model=Envelope[dict])
        def get_mock(scenario_id: str, request: Request, principal: Owner):
            if scenario_id not in scenario_names():
                raise APIError(404, "mock_not_found", "Mock scenario not found")
            return envelope(request, load_scenario(scenario_id))

    from .openapi_examples import add_examples

    original_openapi = app.openapi

    def documented_openapi():
        return add_examples(original_openapi())

    app.openapi = documented_openapi
    return app
