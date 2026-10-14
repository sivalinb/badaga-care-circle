import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from .config import ROOT


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript("""
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS households(id TEXT PRIMARY KEY, label_en TEXT, label_ta TEXT);
              CREATE TABLE IF NOT EXISTS members(id TEXT PRIMARY KEY, household_id TEXT, label_en TEXT, label_ta TEXT, age INTEGER);
              CREATE TABLE IF NOT EXISTS checkins(id TEXT PRIMARY KEY, household_id TEXT, member_id TEXT, systolic INTEGER, diastolic INTEGER, created_at TEXT, status TEXT);
              CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, household_id TEXT, kind TEXT, helper_id TEXT, due_date TEXT, status TEXT, created_at TEXT);
              CREATE TABLE IF NOT EXISTS backup(household_id TEXT PRIMARY KEY, payload TEXT, practised INTEGER, updated_at TEXT);
              CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, household_id TEXT, kind TEXT, reason TEXT, payload TEXT, status TEXT, notes TEXT, created_at TEXT, reviewed_at TEXT);
              CREATE TABLE IF NOT EXISTS traces(id TEXT PRIMARY KEY, created_at TEXT, route TEXT, language TEXT, provider TEXT, status TEXT, latency_ms REAL, input_tokens INTEGER, output_tokens INTEGER, metadata TEXT);
              CREATE TABLE IF NOT EXISTS audits(id TEXT PRIMARY KEY, household_id TEXT, actor_role TEXT, action TEXT, record_id TEXT, created_at TEXT);
            """)
        os.chmod(path, 0o600)
        self.seed()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, sql, params=()):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def seed(self):
        data = json.loads((ROOT / "data" / "households.json").read_text(encoding="utf-8"))
        with self.connection() as conn:
            for home in data:
                conn.execute("INSERT OR IGNORE INTO households VALUES(?,?,?)", (home["id"], home["label_en"], home["label_ta"]))
                for member in home["members"]:
                    conn.execute("INSERT OR IGNORE INTO members VALUES(?,?,?,?,?)", (member["id"], home["id"], member["label_en"], member["label_ta"], member["age"]))

    def authorise(self, actor, household_id, *, clinical=False):
        if actor.role not in {"participant", "volunteer", "clinician"}:
            raise PermissionError("permission")
        if not self.query("SELECT id FROM households WHERE id=?", (household_id,)):
            raise PermissionError("permission")
        if actor.role != "clinician" and actor.household_id != household_id:
            raise PermissionError("permission")
        if clinical and actor.role == "volunteer":
            raise PermissionError("permission")

    def households(self):
        return self.query("SELECT * FROM households ORDER BY id")

    def members(self, actor, household_id):
        self.authorise(actor, household_id)
        return self.query("SELECT * FROM members WHERE household_id=? ORDER BY id", (household_id,))

    def checkins(self, actor, household_id):
        self.authorise(actor, household_id, clinical=True)
        return self.query("SELECT * FROM checkins WHERE household_id=? ORDER BY created_at DESC", (household_id,))

    def add_checkin(self, actor, household_id, member_id, systolic, diastolic, *, review_reason=None, language="en", source_ids=()):
        self.authorise(actor, household_id, clinical=True)
        if member_id not in {m["id"] for m in self.members(actor, household_id)}:
            raise PermissionError("permission")
        identifier = "BP-" + uuid4().hex[:10]
        with self.connection() as conn:
            conn.execute("INSERT INTO checkins VALUES(?,?,?,?,?,?,?)", (identifier, household_id, member_id, systolic, diastolic, utcnow(), "pending"))
            if review_reason:
                self._insert_review(conn, household_id, "clinical", review_reason, {
                    "checkin_id": identifier, "member_id": member_id, "systolic": systolic,
                    "diastolic": diastolic, "language": language, "source_ids": list(source_ids),
                })
            conn.execute("INSERT INTO audits VALUES(?,?,?,?,?,?)", (uuid4().hex, household_id, actor.role, "checkin_created", identifier, utcnow()))
        return identifier

    def _insert_review(self, conn, household_id, kind, reason, payload):
        identifier = "REV-" + uuid4().hex[:10]
        conn.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)", (identifier, household_id, kind, reason, json.dumps(payload, ensure_ascii=False), "pending", "", utcnow(), None))
        return identifier

    def add_review(self, household_id, kind, reason, payload):
        with self.connection() as conn:
            return self._insert_review(conn, household_id, kind, reason, payload)

    def reviews(self, actor):
        if actor.role != "clinician":
            raise PermissionError("permission")
        return self.query("SELECT * FROM reviews ORDER BY created_at DESC LIMIT 100")

    def review_item(self, actor, identifier):
        rows = self.query("SELECT * FROM reviews WHERE id=?", (identifier,))
        if not rows:
            raise ValueError("not_found")
        row = rows[0]
        self.authorise(actor, row["household_id"], clinical=True)
        row["payload"] = json.loads(row["payload"])
        return row

    def decide_review(self, actor, identifier, decision, notes):
        if actor.role != "clinician":
            raise PermissionError("permission")
        row = self.review_item(actor, identifier)
        allowed = {"approve", "reject"} if row["kind"] == "education" else {"followup", "close"}
        if decision not in allowed:
            raise ValueError("wrong_decision")
        if not notes.strip():
            raise ValueError("note_required")
        status = {"approve": "approved", "reject": "rejected", "followup": "followup", "close": "completed"}[decision]
        with self.connection() as conn:
            conn.execute("UPDATE reviews SET status=?, notes=?, reviewed_at=? WHERE id=?", (status, notes, utcnow(), identifier))
            if decision == "close" and row["payload"].get("checkin_id"):
                conn.execute("UPDATE checkins SET status='completed' WHERE id=?", (row["payload"]["checkin_id"],))
        self.audit(actor, row["household_id"], "review_" + status, identifier)

    def tasks(self, actor, household_id):
        self.authorise(actor, household_id)
        return self.query("SELECT * FROM tasks WHERE household_id=? ORDER BY created_at DESC", (household_id,))

    def add_task(self, actor, household_id, kind, helper_id, due_date):
        self.authorise(actor, household_id)
        if helper_id not in {m["id"] for m in self.members(actor, household_id)}:
            raise PermissionError("permission")
        identifier = "TASK-" + uuid4().hex[:10]
        with self.connection() as conn:
            conn.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?)", (identifier, household_id, kind, helper_id, due_date, "requested", utcnow()))
        self.audit(actor, household_id, "task_created", identifier)
        return identifier

    def update_task(self, actor, household_id, identifier, status):
        self.authorise(actor, household_id)
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=? AND household_id=?", (identifier, household_id)).fetchone()
            if not row:
                raise ValueError("not_found")
            allowed = {"requested": {"accepted"}, "accepted": {"completed"}, "completed": set()}
            if status not in allowed[row["status"]]:
                raise ValueError("task_transition")
            conn.execute("UPDATE tasks SET status=? WHERE id=? AND household_id=?", (status, identifier, household_id))
        self.audit(actor, household_id, "task_" + status, identifier)

    def backup(self, actor, household_id):
        self.authorise(actor, household_id, clinical=True)
        rows = self.query("SELECT * FROM backup WHERE household_id=?", (household_id,))
        return json.loads(rows[0]["payload"]) if rows else None

    def save_backup(self, actor, household_id, payload):
        self.authorise(actor, household_id, clinical=True)
        allowed = {m["id"] for m in self.members(actor, household_id)}
        if len(set(payload["people"])) != 2 or not set(payload["people"]).issubset(allowed):
            raise ValueError("backup_two")
        with self.connection() as conn:
            conn.execute("INSERT INTO backup VALUES(?,?,?,?) ON CONFLICT(household_id) DO UPDATE SET payload=excluded.payload,practised=excluded.practised,updated_at=excluded.updated_at", (household_id, json.dumps(payload, ensure_ascii=False), int(payload["practised"]), utcnow()))
        self.audit(actor, household_id, "backup_saved", household_id)

    def audit(self, actor, household_id, action, record_id):
        with self.connection() as conn:
            conn.execute("INSERT INTO audits VALUES(?,?,?,?,?,?)", (uuid4().hex, household_id, actor.role, action, record_id, utcnow()))

    def trace(self, identifier, *, route, language, provider, status, latency_ms, input_tokens=0, output_tokens=0, metadata=None):
        # Strict allowlist: never serialise arbitrary input, provider exception text or PHI.
        metadata = metadata or {}
        allowed = {"rule_version", "source_ids", "retrieval_mode", "fallback_reason", "stage_ms", "source_version"}
        safe = {key: value for key, value in metadata.items() if key in allowed}
        with self.connection() as conn:
            conn.execute("INSERT INTO traces VALUES(?,?,?,?,?,?,?,?,?,?)", (identifier, utcnow(), route, language, provider, status, latency_ms, int(input_tokens or 0), int(output_tokens or 0), json.dumps(safe)))

    def traces(self, actor):
        if actor.role != "clinician":
            raise PermissionError("permission")
        return self.query("SELECT * FROM traces ORDER BY created_at DESC LIMIT 40")

    def metrics(self, actor):
        if actor.role != "clinician":
            raise PermissionError("permission")
        rows = self.query("SELECT latency_ms,provider,status,input_tokens,output_tokens FROM traces ORDER BY created_at DESC LIMIT 1000")
        latencies = sorted(r["latency_ms"] for r in rows)
        from collections import Counter
        return {"window": "latest 1000 requests", "requests": len(rows),
                "p95_latency_ms": latencies[min(len(latencies)-1, int(len(latencies)*0.95))] if rows else None,
                "input_tokens_including_embeddings": sum(r["input_tokens"] for r in rows),
                "output_tokens": sum(r["output_tokens"] for r in rows),
                "providers": dict(Counter(r["provider"] for r in rows)),
                "statuses": dict(Counter(r["status"] for r in rows))}

    def counts(self):
        counts = {}
        for key, query in {
            "households": "SELECT COUNT(*) AS n FROM households",
            "reviews": "SELECT COUNT(*) AS n FROM reviews WHERE status IN ('pending','followup')",
            "tasks": "SELECT COUNT(*) AS n FROM tasks WHERE status='completed'",
            "backups": "SELECT COUNT(*) AS n FROM backup WHERE practised=1",
        }.items():
            counts[key] = self.query(query)[0]["n"]
        return counts
