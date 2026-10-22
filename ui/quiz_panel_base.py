"""
ui/quiz_panel_base.py

Everything Quiz 1 and Quiz 2 share: string/fret selectors, duration,
optional 3-2-1 pre-count, timer, Start / Pause / Stop, keyboard shortcuts,
logging, scoring, and the end-of-quiz summary. Subclasses supply only the
question/answer specifics.

Phases: "idle" -> ("precount") -> "running" -> "idle". Pause is a flag on
"running": it freezes the clock and any pending auto-advance, hides the
question, and shifts the current question's issued_at forward by the paused
time so response-time stats aren't inflated.
"""

import time
import uuid

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.prefs import Prefs
from data.db import HistoryDB
from ui.fretboard_widget import FretboardWidget
from ui.kit import Card, FeedbackTag, SkinButton, Stepper
from ui.selection_widgets import FretRangeSelector, StringSelector
from ui.shared_state import SharedFretboardState
from ui.summary_dialog import AttemptSummary, QuizSummaryDialog
from ui.theme import SkinManager, skin

MIN_DURATION_SECONDS = 10
MAX_DURATION_SECONDS = 600
AUTO_ADVANCE_DELAY_CORRECT_MS = 900
AUTO_ADVANCE_DELAY_INCORRECT_MS = 2600
PRECOUNT_FROM = 3
NO_STRINGS_MESSAGE = "Select at least one string to start."
PAUSED_MESSAGE = "Paused \u2014 press Space or Resume."


