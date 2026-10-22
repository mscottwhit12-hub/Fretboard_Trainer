"""
core/diagnostics.py

Read-only analysis over HistoryDB's attempt log -- surfaces "struggle
points" for the Diagnostics tab. No UI framework dependency, and no
feedback into quiz question generation (core/quiz1.py's and
core/quiz2.py's randomization stays neutral, per their own docstrings) --
this is purely observational for now. Kept UI-agnostic specifically so it
CAN be wired into adaptive practice later without a rewrite.

SCOPE (for now): position-based diagnostics only --
    - per (string, fret) accuracy, for the heatmap
    - Quiz Mode 2 "position confusion" -- which WRONG position tends to
      get clicked when the target was some OTHER position (only
      meaningful in Quiz Mode 2, since Quiz Mode 1 gives you the position
      and asks for the note -- there's no position to confuse there)

Note-name / music-theory analysis (e.g. "you keep confusing F# for F") is
intentionally NOT built yet, even though data/db.py already logs
`given_note_name` for exactly that future purpose. The schema and storage
are already in place -- adding that analysis later is a new function in
this file, not a migration or a rewrite of anything here.
"""

from dataclasses import dataclass

from data.db import AttemptRecord, HistoryDB, QUIZ_MODE_NOTE_TO_FRET


@dataclass
class PositionStat:
    string: int
    fret: int
    attempts: int
    correct: int

    @property
    def accuracy(self) -> float:
        """0.0-1.0. Callers rendering this (e.g. the heatmap) should check
        `attempts == 0` for a distinct "no data" state rather than reading
        this value directly in that case -- it returns 1.0 for zero
        attempts specifically so an unattempted position never accidentally
        sorts as "worst" in code that forgets to check."""
        return self.correct / self.attempts if self.attempts else 1.0


@dataclass
class PositionConfusion:
    """Quiz Mode 2 only: the target position vs. a wrong position that got
    clicked instead, and how many times that specific mix-up happened."""

    target_string: int
    target_fret: int
    given_string: int
    given_fret: int
    count: int


def _filtered_attempts(
    db: HistoryDB,
    quiz_mode: str | None,
    session_limit: int | None,
    strings: set[int] | None = None,
    frets: tuple[int, int] | None = None,
) -> list[AttemptRecord]:
    session_ids = None
    if session_limit is not None:
        session_ids = db.get_recent_session_ids(quiz_mode=quiz_mode, limit=session_limit)
        if not session_ids:
            return []
    attempts = db.get_all_attempts(quiz_mode=quiz_mode, session_ids=session_ids)
    if strings is not None:
        attempts = [a for a in attempts if a.string in strings]
    if frets is not None:
        attempts = [a for a in attempts if frets[0] <= a.fret <= frets[1]]
    return attempts


def position_accuracy(
    db: HistoryDB,
    quiz_mode: str | None = None,
    session_limit: int | None = None,
    strings: set[int] | None = None,
    frets: tuple[int, int] | None = None,
) -> dict[tuple[int, int], PositionStat]:
    """Accuracy per (string, fret), across all attempts unless narrowed by
    `quiz_mode`, `session_limit` (most-recent N sessions), and/or `strings`
    (only these string numbers -- e.g. the currently-selected Active
    Strings, shared with the quiz tabs)."""
    attempts = _filtered_attempts(db, quiz_mode, session_limit, strings, frets)
    stats: dict[tuple[int, int], PositionStat] = {}
    for a in attempts:
        key = (a.string, a.fret)
        if key not in stats:
            stats[key] = PositionStat(string=a.string, fret=a.fret, attempts=0, correct=0)
        stats[key].attempts += 1
        if a.correct:
            stats[key].correct += 1
    return stats


def weakest_positions(
    db: HistoryDB,
    quiz_mode: str | None = None,
    session_limit: int | None = None,
    strings: set[int] | None = None,
    frets: tuple[int, int] | None = None,
    min_attempts: int = 2,
    limit: int = 10,
) -> list[PositionStat]:
    """Lowest-accuracy positions first. `min_attempts` filters out
    single-guess noise (one unlucky miss shouldn't outrank a position
    that's been genuinely struggled with over many tries); ties are broken
    toward more attempts, since that's more confidently a real pattern."""
    stats = position_accuracy(db, quiz_mode, session_limit, strings, frets).values()
    qualifying = [s for s in stats if s.attempts >= min_attempts]
    return sorted(qualifying, key=lambda s: (s.accuracy, -s.attempts))[:limit]


