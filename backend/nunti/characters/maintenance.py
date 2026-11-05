"""Plan or enqueue Google voice renewal; provider calls only run in the durable worker."""

import argparse
from contextlib import closing
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from ..config import Settings
from .models import canonical
from .store import CharacterStore


def plan_renewals(store, now=None, days=90):
    now = now or datetime.now(UTC)
    threshold = now + timedelta(days=days)
    renewals, unknown = [], []
    with closing(store.connect()) as db:
        rows = db.execute("SELECT owner,character_id FROM characters").fetchall()
    for row in rows:
        artifact, binding = store.character(row["owner"], row["character_id"])
        if binding["source"]["providerId"] != "gemini-designed":
            continue
        expiry = store.operations(row["owner"], row["character_id"]).get("expireTime")
        if not expiry:
            unknown.append({"characterId": artifact["characterId"], "voiceId": binding["voiceId"]})
            continue
        expires = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            raise ValueError("PROVIDER_EXPIRY_TIMEZONE_REQUIRED")
        if expires <= threshold:
            renewals.append(
                {
                    "owner": row["owner"],
                    "characterId": artifact["characterId"],
                    "voiceId": binding["voiceId"],
                    "lastObservedExpireTime": expiry,
                    "expired": expires <= now,
                    "pipeline": binding["pipeline"],
                    "wouldPost": "/v2/characters/" + artifact["characterId"] + "/speech",
                    "period": now.strftime("%Y-%m"),
                    "wouldRequest": {
                        "requestId": str(
                            uuid5(
                                NAMESPACE_URL,
                                "nunti-voice-renewal:"
                                + row["owner"]
                                + ":"
                                + artifact["characterId"]
                                + ":"
                                + now.strftime("%Y-%m"),
                            )
                        ),
                        "text": f"{now.year}년 {now.month}월에도 천천히 함께 가자.",
                    },
                    "characterMode": artifact["mode"],
                }
            )
    return {
        "mode": "DRY_RUN",
        "providerRequests": 0,
        "jobsSubmitted": 0,
        "windowDays": days,
        "renewals": renewals,
        "unknownExpiryVoices": unknown,
        "executed": False,
        "expiryIsLastObservedNotCurrentProviderQuery": True,
        "liveRenewalVerified": False,
    }


def enqueue_due(store, now=None):
    plan = plan_renewals(store, now=now)
    jobs, skipped = [], []
    for renewal in plan["renewals"]:
        if renewal["characterMode"] != "API":
            skipped.append(
                {"characterId": renewal["characterId"], "reason": "FIXTURE_NOT_RENEWABLE"}
            )
            continue
        view = store.submit(
            renewal["owner"],
            renewal["wouldRequest"],
            "API",
            renewal["characterId"],
            maintenance_period=renewal["period"],
        )
        jobs.append(store.get_job(renewal["owner"], view["requestId"]))
    return {
        "mode": "ENQUEUE_ONLY",
        "providerRequests": 0,
        "executed": False,
        "jobs": jobs,
        "skipped": skipped,
        "liveRenewalVerified": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="List stored Google voices expiring within 90 days, without network"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--enqueue-due", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    store = CharacterStore(
        settings.character_db_path or settings.db_path.parent / "characters-v2.sqlite3",
        settings.character_media_path or settings.db_path.parent / "characters-v2-media",
    )
    if not store.path.is_file():
        raise ValueError("CHARACTER_DATABASE_REQUIRED")
    print(canonical(enqueue_due(store) if args.enqueue_due else plan_renewals(store)))


if __name__ == "__main__":
    main()
