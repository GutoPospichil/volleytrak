from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from .config import DB_PATH, ensure_dirs
from .constants import learning_example_weight

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    opponent TEXT NOT NULL DEFAULT '',
    played_on TEXT NOT NULL DEFAULT '',
    video_path TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'upload',
    whistle_mode TEXT NOT NULL DEFAULT 'with',
    status TEXT NOT NULL DEFAULT 'uploaded',
    progress REAL NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    calibration TEXT,
    result TEXT,
    annotated_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    number INTEGER,
    team TEXT NOT NULL DEFAULT 'home',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    t REAL NOT NULL,
    kind TEXT NOT NULL,
    player_id INTEGER REFERENCES players(id) ON DELETE SET NULL,
    set_no INTEGER,
    rally_no INTEGER,
    note TEXT NOT NULL DEFAULT '',
    data TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_match ON events(match_id, t);

CREATE TABLE IF NOT EXISTS clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    start REAL NOT NULL,
    end REAL NOT NULL,
    duration REAL NOT NULL,
    path TEXT NOT NULL,
    thumb TEXT,
    score REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    source TEXT NOT NULL DEFAULT 'speed',
    features TEXT,
    saved_score REAL,
    starred INTEGER NOT NULL DEFAULT 0,
    saved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_clips_match ON clips(match_id, start);

CREATE TABLE IF NOT EXISTS clip_rejections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    start REAL NOT NULL,
    end REAL NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    features TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_clip_rejections_match
    ON clip_rejections(match_id, start);

CREATE TABLE IF NOT EXISTS learning_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    start REAL NOT NULL,
    end REAL NOT NULL,
    duration REAL NOT NULL,
    label TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    features TEXT,
    weight REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(match_id, start, end)
);

CREATE INDEX IF NOT EXISTS idx_learning_examples_label
    ON learning_examples(label);
