"""Offline billing/expiry operations and cross-runtime RIFF format boundaries."""

import json
import struct
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from nunti.api import create_app
from nunti.characters.maintenance import plan_renewals
from nunti.characters.media import inspect_wav, pcm_wav
from nunti.characters.providers import FixturePipeline
from nunti.characters.reconcile import reconcile
from nunti.characters.worker import GenerationWorker

from .test_characters_v2 import api_settings, input_value
from .test_characters_v2 import generation_settings as generation_settings


@pytest.mark.parametrize(
    "mutation", ["trailing", "duplicate_fmt", "duplicate_data", "bad_byte_rate"]
)
def test_riff_boundary_matches_android_and_rejects_ambiguous_chunks(mutation):
    original = pcm_wav(bytes([1, 0]) * 1200)
    if mutation == "trailing":
        changed = original + b"unaccounted trailing bytes"
    elif mutation == "duplicate_fmt":
        changed = original[:36] + original[12:36] + original[36:]
        changed = changed[:4] + struct.pack("<I", len(changed) - 8) + changed[8:]
    elif mutation == "duplicate_data":
        changed = original + original[36:]
        changed = changed[:4] + struct.pack("<I", len(changed) - 8) + changed[8:]
    else:
        changed = original[:28] + struct.pack("<I", 1) + original[32:]
    with pytest.raises(ValueError, match="INVALID_AUDIO_FORMAT"):
        inspect_wav(changed)
    assert inspect_wav(original)["durationMs"] == 50


def test_offline_billing_reconciliation_records_zero_and_unknown_separately(generation_settings):
    with TestClient(create_app(generation_settings)) as client:
        store = client.app.state.character_store
        value = input_value()
        store.submit("a", value, "API")
        job = store.claim("billing-fixture")
        for name in ("planning", "image_candidates"):
            store.begin_step(job, name, {}, 100)
            store.finish_step(job, name, {"testReceiptOnly": True})
        assert store.get_job("a", value["requestId"])["cost"]["actualMicros"] is None
        charges = {
            "owner": "a",
            "requestId": value["requestId"],
            "steps": [
                {
                    "name": "planning",
                    "actualMicros": 0,
                    "providerRequestId": "receipt-zero",
                    "evidenceReference": "account-invoice-line-free",
                },
                {
                    "name": "image_candidates",
                    "actualMicros": 175,
                    "providerRequestId": "receipt-image",
                    "evidenceReference": "account-invoice-image",
                },
            ],
        }
        result = reconcile(store, charges)
        assert result["providerRequests"] == 0
        assert result["cost"]["actualMicros"] == 175
        assert result["cost"]["reservedMicros"] == 200
        assert result["cost"]["overReservation"] is True
        assert reconcile(store, charges) == result
        changed = json.loads(json.dumps(charges))
        changed["steps"][1]["actualMicros"] = 176
        with pytest.raises(ValueError, match="CONFIRMED_CHARGE_CANNOT_CHANGE"):
            reconcile(store, changed)
        changed = json.loads(json.dumps(charges))
        changed["steps"][1]["evidenceReference"] = "different-invoice"
        with pytest.raises(ValueError, match="CONFIRMED_BILLING_EVIDENCE_CANNOT_CHANGE"):
            reconcile(store, changed)


def test_reconciliation_is_owner_scoped_done_only_atomic_and_exposes_overrun(generation_settings):
    with TestClient(create_app(generation_settings)) as client:
        store = client.app.state.character_store
        value = input_value()
        store.submit("a", value, "API")
        job = store.claim("billing-fixture")
        store.begin_step(job, "planning", {}, 100)
        store.finish_step(job, "planning", {})
        store.begin_step(job, "still_calling", {}, 100)
        charge = {
            "name": "planning",
            "actualMicros": 400000,
            "providerRequestId": "actual-receipt",
            "evidenceReference": "invoice-higher-than-reservation",
        }
        with pytest.raises(ValueError, match="RECONCILIATION_JOB_NOT_FOUND"):
            reconcile(store, {"owner": "b", "requestId": value["requestId"], "steps": [charge]})
        pending = charge | {"name": "still_calling"}
        with pytest.raises(ValueError, match="RECONCILIATION_REQUIRES_DONE_STEP"):
            reconcile(
                store, {"owner": "a", "requestId": value["requestId"], "steps": [charge, pending]}
            )
        assert store.get_job("a", value["requestId"])["cost"]["knownActualMicros"] == 0
        result = reconcile(
            store, {"owner": "a", "requestId": value["requestId"], "steps": [charge]}
        )
        assert result["cost"]["knownActualMicros"] == 400000
        assert result["cost"]["actualMicros"] is None
        assert result["cost"]["overBudget"] is True
        with pytest.raises(ValueError, match="BUDGET_CAP_REACHED"):
            store.begin_step(job, "next_paid_step", {}, 1)


