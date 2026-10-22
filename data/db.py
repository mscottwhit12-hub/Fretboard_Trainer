"""
data/db.py

SQLite persistence for quiz attempt history. This is the layer that makes
performance data survive across app sessions (per spec: "the app remembers
heat map and performance data across sessions").

IMPORTANT DESIGN BOUNDARY (per app spec, stated repeatedly): this history is
READ-ONLY from the quiz logic's perspective. Nothing in core/quiz1.py or
core/quiz2.py ever queries this database to decide what to ask next.
HistoryDB is a one-way sink for logging, and a read source ONLY for
reporting/diagnostics UI. Keeping this file with no back-channel into core/
question generation is what enforces that boundary at the code level, not
just by convention. (core/diagnostics.py, which reads from here, is
similarly one-way for now -- see its docstring.)

Default DB location: %APPDATA%\\FretboardTrainer\\history.db on Windows
(falls back to the user's home directory elsewhere). This is deliberate --
NOT stored next to the .exe, because a PyInstaller-packaged app is often
installed somewhere the user doesn't have write access to (e.g. Program
Files). %APPDATA% is always writable by the current user.

SCHEMA HISTORY: session_id, given_string, given_fret, and given_note_name
were added after the original release, to support the Diagnostics tab
(session-scoped "last N sessions" queries, and eventually confusion-pair
analysis). They're added via an additive migration (_migrate_schema) so an
existing history.db from before this change keeps working -- old rows just
have NULL in the new columns rather than the file breaking.
"""

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.quiz1 import AnswerResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    quiz_mode TEXT NOT NULL,
    string INTEGER NOT NULL,
    fret INTEGER NOT NULL,
    midi_note INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    response_time_ms INTEGER NOT NULL,
    session_id TEXT,
    given_string INTEGER,
    given_fret INTEGER,
    given_note_name TEXT
);
"""

# Columns added after the original release -- see the migration docstring
# above. Kept as a separate map (rather than folding into SCHEMA) so an
# existing database can be brought up to date with ALTER TABLE instead of
# requiring a fresh file.
_MIGRATION_COLUMNS: dict[str, str] = {
    "session_id": "TEXT",
    "given_string": "INTEGER",
    "given_fret": "INTEGER",
    "given_note_name": "TEXT",
}

ATTEMPT_COLUMNS = [
    "id", "timestamp", "quiz_mode", "string", "fret",
    "midi_note", "correct", "response_time_ms",
    "session_id", "given_string", "given_fret", "given_note_name",
]

# Quiz mode identifiers -- used consistently across this file and the quiz
# session callers, so diagnostics queries (and future heat map queries) can
# filter cleanly by mode.
QUIZ_MODE_FRET_TO_NOTE = "fret_to_note"
QUIZ_MODE_NOTE_TO_FRET = "note_to_fret"


def default_db_path() -> Path:
    """User-writable location for the history database. See module docstring for why."""
    appdata = os.getenv("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    target_dir = base / "FretboardTrainer"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "history.db"


@dataclass
class AttemptRecord:
    """One row read back from the attempts table."""

    id: int
    timestamp: str
    quiz_mode: str
    string: int
    fret: int
    midi_note: int
    correct: bool
    response_time_ms: int
    session_id: str | None
    given_string: int | None
    given_fret: int | None
    given_note_name: str | None


class HistoryDB:
    """
    Thin wrapper around a SQLite connection for logging and reading back
    quiz attempts. Supports use as a context manager:

        with HistoryDB() as db:
            db.log_attempt(result)
    """

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(SCHEMA)
        self._conn.commit()
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        existing_columns = {row[1] for row in self._conn.execute("PRAGMA table_info(attempts)").fetchall()}
        for column, col_type in _MIGRATION_COLUMNS.items():
            if column not in existing_columns:
                self._conn.execute(f"ALTER TABLE attempts ADD COLUMN {column} {col_type}")
        self._conn.commit()

    def log_attempt(
        self,
        result: AnswerResult,
        quiz_mode: str = QUIZ_MODE_FRET_TO_NOTE,
        session_id: str | None = None,
        given_string: int | None = None,
        given_fret: int | None = None,
        given_note_name: str | None = None,
    ) -> int:
        """Record one answered question. Returns the new row's id.

        `session_id` should be a fresh identifier generated once per "Start
        Quiz" click (see ui/quiz1_panel.py / quiz2_panel.py), so diagnostics
        can group attempts into sessions for "last N sessions" queries.

        `given_string`/`given_fret` are only meaningful for Quiz Mode 2
        (Note -> Fret), where the position itself is the guess -- Quiz Mode
        1 gives you the position and asks for the note, so there's no
        position to log a guess for. `given_note_name` is meaningful for
        both modes (the note name picked in Quiz 1, or the note actually AT
        wherever was clicked in Quiz 2) and is normalized to its canonical
        spelling by the caller, not whatever sharp/flat happened to be
        displayed, so confusion-pair analysis (a future addition) can group
        by note identity rather than display spelling.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            """
            INSERT INTO attempts
                (timestamp, quiz_mode, string, fret, midi_note, correct, response_time_ms,
                 session_id, given_string, given_fret, given_note_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                quiz_mode,
                result.string,
                result.fret,
                result.midi_note,
                int(result.correct),
                result.response_time_ms,
                session_id,
                given_string,
                given_fret,
                given_note_name,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_all_attempts(
        self,
        quiz_mode: str | None = None,
        session_ids: list[str] | None = None,
    ) -> list[AttemptRecord]:
        """All logged attempts, oldest first. Optionally filtered to one
        quiz mode and/or a specific set of session_ids (see
        get_recent_session_ids). Passing an empty `session_ids` list
        short-circuits to an empty result rather than querying, since
        `IN ()` isn't valid SQL."""
        if session_ids is not None and len(session_ids) == 0:
            return []

        query = f"SELECT {', '.join(ATTEMPT_COLUMNS)} FROM attempts"
        clauses = []
        params: list = []
        if quiz_mode is not None:
            clauses.append("quiz_mode = ?")
            params.append(quiz_mode)
        if session_ids is not None:
            placeholders = ", ".join("?" for _ in session_ids)
            clauses.append(f"session_id IN ({placeholders})")
            params.extend(session_ids)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp ASC"

        rows = self._conn.execute(query, params).fetchall()
        return [
            AttemptRecord(
                id=row[0],
                timestamp=row[1],
                quiz_mode=row[2],
                string=row[3],
                fret=row[4],
                midi_note=row[5],
                correct=bool(row[6]),
                response_time_ms=row[7],
                session_id=row[8],
                given_string=row[9],
                given_fret=row[10],
                given_note_name=row[11],
            )
            for row in rows
        ]

    def get_recent_session_ids(self, quiz_mode: str | None = None, limit: int = 5) -> list[str]:
        """Distinct session_ids, most-recent first, capped at `limit`. Rows
        logged before the session_id migration (NULL) are excluded, since
        they can't be grouped into a session."""
        query = (
            "SELECT session_id, MAX(timestamp) AS latest FROM attempts "
            "WHERE session_id IS NOT NULL"
        )
        params: list = []
        if quiz_mode is not None:
            query += " AND quiz_mode = ?"
            params.append(quiz_mode)
        query += " GROUP BY session_id ORDER BY latest DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [row[0] for row in rows]

    def count_attempts(self, quiz_mode: str | None = None) -> int:
        if quiz_mode is None:
            return self._conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        return self._conn.execute(
            "SELECT COUNT(*) FROM attempts WHERE quiz_mode = ?", (quiz_mode,)
        ).fetchone()[0]

    def clear_all(self) -> int:
        """Delete every logged attempt. Returns how many rows were removed."""
        count = self.count_attempts()
        self._conn.execute("DELETE FROM attempts")
        self._conn.commit()
        return count

    def export_csv(self, path: Path | str) -> int:
        """Write every attempt to a CSV file (with header). Returns row count."""
        import csv
        records = self.get_all_attempts()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(ATTEMPT_COLUMNS)
            for r in records:
                writer.writerow([
                    r.id, r.timestamp, r.quiz_mode, r.string, r.fret, r.midi_note,
                    int(r.correct), r.response_time_ms, r.session_id or "",
                    "" if r.given_string is None else r.given_string,
                    "" if r.given_fret is None else r.given_fret,
                    r.given_note_name or "",
                ])
        return len(records)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "HistoryDB":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