"""

MATCH_FIELDS = {
    "title",
    "opponent",
    "played_on",
    "whistle_mode",
    "status",
    "progress",
    "message",
    "calibration",
    "result",
    "annotated_path",
}


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    ensure_dirs()
    with db() as conn:
        conn.executescript(SCHEMA)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(clips)")}
        if "status" not in columns:
            conn.execute(
                "ALTER TABLE clips ADD COLUMN status TEXT NOT NULL DEFAULT 'new'"
            )
        if "saved_at" not in columns:
            conn.execute("ALTER TABLE clips ADD COLUMN saved_at TEXT")
        if "source" not in columns:
            conn.execute(
                "ALTER TABLE clips ADD COLUMN source TEXT NOT NULL DEFAULT 'speed'"
            )
        if "features" not in columns:
            conn.execute("ALTER TABLE clips ADD COLUMN features TEXT")
        if "saved_score" not in columns:
            conn.execute("ALTER TABLE clips ADD COLUMN saved_score REAL")
        if "starred" not in columns:
            conn.execute(
                "ALTER TABLE clips ADD COLUMN starred INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_clips_status ON clips(match_id, status, start)"
        )
        match_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(matches)")
        }
        if "whistle_mode" not in match_columns:
            conn.execute(
                "ALTER TABLE matches ADD COLUMN whistle_mode TEXT NOT NULL DEFAULT 'with'"
            )
        rejection_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(clip_rejections)")
        }
        if "reason" not in rejection_columns:
            conn.execute(
                "ALTER TABLE clip_rejections ADD COLUMN reason TEXT NOT NULL DEFAULT ''"
            )
        if "detail" not in rejection_columns:
            conn.execute(
                "ALTER TABLE clip_rejections ADD COLUMN detail TEXT NOT NULL DEFAULT ''"
            )
        if "note" not in rejection_columns:
            conn.execute(
                "ALTER TABLE clip_rejections ADD COLUMN note TEXT NOT NULL DEFAULT ''"
            )
        if "features" not in rejection_columns:
            conn.execute("ALTER TABLE clip_rejections ADD COLUMN features TEXT")
    backfill_learning_examples()


def _load_features(value: Any) -> dict | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _upsert_learning_example(
    conn: sqlite3.Connection,
    match_id: int,
    start: float,
    end: float,
    label: str,
    reason: str = "",
    detail: str = "",
    note: str = "",
    source: str = "",
    features: dict[str, Any] | None = None,
    weight: float = 1.0,
) -> None:
    if label not in {"good", "bad"}:
        raise ValueError("label de aprendizado inválido")
    start = round(float(start), 2)
    end = round(float(end), 2)
    duration = round(end - start, 2)
    if duration <= 0:
        return
    payload = json.dumps(features, ensure_ascii=False) if features is not None else None
    conn.execute(
        """
        INSERT INTO learning_examples
            (match_id, start, end, duration, label, reason, detail, note, source, features, weight)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id, start, end) DO UPDATE SET
            duration = excluded.duration,
            label = excluded.label,
            reason = excluded.reason,
            detail = excluded.detail,
            note = excluded.note,
            source = excluded.source,
            features = excluded.features,
            weight = excluded.weight,
            updated_at = datetime('now')
        """,
        (
            match_id,
            start,
            end,
            duration,
            label,
            reason or "",
            detail or "",
            note or "",
            source or "",
            payload,
            float(weight),
        ),
    )


def upsert_learning_example(
    match_id: int,
    start: float,
    end: float,
    label: str,
    reason: str = "",
    detail: str = "",
    note: str = "",
    source: str = "",
    features: dict[str, Any] | None = None,
    weight: float = 1.0,
) -> None:
    with db() as conn:
        _upsert_learning_example(
            conn,
            match_id,
            start,
            end,
            label,
            reason,
            detail,
            note,
            source,
            features,
            weight,
        )


def remove_learning_example(match_id: int, start: float, end: float) -> None:
    start = round(float(start), 2)
    end = round(float(end), 2)
    with db() as conn:
        conn.execute(
            "DELETE FROM learning_examples WHERE match_id = ? AND start = ? AND end = ?",
            (match_id, start, end),
        )


def backfill_learning_examples() -> int:
    with db() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM learning_examples").fetchone()[0]
        if existing:
            return 0
        saved = conn.execute("SELECT * FROM clips WHERE status = 'saved'").fetchall()
        rejected = conn.execute("SELECT * FROM clip_rejections").fetchall()
        total = 0
        for rejection in rejected:
            features = _load_features(rejection["features"])
            reason = rejection["reason"] or "other"
            source = ""
            if features and features.get("source"):
                source = str(features["source"])
            _upsert_learning_example(
                conn,
                rejection["match_id"],
                rejection["start"],
                rejection["end"],
                "bad",
                reason=reason,
                detail=rejection["detail"] or "",
                note=rejection["note"] or "",
                source=source,
                features=features,
                weight=learning_example_weight("bad", reason),
            )
            total += 1
        for clip in saved:
            features = _load_features(clip["features"])
            _upsert_learning_example(
                conn,
                clip["match_id"],
                clip["start"],
                clip["end"],
                "good",
                source=clip["source"] or "",
                features=features,
                weight=learning_example_weight(
                    "good", starred=bool(clip["starred"])
                ),
            )
            total += 1
        return total


def learning_stats() -> dict:
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM learning_examples").fetchone()[0]
        good = conn.execute(
            "SELECT COUNT(*) FROM learning_examples WHERE label = 'good'"
        ).fetchone()[0]
        bad = conn.execute(
            "SELECT COUNT(*) FROM learning_examples WHERE label = 'bad'"
        ).fetchone()[0]
        matches = conn.execute(
            "SELECT COUNT(DISTINCT match_id) FROM learning_examples"
        ).fetchone()[0]
        reasons = conn.execute(
            """
            SELECT reason, COUNT(*) AS count
            FROM learning_examples
            WHERE label = 'bad'
            GROUP BY reason
            ORDER BY count DESC, reason
            """
        ).fetchall()
        last_updated = conn.execute(
            "SELECT MAX(updated_at) FROM learning_examples"
        ).fetchone()[0]
    return {
        "total": int(total),
        "good": int(good),
        "bad": int(bad),
        "matches": int(matches),
        "reasons": {row["reason"] or "other": int(row["count"]) for row in reasons},
        "last_updated": last_updated,
    }


def list_learning_examples() -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM learning_examples ORDER BY match_id, start, id"
        ).fetchall()


def list_recent_learning_examples(limit: int = 20) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            """
            SELECT le.*, m.title AS match_title
            FROM learning_examples le
            LEFT JOIN matches m ON m.id = le.match_id
            ORDER BY le.updated_at DESC, le.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_match(match_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()


def list_matches() -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute("SELECT * FROM matches ORDER BY id DESC").fetchall()


def create_match(
    title: str,
    video_path: str,
    source: str = "upload",
    opponent: str = "",
    played_on: str = "",
    whistle_mode: str = "with",
) -> int:
    if whistle_mode not in {"with", "without"}:
        raise ValueError("whistle_mode deve ser with ou without")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO matches (title, opponent, played_on, video_path, source, whistle_mode) VALUES (?, ?, ?, ?, ?, ?)",
            (title, opponent, played_on, video_path, source, whistle_mode),
        )
        return int(cur.lastrowid)


