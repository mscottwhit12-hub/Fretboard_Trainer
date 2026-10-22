"""
core/quiz1.py

Quiz Mode 1: Fret -> Note.

The app highlights a string/fret position; the user picks the correct note
from a multiple-choice list. QuizSession owns all the state a session needs:
which question is currently active, how many questions have been answered,
and the current answer-button arrangement (which only changes on a shuffle
event, not every question).

IMPORTANT DESIGN RULE (per app spec): randomization here is always neutral.
Nothing in this file ever looks at past performance to decide what to ask
next -- string, fret, and wrong-answer choices are drawn uniformly at random
every time. Performance is only ever recorded (by the caller, via
AnswerResult) for later reporting -- never fed back in here.
"""

import random
import time
from dataclasses import dataclass

from core.fretboard import Fretboard
from core.notes import Note, pitch_class_names
from core.settings import GameRules

DEFAULT_NUM_CHOICES = 4
DEFAULT_SHUFFLE_INTERVAL = 10


@dataclass
class Question:
    """One issued Fret->Note question, awaiting an answer."""

    string: int
    fret: int
    correct_note: Note
    choices: list[tuple[int, str]]  # (pitch_class, display_name), in on-screen display order
    issued_at: float  # time.monotonic() timestamp, used to compute response time


@dataclass
class AnswerResult:
    """
    The outcome of one answered question. This is the shape the SQLite
    logging layer (data/db.py, next up) will consume directly -- string,
    fret, correct/incorrect, and response time map straight onto the
    `attempts` table columns.
    """

    string: int
    fret: int
    midi_note: int
    given_answer: str
    correct: bool
    response_time_ms: int


class QuizSession:
    """
    Stateful driver for a Fret->Note quiz session.

    Usage:
        session = QuizSession(fretboard, shuffle_enabled=True)
        q = session.next_question()
        # ...display q.choices to the user, wait for their pick...
        result = session.submit_answer("C#")
    """

    def __init__(
        self,
        fretboard: Fretboard,
        shuffle_enabled: bool = False,
        shuffle_interval: int = DEFAULT_SHUFFLE_INTERVAL,
        num_choices: int = DEFAULT_NUM_CHOICES,
        rng: random.Random | None = None,
    ):
        if num_choices < 2 or num_choices > 12:
            raise ValueError("num_choices must be between 2 and 12 (there are only 12 pitch classes).")
        if shuffle_interval < 1:
            raise ValueError("shuffle_interval must be at least 1.")

        self.fretboard = fretboard
        self.shuffle_enabled = shuffle_enabled
        self.shuffle_interval = shuffle_interval
        self.num_choices = num_choices
        self._rng = rng or random.Random()

        self.questions_answered = 0
        self.current_question: Question | None = None
        self._last_position: tuple[int, int] | None = None
        self._position_permutation = self._new_permutation()

    def _new_permutation(self) -> list[int]:
        """A random arrangement mapping 'generation order' -> 'on-screen position'."""
        perm = list(range(self.num_choices))
        self._rng.shuffle(perm)
        return perm

    def next_question(self) -> Question:
        """
        Generate the next question: random enabled string, random fret (0-15),
        correct note + (num_choices - 1) wrong pitch classes, arranged on-screen
        according to the current position permutation.

        Because wrong answers are sampled by PITCH CLASS (not by spelling),
        it is structurally impossible for two enharmonic spellings of the same
        note (e.g. C# and Db) to both appear as separate choices.
        """
        pool = self.fretboard.candidate_positions()
        if not pool:
            raise ValueError("No strings enabled -- cannot generate a question.")
        # Never repeat the exact same (string, fret) twice in a row -- unless
        # the pool has only one position, where a repeat is unavoidable.
        if len(pool) > 1:
            pool = [p for p in pool if p != self._last_position]
        string, fret = self._rng.choice(pool)
        self._last_position = (string, fret)
        note = self.fretboard.note_at(string, fret)
        correct_pc = note.pitch_class

        other_pcs = [pc for pc in range(12) if pc != correct_pc]
        wrong_pcs = self._rng.sample(other_pcs, self.num_choices - 1)
        generation_order = [correct_pc] + wrong_pcs  # index 0 is always the correct one, pre-shuffle

        # Apply the current position permutation so the correct answer doesn't
        # always land in the same slot within a shuffle interval.
        arranged: list[int | None] = [None] * self.num_choices
        for source_idx, target_idx in enumerate(self._position_permutation):
            arranged[target_idx] = generation_order[source_idx]

        # Each choice's spelling (sharp vs. flat) is picked according to the
        # current Game Rules accidental preference -- e.g. one question
        # might show "C#" while the next shows "Db" for that same pitch
        # class under Random Mix. This can never create a duplicate
        # displayed answer: choices are already guaranteed to have distinct
        # pitch classes (see the assertion above), and two DIFFERENT pitch
        # classes never share a spelling, so e.g. A# and Bb (which are the
        # same pitch class) can never both appear as separate choices.
        game_rules = GameRules.instance()
        choices = [
            (pc, game_rules.choose_spelling(pitch_class_names(pc), self._rng))
            for pc in arranged
        ]

        self.current_question = Question(
            string=string,
            fret=fret,
            correct_note=note,
            choices=choices,
            issued_at=time.monotonic(),
        )
        return self.current_question

    def submit_answer(self, answer_name: str) -> AnswerResult:
        """
        Grade the currently active question. Accepts either enharmonic
        spelling as correct (delegates to Note.matches_name).

        Triggers a reshuffle of answer-button positions if shuffle_enabled
        is True and this answer completes a shuffle_interval block of
        questions (e.g. every 10th answer) -- not every single question.
        """
        if self.current_question is None:
            raise ValueError("No question is currently active -- call next_question() first.")

        q = self.current_question
        response_time_ms = int((time.monotonic() - q.issued_at) * 1000)
        correct = q.correct_note.matches_name(answer_name)

        self.questions_answered += 1
        if self.shuffle_enabled and self.questions_answered % self.shuffle_interval == 0:
            self._position_permutation = self._new_permutation()

        result = AnswerResult(
            string=q.string,
            fret=q.fret,
            midi_note=q.correct_note.midi,
            given_answer=answer_name,
            correct=correct,
            response_time_ms=response_time_ms,
        )

        self.current_question = None
        return result
