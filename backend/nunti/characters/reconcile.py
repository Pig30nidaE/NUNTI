"""Offline billing evidence reconciliation. Never imports or calls a provider adapter."""

import argparse
import json
import time
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from ..config import Settings
from .models import GenerationInput, Strict, bounded_text, canonical
from .store import CharacterStore


class Charge(Strict):
    name: str = Field(min_length=1, max_length=120)
    actualMicros: int = Field(ge=0)
    providerRequestId: str = Field(min_length=1, max_length=200)
    evidenceReference: str = Field(min_length=1, max_length=1000)

    @field_validator("providerRequestId", "evidenceReference")
    @classmethod
    def nonblank_reference(cls, value):
        return bounded_text(value, 1000, True)


class Reconciliation(Strict):
    owner: str = Field(min_length=1, max_length=128)
    requestId: str
    steps: list[Charge] = Field(min_length=1, max_length=100)
    _uuid = field_validator("requestId")(GenerationInput.uuid.__func__)

    @model_validator(mode="after")
    def unique_steps(self):
        if len({step.name for step in self.steps}) != len(self.steps):
            raise ValueError("DUPLICATE_RECONCILIATION_STEP")
        return self


def reconcile(store, value):
    value = Reconciliation.model_validate(value)
    with store.transaction() as db:
        job = db.execute(
            "SELECT * FROM jobs WHERE owner=? AND request_id=?", (value.owner, value.requestId)
        ).fetchone()
        if job is None:
            raise ValueError("RECONCILIATION_JOB_NOT_FOUND")
        for charge in value.steps:
            step = db.execute(
                "SELECT * FROM steps WHERE owner=? AND request_id=? AND name=?",
                (value.owner, value.requestId, charge.name),
            ).fetchone()
            if not step or step["state"] != "DONE":
                raise ValueError("RECONCILIATION_REQUIRES_DONE_STEP")
            if job["mode"] == "OFFLINE_FIXTURE" and charge.actualMicros != 0:
                raise ValueError("FIXTURE_CANNOT_HAVE_PROVIDER_CHARGE")
            if step["actual_micros"] is not None and step["actual_micros"] != charge.actualMicros:
                raise ValueError("CONFIRMED_CHARGE_CANNOT_CHANGE")
            old = db.execute(
                "SELECT * FROM billing_reconciliations WHERE owner=? AND request_id=? AND name=?",
                (value.owner, value.requestId, charge.name),
            ).fetchone()
            if old and (
                old["actual_micros"],
                old["provider_request_id"],
                old["evidence_reference"],
            ) != (charge.actualMicros, charge.providerRequestId, charge.evidenceReference):
                raise ValueError("CONFIRMED_BILLING_EVIDENCE_CANNOT_CHANGE")
            db.execute(
                "INSERT OR IGNORE INTO billing_reconciliations VALUES(?,?,?,?,?,?,?)",
                (
                    value.owner,
                    value.requestId,
                    charge.name,
                    charge.actualMicros,
                    charge.providerRequestId,
                    charge.evidenceReference,
                    time.time(),
                ),
            )
            db.execute(
                "UPDATE steps SET actual_micros=?,provider_request_id=? "
                "WHERE owner=? AND request_id=? AND name=?",
                (
                    charge.actualMicros,
                    charge.providerRequestId,
                    value.owner,
                    value.requestId,
                    charge.name,
                ),
            )
    result = store.get_job(value.owner, value.requestId)
    return {
        "requestId": value.requestId,
        "reconciledSteps": [step.name for step in value.steps],
        "cost": result["cost"],
        "providerRequests": 0,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Record actual charges from account receipts, offline"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings.from_env()
    store = CharacterStore(
        settings.character_db_path or settings.db_path.parent / "characters-v2.sqlite3",
        settings.character_media_path or settings.db_path.parent / "characters-v2-media",
        job_cap=settings.generation_job_cap_micros,
        total_cap=settings.generation_total_cap_micros,
        voice_capacity=settings.generation_voice_capacity,
    )
    store.initialize()
    result = reconcile(store, json.loads(args.input.read_text()))
    encoded = canonical(result) + "\n"
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
