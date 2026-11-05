"""Durable, separately launched v2 worker. Merely starting FastAPI never calls a provider."""

import argparse
import json
import re
import signal
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ..config import Settings
from .media import inspect_png, inspect_wav
from .models import CharacterArtifact, Concept, canonical, sha
from .providers import ApiPipeline, FixturePipeline, ProviderUnknown, unb64
from .store import CharacterStore


def make_store(settings):
    return CharacterStore(
        settings.character_db_path or settings.db_path.parent / "characters-v2.sqlite3",
        settings.character_media_path or settings.db_path.parent / "characters-v2-media",
        job_cap=settings.generation_job_cap_micros,
        total_cap=settings.generation_total_cap_micros,
        initial_limit=settings.generation_initial_limit,
        voice_capacity=settings.generation_voice_capacity,
    )


class GenerationWorker:
    def __init__(self, store, settings, pipeline_factory=None):
        self.store, self.settings = store, settings
        self.holder = str(uuid4())
        self.pipeline_factory = pipeline_factory
        self.provider_calls = 0

    def _pipeline(self, mode, pipeline_name=None, for_speech=False):
        if self.pipeline_factory:
            return self.pipeline_factory(mode)
        settings = (
            replace(self.settings, generation_pipeline=pipeline_name)
            if pipeline_name
            else self.settings
        )
        if mode == "OFFLINE_FIXTURE":
            return FixturePipeline(settings)
        if mode == "API":
            if self.settings.generation_mode != "API":
                raise ValueError("GENERATION_MODE_NOT_ARMED")
            return ApiPipeline(settings, purpose="speech" if for_speech else "character")
        raise ValueError("GENERATION_DISABLED")

    def _call(self, job, name, request, action):
        self.store.heartbeat(self.holder, job)
        if job["mode"] == "OFFLINE_FIXTURE":
            reserve = 0
        elif name in {"preflight", "voice_refresh_status"}:
            reserve = 0
        else:
            ceiling = self.settings.generation_step_ceilings
            key = name if name in ceiling else "speech" if name.startswith("speech_") else name
            if key not in ceiling or ceiling[key] <= 0:
                raise ValueError("ACCOUNT_PRICE_CONFIGURATION_REQUIRED")
            reserve = ceiling[key]
        existing = self.store.begin_step(job, name, request, reserve)
        if existing is not None:
            return existing
        self.provider_calls += 1
        result = action()
        audit = getattr(getattr(self, "active_pipeline", None), "audit", None)
        self.store.finish_step(job, name, result, audit=audit)
        if audit is not None:
            audit.clear()
        return result

    def run_once(self):
        job = self.store.claim(self.holder)
        if not job:
            self.store.release_worker(self.holder)
            return None
        stop = threading.Event()

        # The provider timeout is 90s, lease is 300s; heartbeat also protects a
        # slow image generation or PCM validation from a second worker process.
        def heartbeat():
            while not stop.wait(30):
                try:
                    self.store.heartbeat(self.holder, job)
                except (ValueError, OSError):
                    return

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            if job["kind"] == "SPEECH":
                self._speech(job)
            else:
                pipeline = self._pipeline(job["mode"])
                self.active_pipeline = pipeline
                self._character(job, pipeline)
        except ProviderUnknown:
            self.store.fail(job, "PROVIDER_RESULT_UNKNOWN", unknown=True)
        except Exception as exc:
            code = (
                str(exc)
                if isinstance(exc, ValueError) and re.fullmatch("[A-Z0-9_]{1,120}", str(exc))
                else "GENERATION_FAILED"
            )
            self.store.fail(job, code, unknown=code == "PROVIDER_RESULT_UNKNOWN")
        finally:
            stop.set()
            thread.join(timeout=1)
            self.store.release_worker(self.holder)
        return self.store.get_job(job["owner"], job["request_id"])

    def _character(self, job, pipeline):
        value = json.loads(job["input_json"])
        character_id = "gen-" + sha((job["owner"] + "\n" + job["request_id"]).encode())[:24]
        # Account slot/model availability is queried only after the adapter has
        # validated all keys and explicit account price configuration.
        account = self._call(
            job, "preflight", {"providerId": pipeline.provider_id}, pipeline.preflight
        )
        self.store.reserve_voice(
            job, character_id, pipeline.provider_id, account["availableVoiceSlots"]
        )
        concept = self._call(job, "planning", value, lambda: pipeline.plan(value))
        concept = Concept.model_validate(concept).model_dump()
        spec = {
            "schemaVersion": 1,
            "characterId": character_id,
            "journeyId": job["request_id"],
            "inputSha256": job["input_sha"],
            "concept": concept,
        }
        spec_hash = sha(canonical(spec).encode())
        self.store.stage(job, "MEDIA")
        images = self._call(
            job,
            "image_candidates",
            {"specHash": spec_hash},
            lambda: pipeline.images(value, concept),
        )
        # Validate every candidate before spending more on voice design/evaluation.
        for candidate in images["candidates"]:
            inspect_png(
                unb64(candidate["data"]), require_alpha=not getattr(pipeline, "google", False)
            )
        voices = self._call(
            job,
            "voice_candidates",
            {"specHash": spec_hash},
            lambda: pipeline.voice_candidates(value, concept),
        )
        self.store.stage(job, "SELECTING")
        selection = self._call(
            job,
            "selection",
            {
                "specHash": spec_hash,
                "imagesHash": sha(canonical(images).encode()),
                "voicesHash": sha(canonical(voices).encode()),
            },
            lambda: pipeline.select(concept, images, voices),
        )
        image = unb64(images["candidates"][selection["imageIndex"]]["data"])
        if getattr(pipeline, "google", False):
            original_sha = self.store.put_asset(job["owner"], image, "image/png")
            prepared = self._call(
                job,
                "remove_background",
                {"originalSha256": original_sha},
                lambda: pipeline.prepare_image(image),
            )
            image = unb64(prepared["data"])
        image_info = inspect_png(image)
        self.store.put_asset(job["owner"], image, "image/png")
        voice = self._call(
            job,
            "save_voice",
            {"specHash": spec_hash, "voiceIndex": selection["voiceIndex"]},
            lambda: pipeline.save_voice(
                character_id, concept, voices["candidates"][selection["voiceIndex"]]
            ),
        )
        self.store.record_voice(job, character_id, voice["voiceId"])
        settings_hash = sha(
            canonical(
                {
                    "providerId": pipeline.provider_id,
                    "designModel": pipeline.design_model,
                    "synthesisModel": pipeline.synthesis_model,
                    "format": "pcm_s16le_24000_mono",
                    "language": "ko-KR",
                    "revision": "nunti-designed-voice-1",
                }
            ).encode()
        )
        binding_id = (
            "dvb-"
            + sha(
                canonical(
                    {
                        "characterId": character_id,
                        "specHash": spec_hash,
                        "settingsSha256": settings_hash,
                        "voiceId": voice["voiceId"],
                    }
                ).encode()
            )[:32]
        )
        source = {
            "kind": "designed-voice-v1",
            "providerId": pipeline.provider_id,
            "designModel": pipeline.design_model,
            "synthesisModel": pipeline.synthesis_model,
            "voiceId": voice["voiceId"],
            "bindingId": binding_id,
            "specSha256": spec_hash,
            "settingsSha256": settings_hash,
            "mediaOrigin": pipeline.origin,
        }
        binding = {
            "voiceId": voice["voiceId"],
            "source": source,
            "spec": spec,
            "profileId": "designed-" + sha(binding_id.encode())[:24],
            "pipeline": self.settings.generation_pipeline,
            "providerOperations": voice.get("providerOperations", {}),
        }
        self.store.stage(job, "SPEECH")
        clips = [
            self._clip(job, pipeline, character_id, binding, name, concept["texts"][name])
            for name in ("greeting", "common", "arrival")
        ]
        manifest = self._manifest(
            character_id, concept["displayName"], pipeline.provider_id, clips, job["mode"]
        )
        artifact = {
            "schemaVersion": 2,
            "characterId": character_id,
            "journeyId": job["request_id"],
            "inputSha256": job["input_sha"],
            "inputCanonical": job["input_json"],
            "specHash": spec_hash,
            "displayName": concept["displayName"],
            "destinationName": value["destination"]["name"],
            "purpose": value["purpose"],
            "mode": job["mode"],
            "visual": {
                "version": "generated-rgba-1",
                "asset": image_info | {"path": "/v2/assets/" + image_info["sha256"]},
                "route": value["route"]["points"],
            },
            "voice": {
                "description": concept["voiceDescription"],
                "bindingId": binding_id,
                "profileId": binding["profileId"],
            },
            "voiceManifest": manifest,
        }
        if job["mode"] == "OFFLINE_FIXTURE":
            artifact["fixtureProvenance"] = pipeline.provenance
        self.store.stage(job, "VALIDATING")
        CharacterArtifact.model_validate(artifact)
        self.store.complete(job, artifact, binding)

    @staticmethod
    def _manifest(character_id, name, provider_id, clips, mode):
        return {
            "schemaVersion": 3,
            "providerId": provider_id,
            "characters": [{"characterId": character_id, "displayName": name}],
            "scope": mode,
            "clips": clips,
        }

    def _clip(self, job, pipeline, character_id, binding, category, text):
        render = self._call(
            job,
            "speech_" + category,
            {"voiceId": binding["voiceId"], "text": text, "source": binding["source"]},
            lambda: pipeline.speak({"voiceId": binding["voiceId"]}, text),
        )
        audio = unb64(render["audio"])
        metadata = inspect_wav(audio)
        self.store.put_asset(job["owner"], audio, "audio/wav")
        clip = {
            "clipId": character_id + "-" + category,
            "characterId": character_id,
            "profileId": binding["profileId"],
            "speakerId": binding["voiceId"],
            "locale": "ko-KR",
            "text": text,
            "textSha256": sha(text.encode()),
            "audioPath": character_id + "-" + category + ".wav",
            "source": binding["source"],
            **metadata,
        }
        if render.get("rawAudioSha256"):
            clip["rawAudioSha256"] = render["rawAudioSha256"]
        if render.get("fixtureProvenance"):
            clip["fixtureProvenance"] = render["fixtureProvenance"]
        self.store.pin_clip(job["owner"], clip)
        return clip

    def _speech(self, job):
        value = json.loads(job["input_json"])
        artifact, binding = self.store.character(job["owner"], job["character_id"])
        existing = self.store.find_clip(
            job["owner"], job["character_id"], sha(value["text"].encode())
        )
        maintenance = self.store.is_maintenance(job)
        if existing:
            if maintenance:
                pipeline = self._pipeline(job["mode"], binding["pipeline"], for_speech=True)
                self.active_pipeline = pipeline
                self._refresh_voice(job, pipeline, artifact, binding)
            self.store.complete(
                job,
                self._manifest(
                    artifact["characterId"],
                    artifact["displayName"],
                    binding["source"]["providerId"],
                    [existing],
                    job["mode"],
                ),
            )
            return
        pipeline = self._pipeline(job["mode"], binding["pipeline"], for_speech=True)
        self.active_pipeline = pipeline
        if (
            artifact["mode"] != job["mode"]
            or binding["source"]["providerId"] != pipeline.provider_id
        ):
            raise ValueError("SAVED_VOICE_PROVIDER_CHANGED")
        if (binding["source"]["designModel"], binding["source"]["synthesisModel"]) != (
            pipeline.design_model,
            pipeline.synthesis_model,
        ):
            raise ValueError("SAVED_VOICE_MODEL_CHANGED")
        clip = self._clip(
            job,
            pipeline,
            artifact["characterId"],
            binding,
            "speech-" + sha(value["text"].encode())[:20],
            value["text"],
        )
        if maintenance:
            self._refresh_voice(job, pipeline, artifact, binding)
        self.store.complete(
            job,
            self._manifest(
                artifact["characterId"],
                artifact["displayName"],
                pipeline.provider_id,
                [clip],
                job["mode"],
            ),
        )

    def _refresh_voice(self, job, pipeline, artifact, binding):
        if binding["source"]["providerId"] != "gemini-designed":
            raise ValueError("VOICE_RENEWAL_PROVIDER_MISMATCH")
        status = self._call(
            job,
            "voice_refresh_status",
            {"voiceId": binding["voiceId"]},
            lambda: pipeline.voice_status(binding["voiceId"]),
        )
        if status.get("voiceId") != binding["voiceId"]:
            raise ValueError("PROVIDER_VOICE_ID_OR_EXPIRY_MISMATCH")
        expires = datetime.fromisoformat(status["expireTime"].replace("Z", "+00:00"))
        if expires.tzinfo is None:
            raise ValueError("PROVIDER_EXPIRY_TIMEZONE_REQUIRED")
        self.store.record_operations(
            job["owner"],
            artifact["characterId"],
            binding["voiceId"],
            {
                "expireTime": status["expireTime"],
                "lastVerifiedAt": datetime.now(UTC).isoformat(),
                "voiceId": binding["voiceId"],
                "lastRenewalRequestId": job["request_id"],
            },
        )
        if expires <= datetime.now(UTC) + timedelta(days=90):
            raise ValueError("VOICE_RENEWAL_NOT_CONFIRMED")


def main():
    parser = argparse.ArgumentParser(
        description="Single durable v2 generation worker (never auto-started by API)"
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    store = make_store(settings)
    store.initialize()
    worker = GenerationWorker(store, settings)
    stopping = threading.Event()

    def stop_after_current_job(signum, frame):
        stopping.set()

    signal.signal(signal.SIGTERM, stop_after_current_job)
    signal.signal(signal.SIGINT, stop_after_current_job)
    try:
        while not stopping.is_set():
            result = worker.run_once()
            if result:
                print(
                    canonical(
                        {key: result[key] for key in ("jobId", "state", "stage", "mode", "error")}
                    ),
                    flush=True,
                )
            if args.once:
                break
            if not result:
                stopping.wait(0.3)
    finally:
        store.release_worker(worker.holder)


if __name__ == "__main__":
    main()
