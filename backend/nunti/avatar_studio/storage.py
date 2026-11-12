"""Owner-scoped immutable media and request outcomes in an independent SQLite store."""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from .models import canonical, digest


class StudioError(ValueError):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


class StudioStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.media = self.root / "media"
        self.media.mkdir(exist_ok=True, mode=0o700)
        self.db = self.root / "studio.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS assets (
                    owner TEXT NOT NULL, sha TEXT NOT NULL, mime TEXT NOT NULL,
                    size INTEGER NOT NULL, PRIMARY KEY(owner,sha));
                CREATE TABLE IF NOT EXISTS extractions (
                    owner TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(owner,id));
                CREATE TABLE IF NOT EXISTS requests (
                    owner TEXT NOT NULL, id TEXT NOT NULL, input_sha TEXT NOT NULL,
                    input_json TEXT NOT NULL, state TEXT NOT NULL, artifact TEXT, error TEXT,
                    reserved_micros INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(owner,id));
                CREATE TABLE IF NOT EXISTS characters (
                    owner TEXT NOT NULL, id TEXT NOT NULL, artifact TEXT NOT NULL,
                    PRIMARY KEY(owner,id));
                CREATE TABLE IF NOT EXISTS provider_responses (
                    owner TEXT NOT NULL, id TEXT NOT NULL, sha TEXT NOT NULL,
                    PRIMARY KEY(owner,id));
            """)
            # A previous process may have crossed a paid side-effect boundary. Never repeat it.
            db.execute(
                "UPDATE requests SET state='FAILED', error='RESULT_UNKNOWN' WHERE state='RUNNING'"
            )
        os.chmod(self.db, 0o600)

    def connect(self):
        db = sqlite3.connect(self.db, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def existing(row, body):
        if row["input_sha"] != digest(body.encode()):
            raise StudioError("REQUEST_INPUT_CONFLICT", 409)
        if row["state"] == "READY":
            return json.loads(row["artifact"])
        raise StudioError(row["error"] or "REQUEST_IN_PROGRESS", 409)

    def previous(self, owner, value):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM requests WHERE owner=? AND id=?", (owner, value["requestId"])
            ).fetchone()
        return self.existing(row, canonical(value)) if row else None

    def claim(self, owner, value, reserved=0, cap=0, limit=20):
        body = canonical(value)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM requests WHERE owner=? AND id=?", (owner, value["requestId"])
            ).fetchone()
            if row:
                return self.existing(row, body)
            if reserved:
                budget = db.execute(
                    "SELECT COALESCE(SUM(reserved_micros),0),COUNT(*) "
                    "FROM requests WHERE reserved_micros>0"
                ).fetchone()
                if budget[0] + reserved > cap or budget[1] >= limit:
                    raise StudioError("IMAGE_API_BUDGET_REACHED", 409)
            db.execute(
                "INSERT INTO requests(owner,id,input_sha,input_json,state,reserved_micros) "
                "VALUES(?,?,?,?,?,?)",
                (owner, value["requestId"], digest(body.encode()), body, "RUNNING", reserved),
            )
        return None

    def complete(self, owner, request_id, artifact):
        body = canonical(artifact)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO characters VALUES(?,?,?)", (owner, artifact["characterId"], body)
            )
            db.execute(
                "UPDATE requests SET state='READY',artifact=? WHERE owner=? AND id=?",
                (body, owner, request_id),
            )

    def fail(self, owner, request_id, code):
        with self.connect() as db:
            db.execute(
                "UPDATE requests SET state='FAILED',error=? WHERE owner=? AND id=?",
                (code, owner, request_id),
            )

    def put_provider_response(self, owner, request_id, content):
        sha = self.put_asset(owner, content, "application/json")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT sha FROM provider_responses WHERE owner=? AND id=?", (owner, request_id)
            ).fetchone()
            if previous is not None and previous["sha"] != sha:
                raise StudioError("PROVIDER_RESPONSE_CHANGED", 409)
            db.execute(
                "INSERT OR IGNORE INTO provider_responses VALUES(?,?,?)", (owner, request_id, sha)
            )

    def provider_response(self, owner, request_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT sha FROM provider_responses WHERE owner=? AND id=?", (owner, request_id)
            ).fetchone()
        if row is None:
            raise StudioError("PROVIDER_RESPONSE_NOT_FOUND", 404)
        return self.asset(owner, row["sha"])[0]

    def put_asset(self, owner, content, mime):
        sha = digest(content)
        folder = self.media / owner
        folder.mkdir(exist_ok=True, mode=0o700)
        path = folder / sha
        if path.exists():
            if digest(path.read_bytes()) != sha:
                raise StudioError("SAVED_MEDIA_CHANGED", 409)
        else:
            fd, name = tempfile.mkstemp(dir=folder)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO assets VALUES(?,?,?,?)", (owner, sha, mime, len(content))
            )
        return sha

    def asset(self, owner, sha):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM assets WHERE owner=? AND sha=?", (owner, sha)
            ).fetchone()
        if row is None:
            raise StudioError("ASSET_NOT_FOUND", 404)
        path = self.media / owner / sha
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise StudioError("SAVED_MEDIA_MISSING", 409) from exc
        if len(content) != row["size"] or digest(content) != sha:
            raise StudioError("SAVED_MEDIA_CHANGED", 409)
        return content, row["mime"]

    def put_extraction(self, owner, value):
        with self.connect() as db:
            db.execute(
                "INSERT INTO extractions VALUES(?,?,?)",
                (owner, value["extractionId"], canonical(value)),
            )

    def extraction(self, owner, extraction_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM extractions WHERE owner=? AND id=?", (owner, extraction_id)
            ).fetchone()
        if row is None:
            raise StudioError("EXTRACTION_NOT_FOUND", 404)
        return json.loads(row[0])

    def avatars(self, owner):
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT artifact FROM characters WHERE owner=? ORDER BY rowid DESC", (owner,)
                )
            ]

    def avatar(self, owner, character_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT artifact FROM characters WHERE owner=? AND id=?", (owner, character_id)
            ).fetchone()
        if row is None:
            raise StudioError("CHARACTER_NOT_FOUND", 404)
        return json.loads(row[0])
