"""Small transactional SQLite repository. Client ids are scoped to an owner's trip."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .errors import APIError
from .models import instant


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical(value: dict) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


class Store:
    def __init__(self, path: Path, retention_days: int):
        self.path = path
        self.retention_days = retention_days

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        return db

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("Unsupported database schema; migrate before starting")
            db.execute("""CREATE TABLE IF NOT EXISTS trips (
                owner TEXT NOT NULL, trip_id TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                PRIMARY KEY (owner, trip_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS records (
                owner TEXT NOT NULL, trip_id TEXT NOT NULL, kind TEXT NOT NULL,
                record_id TEXT NOT NULL, revision INTEGER, occurred_sort TEXT,
                body TEXT NOT NULL, received_at TEXT NOT NULL,
                PRIMARY KEY (owner, trip_id, kind, record_id),
                FOREIGN KEY (owner, trip_id) REFERENCES trips(owner, trip_id) ON DELETE CASCADE)""")
            db.execute("""CREATE INDEX IF NOT EXISTS timeline_idx ON records
                (owner, trip_id, kind, occurred_sort, record_id)""")
            db.execute("PRAGMA user_version=1")
        self.path.chmod(0o600)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def connection(self):
        db = self.connect()
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def purge_expired(self) -> int:
        with self.transaction() as db:
            count = db.execute("DELETE FROM trips WHERE expires_at <= ?", (now(),)).rowcount
        with self.connection() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return count

    def trip(self, db, owner, trip_id):
        row = db.execute(
            "SELECT * FROM trips WHERE owner=? AND trip_id=? AND expires_at>?",
            (owner, trip_id, now()),
        ).fetchone()
        if row is None:
            raise APIError(404, "trip_not_found", "Trip not found")
        return row

    def create_trip(self, owner, value):
        stamp = now()
        expires = (
            (instant(stamp) + timedelta(days=self.retention_days))
            .isoformat()
            .replace("+00:00", "Z")
        )
        with self.transaction() as db:
            # Expiration does not get extended by writes or retries.
            db.execute("DELETE FROM trips WHERE expires_at <= ?", (stamp,))
            old = db.execute(
                "SELECT * FROM trips WHERE owner=? AND trip_id=?", (owner, value["tripId"])
            ).fetchone()
            if old:
                self.same(old, value, "trip_conflict")
                return self.receipt(value["tripId"], old["created_at"], True)
            db.execute(
                "INSERT INTO trips VALUES (?,?,?,?,?)",
                (
                    owner,
                    value["tripId"],
                    canonical(value),
                    stamp,
                    expires,
                ),
            )
        return self.receipt(value["tripId"], stamp)

    @staticmethod
    def same(row, value, code="id_conflict"):
        if row["body"] != canonical(value):
            raise APIError(409, code, "The identifier already has different content")

    @staticmethod
    def receipt(record_id, stamp, duplicate=False):
        return {
            "id": record_id,
            "status": "duplicate" if duplicate else "stored",
            "receivedAt": stamp,
        }

    @staticmethod
    def record(db, owner, trip_id, kind, record_id):
        return db.execute(
            "SELECT * FROM records WHERE owner=? AND trip_id=? AND kind=? AND record_id=?",
            (owner, trip_id, kind, record_id),
        ).fetchone()

    @staticmethod
    def latest(db, owner, trip_id, kind):
        return db.execute(
            "SELECT * FROM records WHERE owner=? AND trip_id=? AND kind=? "
            "ORDER BY revision DESC, received_at DESC, record_id DESC LIMIT 1",
            (owner, trip_id, kind),
        ).fetchone()

    @staticmethod
    def wrapped(row):
        return {"value": json.loads(row["body"]), "receivedAt": row["received_at"]} if row else None

    def insert(
        self, db, owner, trip_id, kind, record_id, value, revision=None, time_field="occurredAt"
    ):
        stamp = now()
        occurred = value.get(time_field)
        sort_time = instant(occurred).astimezone(UTC).isoformat() if occurred else None
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?,?,?,?)",
            (
                owner,
                trip_id,
                kind,
                record_id,
                revision,
                sort_time,
                canonical(value),
                stamp,
            ),
        )
        return self.receipt(record_id, stamp)

    def put(self, owner, trip_id, kind, value):
        with self.transaction() as db:
            self.trip(db, owner, trip_id)
            if kind == "route":
                record_id = str(value["routeRevision"])
            elif kind == "avatar":
                record_id = f"{value['avatarId']}:{value['routeRevision']}"
            else:
                record_id = trip_id
            old = self.record(db, owner, trip_id, kind, record_id)
            if old:
                self.same(old, value, f"{kind}_conflict")
                return self.receipt(record_id, old["received_at"], True)
            latest_route = self.latest(db, owner, trip_id, "route")
            if kind == "route" and latest_route:
                if value["routeRevision"] <= latest_route["revision"]:
                    raise APIError(409, "route_revision_conflict", "Use a higher routeRevision")
            if kind == "avatar":
                if not latest_route:
                    raise APIError(409, "route_required", "Synchronize the route first")
                route = json.loads(latest_route["body"])
                if (value["routeId"], value["routeRevision"]) != (
                    route["routeId"],
                    route["routeRevision"],
                ):
                    raise APIError(
                        409, "route_revision_conflict", "Avatar must match the current route"
                    )
            return self.insert(
                db, owner, trip_id, kind, record_id, value, value.get("routeRevision")
            )

    def append(self, owner, trip_id, kind, values):
        receipts = []
        with self.transaction() as db:
            self.trip(db, owner, trip_id)
            for value in values:
                if value["tripId"] != trip_id:
                    raise APIError(409, "trip_id_mismatch", "Payload tripId must match the URL")
                record_id = value["eventId" if kind == "event" else "emotionId"]
                old = self.record(db, owner, trip_id, kind, record_id)
                if old:
                    self.same(old, value)
                    receipts.append(self.receipt(record_id, old["received_at"], True))
                    continue
                if kind == "emotion":
                    avatar = db.execute(
                        "SELECT 1 FROM records WHERE owner=? AND trip_id=? AND kind='avatar' "
                        "AND json_extract(body, '$.avatarId')=? LIMIT 1",
                        (owner, trip_id, value["avatarId"]),
                    ).fetchone()
                    if not avatar:
                        raise APIError(
                            409, "avatar_required", "Synchronize the referenced avatar first"
                        )
                receipts.append(self.insert(db, owner, trip_id, kind, record_id, value))
        return receipts

    def append_telemetry(self, owner, trip_id, kind, id_field, time_field, values):
        """Store app-computed telemetry (samples or score snapshots). Idempotent per record id:
        the same id with the same content is a duplicate; different content is a conflict."""
        receipts = []
        with self.transaction() as db:
            self.trip(db, owner, trip_id)
            for value in values:
                record_id = value[id_field]
                old = self.record(db, owner, trip_id, kind, record_id)
                if old:
                    self.same(old, value)
                    receipts.append(self.receipt(record_id, old["received_at"], True))
                    continue
                receipts.append(
                    self.insert(db, owner, trip_id, kind, record_id, value, time_field=time_field)
                )
        return receipts

    def get_trip(self, owner, trip_id):
        with self.connection() as db:
            db.execute("BEGIN")  # A consistent snapshot across all summary queries.
            trip = self.trip(db, owner, trip_id)
            route = self.latest(db, owner, trip_id, "route")
            avatar = self.latest(db, owner, trip_id, "avatar")
            if avatar and (not route or avatar["revision"] != route["revision"]):
                avatar = None
            counts = dict(
                db.execute(
                    "SELECT kind, count(*) FROM records WHERE owner=? AND trip_id=? GROUP BY kind",
                    (owner, trip_id),
                ).fetchall()
            )
            return {
                "trip": json.loads(trip["body"]),
                "createdAt": trip["created_at"],
                "expiresAt": trip["expires_at"],
                "route": self.wrapped(route),
                "avatar": self.wrapped(avatar),
                "eventCount": counts.get("event", 0),
                "emotionCount": counts.get("emotion", 0),
                "reportAvailable": "report" in counts,
                "sampleCount": counts.get("sample", 0),
                "scoreCount": counts.get("score", 0),
            }

    def timeline(self, owner, trip_id, kind, offset, limit):
        with self.connection() as db:
            db.execute("BEGIN")
            self.trip(db, owner, trip_id)
            rows = db.execute(
                "SELECT * FROM records WHERE owner=? AND trip_id=? AND kind=? "
                "ORDER BY occurred_sort, record_id LIMIT ? OFFSET ?",
                (owner, trip_id, kind, limit + 1, offset),
            ).fetchall()
            return {
                "items": [self.wrapped(row) for row in rows[:limit]],
                "nextOffset": offset + limit if len(rows) > limit else None,
            }

    def get_report(self, owner, trip_id):
        with self.connection() as db:
            db.execute("BEGIN")
            self.trip(db, owner, trip_id)
            row = self.record(db, owner, trip_id, "report", trip_id)
            if not row:
                raise APIError(404, "report_not_found", "Report not found")
            result = self.wrapped(row)
            result["unresolvedEvidenceEventIds"] = [
                event_id
                for event_id in result["value"]["evidenceEventIds"]
                if not self.record(db, owner, trip_id, "event", event_id)
            ]
            return result

    def delete_trip(self, owner, trip_id):
        with self.transaction() as db:
            db.execute("DELETE FROM trips WHERE owner=? AND trip_id=?", (owner, trip_id))
        return {"tripId": trip_id, "deleted": True}
