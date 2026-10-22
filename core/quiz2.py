"""
core/quiz2.py

Quiz Mode 2: Note -> Fret.

The app names a note on a specific string (e.g. "Find C# on string 3"),
and the user clicks the fretboard to guess where it is. Within the 0-15
fret range a given pitch class occurs at most twice on any one string --
either fret is accepted as correct, since both are genuinely the same
named note on that string.

Reuses core.quiz1.AnswerResult so data/db.py doesn't need a second result
shape. Same neutral-randomization and no-repeat-position rules as quiz1.
"""

import random
import time
from dataclasses import dataclass

from core.fretboard import Fretboard
from core.notes import Note, pitch_class_names
from core.quiz1 import AnswerResult
from core.settings import GameRules


@dataclass
class Question:
    """One issued Note->Fret question, awaiting a fret click on `string`."""

    string: int
    correct_note: Note
    valid_frets: list[int]  # every fret on this string sharing the note's pitch class (1 or 2)
    prompt_text: str
    issued_at: float


class QuizSession:
    """
    Stateful driver for a Note->Fret quiz session.

    Usage:
        session = QuizSession(fretboard)
        q = session.next_question()
        # ...user clicks a position on the fretboard...
        result = session.submit_answer(clicked_string, clicked_fret)
    """

    def __init__(self, fretboard: Fretboard, rng: random.Random | None = None):
        self.fretboard = fretboard
        self._rng = rng or random.Random()
        self.questions_answered = 0
        self.current_question: Question | None = None
        self._last_position: tuple[int, int] | None = None

    def next_question(self) -> Question:
        pool = self.fretboard.candidate_positions()
        if not pool:
            raise ValueError("No strings enabled -- cannot generate a question.")
        if len(pool) > 1:
            pool = [p for p in pool if p != self._last_position]
        string, fret = self._rng.choice(pool)
        self._last_position = (string, fret)

        note = self.fretboard.note_at(string, fret)
        # Uses the current Game Rules accidental preference, e.g. "Find C#"
        # one time and "Find Db" another under Random Mix. No duplicate-
        # answer risk here since only one note is ever named per question.
        note_name = GameRules.instance().choose_spelling(pitch_class_names(note.pitch_class), self._rng)

        valid_frets = sorted(
            f for f in self.fretboard.active_frets()
            if self.fretboard.note_at(string, f).pitch_class == note.pitch_class
        )

        prompt_text = f"Find {note_name} on string {string}"

        self.current_question = Question(
            string=string,
            correct_note=note,
            valid_frets=valid_frets,
            prompt_text=prompt_text,
            issued_at=time.monotonic(),
        )
        return self.current_question

    def submit_answer(self, clicked_string: int, clicked_fret: int) -> AnswerResult:
        """
        Grade a fret click. Correct if the string matches AND the fret is
        ANY of the target note's valid frets on that string -- either
        occurrence of the same named note is accepted.
        """
        if self.current_question is None:
            raise ValueError("No question is currently active -- call next_question() first.")

        q = self.current_question
        response_time_ms = int((time.monotonic() - q.issued_at) * 1000)
        correct = clicked_string == q.string and clicked_fret in q.valid_frets

        self.questions_answered += 1

        # Log the fret the user actually landed on when correct (reflects the
        # real attempt); otherwise log the lowest valid fret as the reference.
        logged_fret = clicked_fret if correct else q.valid_frets[0]
        logged_note = self.fretboard.note_at(q.string, logged_fret)

        result = AnswerResult(
            string=q.string,
            fret=logged_fret,
            midi_note=logged_note.midi,
            given_answer=f"string {clicked_string} fret {clicked_fret}",
            correct=correct,
            response_time_ms=response_time_ms,
        )

        self.current_question = None
        return result
