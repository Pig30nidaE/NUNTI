"""Owner-authenticated v2 generation routes using the host API's envelope."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ..errors import APIError
from .models import GenerationInput, JobView, SpeechInput


def create_router(store, settings, owner_dependency, envelope):
    router = APIRouter(prefix="/v2", tags=["character-generation-v2"])
    Owner = Annotated[str, Depends(owner_dependency)]

    def enabled():
        if settings.generation_mode == "DISABLED":
            raise APIError(403, "generation_disabled", "Character generation is disabled")

    @router.get("/generation-capabilities")
    def capabilities(request: Request, principal: Owner):
        data = {
            "mode": settings.generation_mode,
            "pipeline": settings.generation_pipeline,
            "initialBatchLimit": settings.generation_initial_limit,
            "characterBudgetMicros": settings.generation_job_cap_micros,
            "totalBudgetMicros": settings.generation_total_cap_micros,
            "humanQualityApproved": False,
        }
        if settings.generation_mode == "OFFLINE_FIXTURE":
            from .providers import FixturePipeline

            fixture = FixturePipeline(settings)
            data["fixtureTexts"] = {
                name: value["metadata"]["text"] for name, value in fixture.clips.items()
            }
            data["fixtureFollowupText"] = (
                fixture.followup["metadata"]["text"] if fixture.followup else None
            )
            data["fixtureNotice"] = (
                "Pre-existing image and audio; no new image, voice or destination-specific "
                "speech generation."
            )
        return envelope(request, data)

    @router.post("/character-generations", dependencies=[Depends(enabled)])
    def create_character(value: GenerationInput, request: Request, principal: Owner):
        data = store.submit(principal, value.model_dump(), settings.generation_mode)
        JobView.model_validate(data)
        return envelope(request, store.get_job(principal, value.requestId))

    @router.get("/jobs/{request_id}")
    def get_job(request_id: str, request: Request, principal: Owner):
        return envelope(request, store.get_job(principal, request_id))

    @router.get("/characters/{character_id}")
    def get_character(character_id: str, request: Request, principal: Owner):
        artifact, _ = store.character(principal, character_id)
        return envelope(request, artifact)

    @router.post("/characters/{character_id}/speech", dependencies=[Depends(enabled)])
    def create_speech(character_id: str, value: SpeechInput, request: Request, principal: Owner):
        artifact, _ = store.character(principal, character_id)
        if artifact["mode"] != settings.generation_mode:
            raise APIError(
                409, "character_mode_mismatch", "Saved character uses a different media origin"
            )
        store.submit(principal, value.model_dump(), artifact["mode"], character_id)
        return envelope(request, store.get_job(principal, value.requestId))

    @router.get("/assets/{digest}")
    def get_asset(digest: str, principal: Owner):
        path, mime = store.asset(principal, digest)
        # Read authenticated, size/hash-checked bytes once; no public static mount.
        return Response(
            path.read_bytes(),
            media_type=mime,
            headers={"X-Content-SHA256": digest, "X-Content-Type-Options": "nosniff"},
        )

    return router