class QuizPanelBase(QWidget):
    QUIZ_MODE = ""                 # data.db quiz-mode id
    DURATION_PREF = ""             # core.prefs key
    IDLE_PROMPT = "Set your options, then click Start Quiz."

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = SharedFretboardState.instance()
        self.fretboard = self._state.fretboard
        self._prefs = Prefs.instance()
        self.db = HistoryDB()
        self.session = None
        self.session_id: str | None = None

        self.phase = "idle"
        self.paused = False
        self._pause_started = 0.0
        self._advance_remaining_ms = -1
        self._precount_value = 0
        self.correct_count = 0
        self.total_count = 0
        self.time_remaining_seconds = 0
        self.attempts: list[AttemptSummary] = []

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._on_countdown_tick)
        self.advance_timer = QTimer(self)
        self.advance_timer.setSingleShot(True)
        self.advance_timer.timeout.connect(self._show_next_question)
        self.precount_timer = QTimer(self)
        self.precount_timer.setInterval(1000)
        self.precount_timer.timeout.connect(self._on_precount_tick)

        SkinManager.instance().skin_changed.connect(lambda _s: self._apply_fonts())

        self._build_ui()
        self._build_shortcuts()

        self._state.strings_changed.connect(lambda _s: self._refresh_idle_state())
        self._state.fret_range_changed.connect(lambda _a, _b: self._refresh_idle_state())
        self._state.quiz_running_changed.connect(lambda _r: self._refresh_idle_state())
        self._refresh_idle_state()

    @property
    def quiz_active(self) -> bool:
        return self.phase != "idle"

    @property
    def accepting_answers(self) -> bool:
        return self.phase == "running" and not self.paused

    # --- hooks for subclasses ------------------------------------------------

    def _make_session(self):
        raise NotImplementedError

    def _build_answer_area(self, root: QVBoxLayout) -> None:
        """Optional: add widgets between the prompt and the feedback label."""

    def _present_question(self, question) -> None:
        raise NotImplementedError

    def _on_quiz_stopped(self) -> None:
        """Optional: reset answer widgets after a stop/timeout."""

    def _set_extra_hidden(self, hidden: bool) -> None:
        """Optional: hide/restore answer widgets while paused."""

    def _extra_shortcuts_enabled(self, enabled: bool) -> None:
        """Optional: enable/disable subclass shortcuts."""

    def _summary_title(self) -> str:
        return "Time's up!"

    # --- UI ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        self.string_selector = StringSelector()
        self.string_checkboxes = self.string_selector.checkboxes
        top_row.addWidget(self.string_selector, stretch=3)
        self.fret_selector = FretRangeSelector()
        top_row.addWidget(self.fret_selector, stretch=3)
        root.addLayout(top_row)

        board_card = Card("Fretboard", "white", pad=10)
        self.fretboard_widget = FretboardWidget(self.fretboard)
        self.fretboard_widget.set_range_dimming(True)
        board_card.body.addWidget(self.fretboard_widget)
        root.addWidget(board_card)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        question = Card("Question", "yellow")
        self.prompt_label = QLabel(self.IDLE_PROMPT)
        self.prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setMinimumHeight(52)  # stable height across 3-2-1 / question / paused text
        question.body.addWidget(self.prompt_label)
        self._build_answer_area(question.body)
        self.feedback_label = FeedbackTag()
        question.body.addWidget(self.feedback_label)
        mid.addWidget(question, stretch=3)

        side = QVBoxLayout()
        side.setSpacing(14)
        side.addWidget(self._build_duration_card())
        time_card = Card("Time left", "green", pad=12)
        self.timer_label = QLabel("")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_card.body.addWidget(self.timer_label)
        self.score_label = QLabel("SCORE  0 / 0")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_card.body.addWidget(self.score_label)
        side.addWidget(time_card)
        mid.addLayout(side, stretch=1)
        root.addLayout(mid)

        self.start_button = self._make_button("Start quiz", "primary", self._on_start_clicked, "Ctrl+Enter")
        self.pause_button = self._make_button("Pause", "secondary", self._toggle_pause, "Space")
        self.stop_button = self._make_button("Stop", "danger", self._on_stop_clicked, "Esc")
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addStretch()
        for b in (self.start_button, self.pause_button, self.stop_button):
            row.addWidget(b)
        row.addStretch()
        root.addLayout(row)
        root.addStretch()
        self.time_remaining_seconds = self.duration_spinbox.value()
        self._update_timer_label()
        self._apply_fonts()

    def _apply_fonts(self) -> None:
        sk = skin()
        big = self.phase == "precount"
        self.prompt_label.setFont(sk.font("display", 56 if big else 22))
        self.timer_label.setFont(sk.font("display", 34))
        self.score_label.setFont(sk.font("bold", 16))

    def _make_button(self, text, kind, slot, hint) -> SkinButton:
        b = SkinButton(text, kind)
        b.setMinimumWidth(170)
        b.setToolTip(f"Shortcut: {hint}")
        b.clicked.connect(slot)
        return b

    def _build_duration_card(self) -> Card:
        card = Card("Duration", "blue", pad=12)
        self.duration_spinbox = Stepper(MIN_DURATION_SECONDS, MAX_DURATION_SECONDS, 60)
        self.duration_spinbox.setSingleStep(10)
        self.duration_spinbox.setSuffix("s")
        saved = int(self._prefs.get(self.DURATION_PREF))
        self.duration_spinbox.setValue(max(MIN_DURATION_SECONDS, min(MAX_DURATION_SECONDS, saved)))
        self.duration_spinbox.valueChanged.connect(self._on_duration_changed)
        dr = QHBoxLayout()
        dr.addWidget(self.duration_spinbox)
        dr.addStretch()
        card.body.addLayout(dr)
        self.duration_group = card
        return card

    def _on_duration_changed(self, value: int) -> None:
        self._prefs.set(self.DURATION_PREF, value)
        if self.phase == "idle":
            self.time_remaining_seconds = value
            self._update_timer_label()

    def _set_feedback(self, text: str, kind: str = "") -> None:
        self.feedback_label.set_feedback(text, kind)

    def _build_shortcuts(self) -> None:
        ctx = Qt.ShortcutContext.WindowShortcut
        self._start_shortcuts = [QShortcut(QKeySequence(k), self) for k in ("Ctrl+Return", "Ctrl+Enter")]
        for sc in self._start_shortcuts:
            sc.setContext(ctx)
            sc.activated.connect(self._shortcut_start)
        self._pause_shortcuts = [QShortcut(QKeySequence(k), self) for k in ("Space", "P")]
        for sc in self._pause_shortcuts:
            sc.setContext(ctx)
            sc.activated.connect(self._toggle_pause)
        self._stop_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._stop_shortcut.setContext(ctx)
        self._stop_shortcut.activated.connect(self._on_stop_clicked)
        self._update_shortcuts()

    def _update_shortcuts(self) -> None:
        # Space / P / digits only while a quiz runs, so they never swallow
        # typing in the spinboxes; Esc only while something is running.
        running = self.phase == "running"
        for sc in self._pause_shortcuts:
            sc.setEnabled(running)
        self._stop_shortcut.setEnabled(self.phase != "idle")
        self._extra_shortcuts_enabled(running and not self.paused)

    def _shortcut_start(self) -> None:
        if self.phase == "idle" and self.start_button.isEnabled():
            self._on_start_clicked()

    # --- idle-state bookkeeping -----------------------------------------------

    def _has_positions(self) -> bool:
        return bool(self.fretboard.candidate_positions())

    def _refresh_idle_state(self) -> None:
        self.fretboard_widget.refresh()
        if self.phase != "idle":
            return
        has = self._has_positions()
        self.start_button.setEnabled(has and not self._state.quiz_running)
        if not has:
            self.prompt_label.setText(NO_STRINGS_MESSAGE)
        elif self.prompt_label.text() == NO_STRINGS_MESSAGE:
            self.prompt_label.setText(self.IDLE_PROMPT)

    # --- start / precount ------------------------------------------------------

    def _on_start_clicked(self) -> None:
        if self.phase != "idle" or self._state.quiz_running or not self._has_positions():
            return
        self.session = self._make_session()
        self.session_id = str(uuid.uuid4())
        self.correct_count = self.total_count = 0
        self.attempts = []
        self._update_score_label()
        self._set_feedback("")
        self.duration_spinbox.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._state.set_quiz_running(True)

        if self._prefs.get("precount_enabled"):
            self.phase = "precount"
            self._precount_value = PRECOUNT_FROM
            self._apply_fonts()
            self.prompt_label.setText(str(self._precount_value))
            self.precount_timer.start()
            self._update_shortcuts()
        else:
            self._begin_quiz()

    def _on_precount_tick(self) -> None:
        self._precount_value -= 1
        if self._precount_value <= 0:
            self.precount_timer.stop()
            self._begin_quiz()
        else:
            self.prompt_label.setText(str(self._precount_value))

    def _begin_quiz(self) -> None:
        self.phase = "running"
        self._apply_fonts()
        self.pause_button.setEnabled(True)
        self.time_remaining_seconds = self.duration_spinbox.value()
        self._update_timer_label()
        self.countdown_timer.start()
        self._update_shortcuts()
        self._show_next_question()

    # --- clock -------------------------------------------------------------------

    def _on_countdown_tick(self) -> None:
        self.time_remaining_seconds -= 1
        self._update_timer_label()
        if self.time_remaining_seconds <= 0:
            self._end_quiz()

    def _update_timer_label(self) -> None:
        minutes, seconds = divmod(max(self.time_remaining_seconds, 0), 60)
        self.timer_label.setText(f"{minutes}:{seconds:02d}")

    # --- questions -----------------------------------------------------------------

    def _show_next_question(self) -> None:
        if self.phase != "running":
            return
        if not self._has_positions():
            self._stop_quiz("No positions available — check strings and fret range.")
            return
        question = self.session.next_question()
        self._set_feedback("")
        self._present_question(question)

    def _record(self, result, description: str, **log_kwargs) -> None:
        """Log one answered question, update score/streak/summary data."""
        self.db.log_attempt(result, quiz_mode=self.QUIZ_MODE, session_id=self.session_id, **log_kwargs)
        self.total_count += 1
        if result.correct:
            self.correct_count += 1
        self.attempts.append(AttemptSummary(result.correct, result.response_time_ms, description))
        self._update_score_label()
        delay = AUTO_ADVANCE_DELAY_CORRECT_MS if result.correct else AUTO_ADVANCE_DELAY_INCORRECT_MS
        self.advance_timer.start(delay)

    def _update_score_label(self) -> None:
        self.score_label.setText(f"SCORE  {self.correct_count} / {self.total_count}")

    # --- pause ---------------------------------------------------------------------

    def _toggle_pause(self) -> None:
        if self.phase != "running":
            return
        if not self.paused:
            self.paused = True
            self._pause_started = time.monotonic()
            self.countdown_timer.stop()
            self._advance_remaining_ms = self.advance_timer.remainingTime() if self.advance_timer.isActive() else -1
            self.advance_timer.stop()
            self._saved_prompt = self.prompt_label.text()
            self._saved_feedback = (self.feedback_label.text(), self.feedback_label.kind)
            self.prompt_label.setText(PAUSED_MESSAGE)
            self._set_feedback("")
            self.fretboard_widget.set_content_hidden(True)
            self._set_extra_hidden(True)
            self.pause_button.setText("Resume")
        else:
            paused_for = time.monotonic() - self._pause_started
            q = getattr(self.session, "current_question", None)
            if q is not None:
                q.issued_at += paused_for  # don't count paused time as thinking time
            self.paused = False
            self.prompt_label.setText(self._saved_prompt)
            self._set_feedback(*self._saved_feedback)
            self.fretboard_widget.set_content_hidden(False)
            self._set_extra_hidden(False)
            self.pause_button.setText("Pause")
            self.countdown_timer.start()
            if self._advance_remaining_ms >= 0:
                self.advance_timer.start(max(1, self._advance_remaining_ms))
        self._update_shortcuts()

    # --- stop / end ------------------------------------------------------------------

    def _end_quiz(self) -> None:
        attempts = list(self.attempts)
        self._stop_quiz(f"Time's up! Final score: {self.correct_count} / {self.total_count}")
        if attempts:
            QTimer.singleShot(0, lambda: self._show_summary(attempts))

    def _show_summary(self, attempts: list[AttemptSummary]) -> None:
        QuizSummaryDialog(self._summary_title(), attempts, self).exec()

    def _on_stop_clicked(self) -> None:
        if self.phase == "idle":
            return
        self._stop_quiz("Quiz stopped.")  # a manual stop cancels: no summary

    def _stop_quiz(self, message: str) -> None:
        self.phase = "idle"
        if self.paused:
            self.paused = False
            self.fretboard_widget.set_content_hidden(False)
            self._set_extra_hidden(False)
        self.countdown_timer.stop()
        self.advance_timer.stop()
        self.precount_timer.stop()

        self._on_quiz_stopped()
        self.fretboard_widget.set_interactive(False)
        self.fretboard_widget.clear_highlights()
        self.time_remaining_seconds = self.duration_spinbox.value()
        self._update_timer_label()

        self._apply_fonts()
        self.prompt_label.setText(message)
        self._set_feedback("")
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.duration_spinbox.setEnabled(True)
        self._update_shortcuts()
        self._state.set_quiz_running(False)
        self._refresh_idle_state()

    # --- lifecycle -------------------------------------------------------------------

    def shutdown(self) -> None:
        for t in (self.countdown_timer, self.advance_timer, self.precount_timer):
            t.stop()
        self.db.close()
