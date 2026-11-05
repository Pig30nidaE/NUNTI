"""SQLite job claims, immutable collectibles, media grants and conservative cost reservations.

No foreign key points to v1 trips. Paid requests whose outcome is unknown are
never replayed automatically, including after a worker lease expires.
"""

import json
import re
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path

from ..errors import APIError
from .models import canonical, sha


class CharacterStore:
    def __init__(
        self,
        path: Path,
        media: Path,
        *,
        job_cap=300000,
        total_cap=6000000,
        initial_limit=20,
        voice_capacity=30,
    ):
        self.path, self.media = Path(path), Path(media)
        self.job_cap, self.total_cap = job_cap, total_cap
        self.initial_limit, self.voice_capacity = initial_limit, voice_capacity

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.media.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 2):
                raise RuntimeError("Unsupported character database schema")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs(
                    owner TEXT NOT NULL, request_id TEXT NOT NULL, job_id TEXT NOT NULL,
                    kind TEXT NOT NULL, character_id TEXT, input_json TEXT NOT NULL,
                    input_sha TEXT NOT NULL, mode TEXT NOT NULL, state TEXT NOT NULL,
                    stage TEXT NOT NULL, error TEXT, result_json TEXT,
                    lease_owner TEXT, lease_until REAL, created REAL NOT NULL,
                    PRIMARY KEY(owner,request_id));
                CREATE TABLE IF NOT EXISTS characters(
                    owner TEXT NOT NULL, character_id TEXT NOT NULL,
                    artifact_json TEXT NOT NULL, binding_json TEXT NOT NULL,
                    PRIMARY KEY(owner,character_id));
                CREATE TABLE IF NOT EXISTS assets(
                    owner TEXT NOT NULL, sha TEXT NOT NULL, mime TEXT NOT NULL,
                    byte_length INTEGER NOT NULL, PRIMARY KEY(owner,sha));
                CREATE TABLE IF NOT EXISTS steps(
                    owner TEXT NOT NULL, request_id TEXT NOT NULL, name TEXT NOT NULL,
                    request_sha TEXT NOT NULL, state TEXT NOT NULL,
                    result_json TEXT, reserved_micros INTEGER NOT NULL,
                    actual_micros INTEGER, provider_request_id TEXT,
                    PRIMARY KEY(owner,request_id,name));
                CREATE TABLE IF NOT EXISTS voices(
                    owner TEXT NOT NULL, character_id TEXT NOT NULL,
                    provider TEXT NOT NULL, voice_id TEXT, state TEXT NOT NULL,
                    PRIMARY KEY(owner,character_id));
                CREATE TABLE IF NOT EXISTS worker_lock(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    holder TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS character_seals(
                    owner TEXT NOT NULL,character_id TEXT NOT NULL,digest TEXT NOT NULL,
                    PRIMARY KEY(owner,character_id));
                CREATE TABLE IF NOT EXISTS provider_receipts(
                    owner TEXT NOT NULL,request_id TEXT NOT NULL,step TEXT NOT NULL,
                    audit_json TEXT NOT NULL,PRIMARY KEY(owner,request_id,step));
                CREATE TABLE IF NOT EXISTS billing_reconciliations(
                    owner TEXT NOT NULL,request_id TEXT NOT NULL,name TEXT NOT NULL,
                    actual_micros INTEGER NOT NULL,provider_request_id TEXT NOT NULL,
                    evidence_reference TEXT NOT NULL,recorded REAL NOT NULL,
                    PRIMARY KEY(owner,request_id,name));
                CREATE TABLE IF NOT EXISTS voice_operations(
                    owner TEXT NOT NULL,character_id TEXT NOT NULL,voice_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,PRIMARY KEY(owner,character_id));
                CREATE TABLE IF NOT EXISTS maintenance_jobs(
                    owner TEXT NOT NULL,request_id TEXT NOT NULL,character_id TEXT NOT NULL,
                    period TEXT NOT NULL,PRIMARY KEY(owner,request_id));
                CREATE TABLE IF NOT EXISTS voice_clips(
                    owner TEXT NOT NULL,character_id TEXT NOT NULL,text_sha TEXT NOT NULL,
                    clip_json TEXT NOT NULL,clip_sha TEXT NOT NULL,
                    PRIMARY KEY(owner,character_id,text_sha));
                PRAGMA user_version=2;
            """)
        self.path.chmod(0o600)
        with closing(self.connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")

    def submit(self, owner, value, mode, character_id=None, maintenance_period=None):
        request_id = value["requestId"]
        encoded = canonical(value)
        digest = sha(encoded.encode())
        kind = "SPEECH" if character_id else "CHARACTER"
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE owner=? AND request_id=?", (owner, request_id)
            ).fetchone()
            if row:
                if (row["input_sha"], row["kind"], row["character_id"]) != (
                    digest,
                    kind,
                    character_id,
                ):
                    raise APIError(
                        409, "request_conflict", "Request ID is bound to different input"
                    )
                return self._view(row)
            if (
                kind == "CHARACTER"
                and db.execute("SELECT count(*) FROM jobs WHERE kind='CHARACTER'").fetchone()[0]
                >= self.initial_limit
            ):
                raise APIError(409, "initial_batch_limit", "Initial character batch limit reached")
            if (
                character_id
                and not db.execute(
                    "SELECT 1 FROM characters WHERE owner=? AND character_id=?",
                    (owner, character_id),
                ).fetchone()
            ):
                raise APIError(404, "character_not_found", "Character not found")
            db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    owner,
                    request_id,
                    request_id,
                    kind,
                    character_id,
                    encoded,
                    digest,
                    mode,
                    "QUEUED",
                    "SPEECH" if character_id else "PLANNING",
                    None,
                    None,
                    None,
                    None,
                    time.time(),
                ),
            )
            if maintenance_period:
                db.execute(
                    "INSERT INTO maintenance_jobs VALUES(?,?,?,?)",
                    (owner, request_id, character_id, maintenance_period),
                )
            return self._view(
                db.execute(
                    "SELECT * FROM jobs WHERE owner=? AND request_id=?", (owner, request_id)
                ).fetchone()
            )

    @staticmethod
    def _view(row):
        result = {
            "jobId": row["job_id"],
            "requestId": row["request_id"],
            "state": row["state"],
            "stage": row["stage"],
            "mode": row["mode"],
            "error": row["error"],
        }
        if row["result_json"]:
            result["speechManifest" if row["kind"] == "SPEECH" else "artifact"] = json.loads(
                row["result_json"]
            )
        return result

    def get_job(self, owner, request_id):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE owner=? AND request_id=?", (owner, request_id)
            ).fetchone()
            costs = db.execute(
                "SELECT reserved_micros,actual_micros FROM steps WHERE owner=? AND request_id=?",
                (owner, request_id),
            ).fetchall()
            global_known = db.execute(
                "SELECT coalesce(sum(actual_micros),0) FROM steps"
            ).fetchone()[0]
        if row is None:
            raise APIError(404, "job_not_found", "Job not found")
        result = self._view(row)
        actual = (
            0
            if row["mode"] == "OFFLINE_FIXTURE"
            or row["kind"] == "SPEECH"
            and row["state"] == "READY"
            and not costs
            else sum(c["actual_micros"] for c in costs)
            if costs and all(c["actual_micros"] is not None for c in costs)
            else None
        )
        result["cost"] = {
            "reservedMicros": sum(c["reserved_micros"] for c in costs),
            "actualMicros": actual,
            "complete": row["state"] == "READY" and actual is not None,
            "currency": "USD",
            "pricingVersion": "2026-11-03",
            "knownActualMicros": sum(c["actual_micros"] or 0 for c in costs),
            "overBudget": sum(c["actual_micros"] or 0 for c in costs) > self.job_cap
            or global_known > self.total_cap,
            "overReservation": any(
                c["actual_micros"] is not None and c["actual_micros"] > c["reserved_micros"]
                for c in costs
            ),
        }
        return result

    def character(self, owner, character_id):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM characters WHERE owner=? AND character_id=?", (owner, character_id)
            ).fetchone()
            seal = db.execute(
                "SELECT digest FROM character_seals WHERE owner=? AND character_id=?",
                (owner, character_id),
            ).fetchone()
        if row is None:
            raise APIError(404, "character_not_found", "Character not found")
        if not seal or sha((row["artifact_json"] + "\n" + row["binding_json"]).encode()) != seal[0]:
            raise APIError(
                503, "character_integrity_failed", "Stored character failed integrity verification"
            )
        artifact, binding = json.loads(row["artifact_json"]), json.loads(row["binding_json"])
        from .models import CharacterArtifact

        CharacterArtifact.model_validate(artifact)
        if sha(canonical(binding["spec"]).encode()) != artifact["specHash"]:
            raise APIError(
                503, "character_integrity_failed", "Stored character failed integrity verification"
            )
        return artifact, binding

    def release_worker(self, holder):
        with self.transaction() as db:
            db.execute("DELETE FROM worker_lock WHERE singleton=1 AND holder=?", (holder,))

    def claim(self, holder, lease_seconds=300, now=None):
        stamp = time.time() if now is None else now
        with self.transaction() as db:
            lock = db.execute("SELECT * FROM worker_lock WHERE singleton=1").fetchone()
            if lock and lock["holder"] != holder and lock["expires"] > stamp:
                return None
            db.execute(
                "INSERT OR REPLACE INTO worker_lock VALUES(1,?,?)", (holder, stamp + lease_seconds)
            )
            # Uncertain paid work cannot safely be repeated after a process died.
            db.execute(
                """UPDATE jobs SET state='RESULT_UNKNOWN',error='PROVIDER_RESULT_UNKNOWN',
                lease_owner=NULL,lease_until=NULL WHERE state='RUNNING' AND lease_until<=?
                AND EXISTS(SELECT 1 FROM steps s WHERE s.owner=jobs.owner
                           AND s.request_id=jobs.request_id
                           AND s.state='CALLING')""",
                (stamp,),
            )
            row = db.execute(
                """SELECT * FROM jobs WHERE state='QUEUED' OR
                (state='RUNNING' AND lease_until<=?) ORDER BY created LIMIT 1""",
                (stamp,),
            ).fetchone()
            if not row:
                return None
            db.execute(
                (
                    "UPDATE jobs SET state='RUNNING',lease_owner=?,lease_until=? WHERE owner=? "
                    "AND request_id=?"
                ),
                (holder, stamp + lease_seconds, row["owner"], row["request_id"]),
            )
            return dict(row) | {"lease_owner": holder, "state": "RUNNING"}

    def heartbeat(self, holder, job, seconds=300):
        with self.transaction() as db:
            stamp = time.time() + seconds
            cursor = db.execute(
                (
                    "UPDATE jobs SET lease_until=? WHERE owner=? AND request_id=? AND lease_own"
                    "er=? AND state='RUNNING'"
                ),
                (stamp, job["owner"], job["request_id"], holder),
            )
            if cursor.rowcount != 1:
                raise ValueError("WORKER_LEASE_LOST")
            db.execute(
                "UPDATE worker_lock SET expires=? WHERE singleton=1 AND holder=?", (stamp, holder)
            )

    def stage(self, job, stage):
        with self.transaction() as db:
            db.execute(
                (
                    "UPDATE jobs SET stage=? WHERE owner=? AND request_id=? AND state='RUNNING'"
                    " AND lease_owner=?"
                ),
                (stage, job["owner"], job["request_id"], job["lease_owner"]),
            )

    def begin_step(self, job, name, request, reserve_micros):
        digest = sha(canonical(request).encode())
        with self.transaction() as db:
            old = db.execute(
                "SELECT * FROM steps WHERE owner=? AND request_id=? AND name=?",
                (job["owner"], job["request_id"], name),
            ).fetchone()
            if old:
                if old["request_sha"] != digest:
                    raise ValueError("PROVIDER_REQUEST_CHANGED")
                if old["state"] == "DONE":
                    return json.loads(old["result_json"])
                raise ValueError("PROVIDER_RESULT_UNKNOWN")
            if reserve_micros < 0:
                raise ValueError("INVALID_PRICE_CONFIGURATION")
            accounted = (
                "CASE WHEN actual_micros>reserved_micros "
                "THEN actual_micros ELSE reserved_micros END"
            )
            used = db.execute("SELECT coalesce(sum(" + accounted + "),0) FROM steps").fetchone()[0]
            job_used = db.execute(
                "SELECT coalesce(sum("
                + accounted
                + "),0) FROM steps WHERE owner=? AND request_id=?",
                (job["owner"], job["request_id"]),
            ).fetchone()[0]
            if used + reserve_micros > self.total_cap or job_used + reserve_micros > self.job_cap:
                raise ValueError("BUDGET_CAP_REACHED")
            db.execute(
                "INSERT INTO steps VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    job["owner"],
                    job["request_id"],
                    name,
                    digest,
                    "CALLING",
                    None,
                    reserve_micros,
                    None,
                    None,
                ),
            )
        return None

    def finish_step(self, job, name, result, audit=None):
        with self.transaction() as db:
            actual = (
                0
                if job["mode"] == "OFFLINE_FIXTURE" or name in {"preflight", "voice_refresh_status"}
                else None
            )
            db.execute(
                (
                    "UPDATE steps SET state='DONE',result_json=?,actual_micros=? WHERE owner=? "
                    "AND request_id=? AND name=? AND state='CALLING'"
                ),
                (canonical(result), actual, job["owner"], job["request_id"], name),
            )
            if audit:
                db.execute(
                    "INSERT OR REPLACE INTO provider_receipts VALUES(?,?,?,?)",
                    (job["owner"], job["request_id"], name, canonical(audit)),
                )

    def reserve_voice(self, job, character_id, provider, capacity=None):
        with self.transaction() as db:
            if db.execute(
                "SELECT 1 FROM voices WHERE owner=? AND character_id=?",
                (job["owner"], character_id),
            ).fetchone():
                return
            used = db.execute(
                "SELECT count(*) FROM voices WHERE provider=?", (provider,)
            ).fetchone()[0]
            pending = db.execute(
                "SELECT count(*) FROM voices WHERE provider=? AND state='RESERVED'", (provider,)
            ).fetchone()[0]
            if used >= self.voice_capacity or capacity is not None and pending >= capacity:
                raise ValueError("VOICE_SLOT_CAP_REACHED")
            db.execute(
                "INSERT INTO voices VALUES(?,?,?,?,?)",
                (job["owner"], character_id, provider, None, "RESERVED"),
            )

    def record_voice(self, job, character_id, voice_id):
        """Keep the saved provider voice even if initial speech subsequently fails."""
        with self.transaction() as db:
            old = db.execute(
                "SELECT voice_id FROM voices WHERE owner=? AND character_id=?",
                (job["owner"], character_id),
            ).fetchone()
            if old and old[0] is not None and old[0] != voice_id:
                raise ValueError("SAVED_VOICE_ID_CHANGED")
            db.execute(
                "UPDATE voices SET state='ACTIVE',voice_id=? WHERE owner=? AND character_id=?",
                (voice_id, job["owner"], character_id),
            )

    def operations(self, owner, character_id):
        _, binding = self.character(owner, character_id)
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM voice_operations WHERE owner=? AND character_id=?",
                (owner, character_id),
            ).fetchone()
        if row:
            if row["voice_id"] != binding["voiceId"]:
                raise ValueError("OPERATIONAL_VOICE_ID_CHANGED")
            return json.loads(row["metadata_json"])
        return binding.get("providerOperations", {})

    def record_operations(self, owner, character_id, voice_id, metadata):
        _, binding = self.character(owner, character_id)
        if binding["voiceId"] != voice_id:
            raise ValueError("OPERATIONAL_VOICE_ID_CHANGED")
        with self.transaction() as db:
            db.execute(
                "INSERT OR REPLACE INTO voice_operations VALUES(?,?,?,?)",
                (owner, character_id, voice_id, canonical(metadata)),
            )

    def is_maintenance(self, job):
        with closing(self.connect()) as db:
            return (
                db.execute(
                    "SELECT 1 FROM maintenance_jobs WHERE owner=? AND request_id=?",
                    (job["owner"], job["request_id"]),
                ).fetchone()
                is not None
            )

    def find_clip(self, owner, character_id, text_sha):
        artifact, _ = self.character(owner, character_id)
        candidates = [c for c in artifact["voiceManifest"]["clips"] if c["textSha256"] == text_sha]
        with closing(self.connect()) as db:
            pinned = db.execute(
                "SELECT * FROM voice_clips WHERE owner=? AND character_id=? AND text_sha=?",
                (owner, character_id, text_sha),
            ).fetchone()
            rows = db.execute(
                (
                    "SELECT result_json FROM jobs WHERE owner=? AND character_id=? AND kind='SP"
                    "EECH' AND state='READY'"
                ),
                (owner, character_id),
            ).fetchall()
        if pinned:
            if sha(pinned["clip_json"].encode()) != pinned["clip_sha"]:
                raise ValueError("SAVED_SPEECH_ASSET_CHANGED")
            candidates.append(json.loads(pinned["clip_json"]))
        for row in rows:
            candidates.extend(c for c in json.loads(row[0])["clips"] if c["textSha256"] == text_sha)
        if not candidates:
            return None
        if len({canonical(c) for c in candidates}) != 1:
            raise ValueError("SAVED_SPEECH_ASSET_CHANGED")
        self.asset(owner, candidates[0]["audioSha256"])
        return candidates[0]

    def pin_clip(self, owner, clip):
        encoded = canonical(clip)
        with self.transaction() as db:
            old = db.execute(
                "SELECT clip_json FROM voice_clips WHERE owner=? AND character_id=? AND text_sha=?",
                (owner, clip["characterId"], clip["textSha256"]),
            ).fetchone()
            if old and old[0] != encoded:
                raise ValueError("SAVED_SPEECH_ASSET_CHANGED")
            db.execute(
                "INSERT OR IGNORE INTO voice_clips VALUES(?,?,?,?,?)",
                (owner, clip["characterId"], clip["textSha256"], encoded, sha(encoded.encode())),
            )

    def complete(self, job, result, binding=None):
        encoded = canonical(result)
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE owner=? AND request_id=?",
                (job["owner"], job["request_id"]),
            ).fetchone()
            if row["lease_owner"] != job["lease_owner"] or row["state"] != "RUNNING":
                raise ValueError("WORKER_LEASE_LOST")
            if binding:
                old = db.execute(
                    "SELECT artifact_json FROM characters WHERE owner=? AND character_id=?",
                    (job["owner"], result["characterId"]),
                ).fetchone()
                if old and old[0] != encoded:
                    raise ValueError("SAVED_CHARACTER_CHANGED")
                db.execute(
                    "INSERT OR IGNORE INTO characters VALUES(?,?,?,?)",
                    (job["owner"], result["characterId"], encoded, canonical(binding)),
                )
                db.execute(
                    "INSERT OR IGNORE INTO character_seals VALUES(?,?,?)",
                    (
                        job["owner"],
                        result["characterId"],
                        sha((encoded + "\n" + canonical(binding)).encode()),
                    ),
                )
                db.execute(
                    "UPDATE voices SET voice_id=?,state='ACTIVE' WHERE owner=? AND character_id=?",
                    (binding["voiceId"], job["owner"], result["characterId"]),
                )
            db.execute(
                (
                    "UPDATE jobs SET state='READY',stage='COMPLETE',result_json=?,lease_owner=N"
                    "ULL,lease_until=NULL WHERE owner=? AND request_id=?"
                ),
                (encoded, job["owner"], job["request_id"]),
            )

    def fail(self, job, code, unknown=False):
        if not re.fullmatch(r"[A-Z0-9_]{1,120}", code):
            code = "GENERATION_FAILED"
        with self.transaction() as db:
            db.execute(
                (
                    "UPDATE jobs SET state=?,error=?,lease_owner=NULL,lease_until=NULL WHERE ow"
                    "ner=? AND request_id=? AND lease_owner=?"
                ),
                (
                    "RESULT_UNKNOWN" if unknown else "FAILED",
                    code,
                    job["owner"],
                    job["request_id"],
                    job["lease_owner"],
                ),
            )

    def put_asset(self, owner, data, mime):
        import os
        import tempfile

        digest = sha(data)
        path = self.media / digest
        if path.exists():
            if sha(path.read_bytes()) != digest:
                raise ValueError("COMMITTED_ASSET_CHANGED")
        else:
            fd, temporary = tempfile.mkstemp(prefix=".asset-", dir=self.media)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO assets VALUES(?,?,?,?)", (owner, digest, mime, len(data))
            )
        return digest

    def asset(self, owner, digest):
        if not re.fullmatch("[0-9a-f]{64}", digest):
            raise APIError(404, "asset_not_found", "Asset not found")
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM assets WHERE owner=? AND sha=?", (owner, digest)
            ).fetchone()
        if not row:
            raise APIError(404, "asset_not_found", "Asset not found")
        path = self.media / digest
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != row["byte_length"]
            or sha(path.read_bytes()) != digest
        ):
            raise APIError(
                503, "asset_integrity_failed", "Stored media failed integrity verification"
            )
        return path, row["mime"]