def test_google_expiry_maintenance_is_read_only_and_never_changes_voice(generation_settings):
    class GoogleLikeFixture(FixturePipeline):
        provider_id = "gemini-designed"
        origin = "PROVIDER_GENERATED"
        design_model = "gemini-3.8-flash-tts"
        synthesis_model = "gemini-3.8-flash-tts"

        def save_voice(self, character_id, concept, candidate):
            return {
                "voiceId": "google-retained-voice",
                "providerOperations": {"expireTime": "2027-01-01T00:00:00Z"},
            }

    with TestClient(create_app(generation_settings)) as client:
        store = client.app.state.character_store
        value = input_value()
        # Provider double exercises TTL metadata without a model call.
        store.submit("a", value, "OFFLINE_FIXTURE")
        result = GenerationWorker(
            store, generation_settings, lambda mode: GoogleLikeFixture(generation_settings)
        ).run_once()
        assert result["state"] == "READY", result
        before = store.path.read_bytes()
        plan = plan_renewals(store, now=datetime(2026, 11, 3, tzinfo=UTC))
        assert plan["providerRequests"] == plan["jobsSubmitted"] == 0
        assert plan["liveRenewalVerified"] is False
        assert len(plan["renewals"]) == 1
        assert plan["renewals"][0]["voiceId"] == "google-retained-voice"
        assert plan["renewals"][0]["wouldRequest"]["text"] == "2026년 11월에도 천천히 함께 가자."
        assert store.path.read_bytes() == before