def update_match(match_id: int, **fields: Any) -> None:
    clean = {key: value for key, value in fields.items() if key in MATCH_FIELDS}
    if not clean:
        return
    assignments = ", ".join(f"{key} = ?" for key in clean)
    with db() as conn:
        conn.execute(
            f"UPDATE matches SET {assignments} WHERE id = ?",
            (*clean.values(), match_id),
        )


def delete_match(match_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))


def list_events(match_id: int) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM events WHERE match_id = ? ORDER BY t, id", (match_id,)
        ).fetchall()


def get_event(event_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()


def add_event(
    match_id: int,
    t: float,
    kind: str,
    player_id: int | None = None,
    set_no: int | None = None,
    rally_no: int | None = None,
    note: str = "",
    data: dict[str, Any] | None = None,
    source: str = "manual",
) -> int:
    payload = json.dumps(data, ensure_ascii=False) if data is not None else None
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO events (match_id, t, kind, player_id, set_no, rally_no, note, data, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (match_id, t, kind, player_id, set_no, rally_no, note, payload, source),
        )
        return int(cur.lastrowid)


def delete_event(event_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))


def clear_auto_events(match_id: int) -> None:
    with db() as conn:
        conn.execute(
            "DELETE FROM events WHERE match_id = ? AND source = 'auto'", (match_id,)
        )


def list_players() -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM players ORDER BY team, number IS NULL, number, name"
        ).fetchall()


def get_player(player_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()


def add_player(name: str, number: int | None = None, team: str = "home") -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO players (name, number, team) VALUES (?, ?, ?)",
            (name, number, team),
        )
        return int(cur.lastrowid)


def delete_player(player_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM players WHERE id = ?", (player_id,))


def clear_clips(match_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM clips WHERE match_id = ?", (match_id,))


def clear_unreviewed_clips(match_id: int) -> list[sqlite3.Row]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM clips WHERE match_id = ? AND status = 'new' AND source != 'manual'",
            (match_id,),
        ).fetchall()
        conn.execute(
            "DELETE FROM clips WHERE match_id = ? AND status = 'new' AND source != 'manual'",
            (match_id,),
        )
        return rows


def add_clip(
    match_id: int,
    start: float,
    end: float,
    duration: float,
    path: str,
    thumb: str | None = None,
    score: float = 0.0,
    status: str = "new",
    source: str = "speed",
    features: dict[str, Any] | None = None,
) -> int:
    if status not in {"new", "saved"}:
        raise ValueError("status de clipe inválido")
    payload = json.dumps(features, ensure_ascii=False) if features is not None else None
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO clips
                (match_id, start, end, duration, path, thumb, score, source, features, status, saved_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'saved' THEN datetime('now') ELSE NULL END)
            """,
            (
                match_id,
                start,
                end,
                duration,
                path,
                thumb,
                score,
                source,
                payload,
                status,
                status,
            ),
        )
        return int(cur.lastrowid)


def list_clips(match_id: int, status: str | None = None) -> list[sqlite3.Row]:
    with db() as conn:
        if status:
            return conn.execute(
                "SELECT * FROM clips WHERE match_id = ? AND status = ? ORDER BY start, id",
                (match_id, status),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM clips WHERE match_id = ? ORDER BY start, id", (match_id,)
        ).fetchall()


def get_clip(clip_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()


def set_clip_starred(clip_id: int, starred: bool) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE clips SET starred = ? WHERE id = ?",
            (1 if starred else 0, clip_id),
        )


def update_clip_saved_score(clip_id: int, score: float) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE clips SET saved_score = ? WHERE id = ?", (score, clip_id)
        )


def update_clip_features(clip_id: int, features: dict[str, Any]) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE clips SET features = ? WHERE id = ?",
            (json.dumps(features, ensure_ascii=False), clip_id),
        )


def set_clip_status(clip_id: int, status: str) -> None:
    if status not in {"new", "saved"}:
        raise ValueError("status de clipe inválido")
    with db() as conn:
        conn.execute(
            """
            UPDATE clips
            SET status = ?,
                saved_at = CASE WHEN ? = 'saved' THEN datetime('now') ELSE NULL END
            WHERE id = ?
            """,
            (status, status, clip_id),
        )


def delete_clip(clip_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))


def add_clip_rejection(
    match_id: int,
    start: float,
    end: float,
    reason: str = "",
    detail: str = "",
    note: str = "",
    features: dict[str, Any] | None = None,
) -> int:
    payload = json.dumps(features, ensure_ascii=False) if features is not None else None
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO clip_rejections (match_id, start, end, reason, detail, note, features)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (match_id, start, end, reason, detail, note, payload),
        )
        return int(cur.lastrowid)


def list_clip_rejections(match_id: int) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM clip_rejections WHERE match_id = ? ORDER BY start",
            (match_id,),
        ).fetchall()