def position_confusions(
    db: HistoryDB,
    session_limit: int | None = None,
    strings: set[int] | None = None,
    limit: int = 10,
    frets: tuple[int, int] | None = None,
) -> list[PositionConfusion]:
    """Quiz Mode 2 only: ranks which wrong position gets clicked instead of
    the target, by how often it happens. Requires given_string/given_fret,
    which are only ever logged for Quiz Mode 2 -- Quiz Mode 1 hands you the
    position and asks for the note, so there's nothing to confuse there.
    `strings`, if given, filters by the TARGET string (i.e. "confusions
    among my currently-selected strings"), not the wrongly-clicked string."""
    attempts = _filtered_attempts(db, QUIZ_MODE_NOTE_TO_FRET, session_limit, strings, frets)
    counts: dict[tuple[int, int, int, int], int] = {}
    for a in attempts:
        if a.correct or a.given_string is None or a.given_fret is None:
            continue
        key = (a.string, a.fret, a.given_string, a.given_fret)
        counts[key] = counts.get(key, 0) + 1

    confusions = [
        PositionConfusion(
            target_string=ts, target_fret=tf, given_string=gs, given_fret=gf, count=c,
        )
        for (ts, tf, gs, gf), c in counts.items()
    ]
    return sorted(confusions, key=lambda c: -c.count)[:limit]


@dataclass
class PositionSpeedStat:
    string: int
    fret: int
    correct_attempts: int
    average_response_time_ms: float


@dataclass
class HeatmapCell:
    """A generic (attempts, score) pair the heatmap widget can render,
    independent of whether the score means accuracy or relative speed.
    `accuracy` here just means "0-1 mastery score for coloring purposes",
    reusing the same field name position_accuracy's PositionStat exposes
    so both can feed FretboardWidget.set_heatmap_data interchangeably."""

    attempts: int
    accuracy: float


def position_speed(
    db: HistoryDB,
    quiz_mode: str | None = None,
    session_limit: int | None = None,
    strings: set[int] | None = None,
    frets: tuple[int, int] | None = None,
) -> dict[tuple[int, int], PositionSpeedStat]:
    """Average response time on CORRECT attempts only, per position.
    Incorrect answers are excluded -- a wrong guess doesn't reflect real
    recognition speed either way (a fast wrong guess isn't "mastered", and
    a slow wrong guess is already captured as a miss by position_accuracy,
    not a timing signal)."""
    attempts = _filtered_attempts(db, quiz_mode, session_limit, strings, frets)
    times: dict[tuple[int, int], list[int]] = {}
    for a in attempts:
        if not a.correct:
            continue
        times.setdefault((a.string, a.fret), []).append(a.response_time_ms)
    return {
        key: PositionSpeedStat(
            string=key[0],
            fret=key[1],
            correct_attempts=len(t),
            average_response_time_ms=sum(t) / len(t),
        )
        for key, t in times.items()
    }


def speed_heatmap_cells(
    db: HistoryDB,
    quiz_mode: str | None = None,
    session_limit: int | None = None,
    strings: set[int] | None = None,
    frets: tuple[int, int] | None = None,
) -> dict[tuple[int, int], HeatmapCell]:
    """Converts per-position average correct-answer time into a 0-1 score
    for heatmap coloring: the SLOWEST position in the current filtered
    data becomes 0.0 (the 0%/struggle color), the FASTEST becomes 1.0 (the
    100%/mastered color), everything else scales linearly between them.
    This is purely relative to the current filtered dataset -- there's no
    fixed "good" response time in milliseconds, just relative-to-your-
    -own-data, same as the user asked for."""
    stats = position_speed(db, quiz_mode, session_limit, strings, frets)
    if not stats:
        return {}
    times = [s.average_response_time_ms for s in stats.values()]
    fastest, slowest = min(times), max(times)
    span = slowest - fastest
    cells: dict[tuple[int, int], HeatmapCell] = {}
    for key, stat in stats.items():
        # If every position took exactly the same time, there's nothing to
        # rank -- default to 1.0 rather than dividing by zero.
        score = 1.0 if span == 0 else (slowest - stat.average_response_time_ms) / span
        cells[key] = HeatmapCell(attempts=stat.correct_attempts, accuracy=score)
    return cells


def rank_worst_cells(
    cells: dict[tuple[int, int], HeatmapCell], min_attempts: int = 1, limit: int = 5,
) -> list[tuple[tuple[int, int], HeatmapCell]]:
    """Lowest-score cells first. Works for either accuracy or speed data
    once wrapped as HeatmapCell, since both just expose .attempts/.accuracy."""
    qualifying = [(pos, c) for pos, c in cells.items() if c.attempts >= min_attempts]
    return sorted(qualifying, key=lambda item: (item[1].accuracy, -item[1].attempts))[:limit]