def test_reconcile_and_maintenance_clis_run_offline_without_provider_keys(
    generation_settings, tmp_path
):
    import os
    import subprocess
    import sys

    from .conftest import TOKEN_A

    with TestClient(create_app(generation_settings)) as client:
        store = client.app.state.character_store
        value = input_value()
        store.submit("a", value, "API")
        job = store.claim("offline-cli-fixture")
        store.begin_step(job, "planning", {}, 100)
        store.finish_step(job, "planning", {"receiptFixture": True})
        payload = {
            "owner": "a",
            "requestId": value["requestId"],
            "steps": [
                {
                    "name": "planning",
                    "actualMicros": 75,
                    "providerRequestId": "invoice-id",
                    "evidenceReference": "invoice-reference",
                }
            ],
        }
        source, report = tmp_path / "charges.json", tmp_path / "result.json"
        source.write_text(json.dumps(payload))
        env = os.environ.copy()
        for name in ("OPENAI_API_KEY", "ELEVENLABS_API_KEY", "GOOGLE_API_KEY", "RECRAFT_API_TOKEN"):
            env.pop(name, None)
        env.update(
            NUNTI_AUTH_TOKENS=json.dumps({TOKEN_A: "a"}),
            NUNTI_DB_PATH=str(generation_settings.db_path),
            NUNTI_REQUIRE_HTTPS="false",
        )
        applied = subprocess.run(
            [
                sys.executable,
                "-m",
                "nunti.characters.reconcile",
                "--input",
                str(source),
                "--output",
                str(report),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert applied.returncode == 0, applied.stderr
        assert json.loads(report.read_text())["cost"]["actualMicros"] == 75
        dry = subprocess.run(
            [sys.executable, "-m", "nunti.characters.maintenance", "--dry-run"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert dry.returncode == 0, dry.stderr
        assert json.loads(dry.stdout)["providerRequests"] == 0
        assert json.loads(dry.stdout)["jobsSubmitted"] == 0


def test_monthly_google_renewal_enqueue_deduplicates_and_updates_only_operations(
    generation_settings,
):
    from datetime import timedelta

    from nunti.characters.maintenance import enqueue_due

    settings = api_settings(generation_settings, generation_pipeline="GOOGLE_COMPARE")
    now = datetime.now(UTC)

    class GoogleTransportDouble(FixturePipeline):
        provider_id = "gemini-designed"
        origin = "PROVIDER_GENERATED"
        design_model = "gemini-3.8-flash-tts"
        synthesis_model = "gemini-3.8-flash-tts"

        def __init__(self, settings):
            super().__init__(settings)
            self.saved, self.spoken, self.statuses = 0, [], []

        def save_voice(self, character_id, concept, candidate):
            self.saved += 1
            return {
                "voiceId": "google-fixed-retained-id",
                "providerOperations": {"expireTime": (now + timedelta(days=20)).isoformat()},
            }

        def speak(self, voice, text):
            self.spoken.append((voice["voiceId"], text))
            return {"audio": self.clips["greeting"]["audio"], "format": "wav"}

        def voice_status(self, voice_id):
            self.statuses.append(voice_id)
            return {"voiceId": voice_id, "expireTime": (now + timedelta(days=365)).isoformat()}

    with TestClient(create_app(settings)) as client:
        store = client.app.state.character_store
        provider = GoogleTransportDouble(settings)
        worker = GenerationWorker(store, settings, lambda mode: provider)
        value = input_value()
        store.submit("a", value, "API")
        original = worker.run_once()["artifact"]
        before = json.loads(json.dumps(original))
        old_files = {p.name: p.read_bytes() for p in store.media.iterdir()}
        first, second = enqueue_due(store, now=now), enqueue_due(store, now=now)
        assert first == second
        assert first["providerRequests"] == 0
        assert len(first["jobs"]) == 1
        with store.connect() as db:
            assert db.execute("SELECT count(*) FROM maintenance_jobs").fetchone()[0] == 1
        result = worker.run_once()
        assert result["state"] == "READY", result
        assert provider.saved == 1  # Only initial character design, no replacement voice.
        assert len(provider.spoken) == 4
        assert provider.spoken[-1][0] == "google-fixed-retained-id"
        assert str(now.year) in provider.spoken[-1][1]
        assert provider.statuses == ["google-fixed-retained-id"]
        assert (
            store.operations("a", original["characterId"])["expireTime"]
            == (now + timedelta(days=365)).isoformat()
        )
        assert store.character("a", original["characterId"])[0] == before
        assert all((store.media / name).read_bytes() == data for name, data in old_files.items())
        assert enqueue_due(store, now=now)["jobs"] == []
        assert worker.run_once() is None


def test_renewal_404_fails_without_replacing_voice_and_preserves_synthesized_clip(
    generation_settings,
):
    from datetime import timedelta

    from nunti.characters.maintenance import enqueue_due

    settings = api_settings(generation_settings, generation_pipeline="GOOGLE_COMPARE")
    now = datetime.now(UTC)

    class MissingVoiceDouble(FixturePipeline):
        provider_id = "gemini-designed"
        origin = "PROVIDER_GENERATED"
        design_model = "gemini-3.8-flash-tts"
        synthesis_model = "gemini-3.8-flash-tts"

        def save_voice(self, character_id, concept, candidate):
            return {
                "voiceId": "google-missing-id",
                "providerOperations": {"expireTime": (now + timedelta(days=1)).isoformat()},
            }

        def speak(self, voice, text):
            return {"audio": self.clips["greeting"]["audio"], "format": "wav"}

        def voice_status(self, voice_id):
            raise ValueError("PROVIDER_HTTP_404")

    with TestClient(create_app(settings)) as client:
        store = client.app.state.character_store
        provider = MissingVoiceDouble(settings)
        worker = GenerationWorker(store, settings, lambda mode: provider)
        store.submit("a", input_value(), "API")
        original = worker.run_once()["artifact"]
        plan = enqueue_due(store, now=now)
        result = worker.run_once()
        assert result["state"] == "FAILED" and result["error"] == "PROVIDER_HTTP_404"
        request = json.loads(
            next(
                row[0]
                for row in store.connect().execute(
                    "SELECT input_json FROM jobs WHERE request_id=?",
                    (plan["jobs"][0]["requestId"],),
                )
            )
        )
        from nunti.characters.models import sha

        cached = store.find_clip("a", original["characterId"], sha(request["text"].encode()))
        assert cached is not None
        assert cached["source"] == original["voiceManifest"]["clips"][0]["source"]
        assert store.character("a", original["characterId"])[0] == original
