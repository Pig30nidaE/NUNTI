"""Executable reference for Android sync behavior, not an Android implementation.

Persist before sending; delete only after acknowledgment. An uncertain response
keeps the original payload and identifiers. Local emotion/TTS never waits here.
"""

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import httpx


class DemoOutbox:
    def __init__(self, path: Path, *, consent: bool = False):
        self.path = path
        self.consent = consent
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS pending (
                seq INTEGER PRIMARY KEY, request_key TEXT UNIQUE, method TEXT, path TEXT,
                body TEXT, attempts INTEGER DEFAULT 0, due REAL DEFAULT 0,
                blocked INTEGER DEFAULT 0)""")
        path.chmod(0o600)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        return db

    def enqueue(self, key, method, path, body):
        if not self.consent:
            return False
        payload = json.dumps(body, sort_keys=True, ensure_ascii=False)
        with closing(self.connect()) as db, db:
            old = db.execute("SELECT * FROM pending WHERE request_key=?", (key,)).fetchone()
            if old:
                if (old["method"], old["path"], old["body"]) != (method, path, payload):
                    raise ValueError("Outbox identifier conflicts with existing content")
                return True
            db.execute(
                "INSERT INTO pending (request_key,method,path,body) VALUES (?,?,?,?)",
                (key, method, path, payload),
            )
        return True

    def revoke_consent(self):
        self.consent = False
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM pending")

    def pending_count(self):
        with closing(self.connect()) as db:
            return db.execute("SELECT count(*) FROM pending").fetchone()[0]

    def pump_once(self, sender, *, at=None):
        if not self.consent:
            return "disabled"
        at = time.time() if at is None else at
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM pending ORDER BY seq LIMIT 1").fetchone()
        if not row:
            return "empty"
        if row["blocked"]:
            return "blocked"
        if row["due"] > at:
            return "waiting"
        try:
            response = sender(row["method"], row["path"], json=json.loads(row["body"]))
            status = response.status_code
        except (httpx.TransportError, OSError):
            status = 503
        with closing(self.connect()) as db, db:
            if 200 <= status < 300:
                db.execute("DELETE FROM pending WHERE seq=?", (row["seq"],))
                return "acknowledged"
            if status in (408, 429) or status >= 500:
                delay = min(120, 2 ** min(row["attempts"], 7))
                db.execute(
                    "UPDATE pending SET attempts=attempts+1,due=? WHERE seq=?",
                    (at + delay, row["seq"]),
                )
                return "retry"
            # Conflicts, authentication and invalid contracts require intervention.
            db.execute("UPDATE pending SET blocked=1 WHERE seq=?", (row["seq"],))
            return "blocked"
