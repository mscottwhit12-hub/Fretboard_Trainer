"""
ui/quiz1_panel.py

Quiz Mode 1: Fret -> Note. A position is highlighted; pick its note from
four answer buttons (keys 1-4 also work while the quiz runs). Shared quiz
machinery (timer, pause, pre-count, logging, summary) lives in
ui/quiz_panel_base.py.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QGridLayout

from core.notes import Note, name_to_pitch_class, pitch_class_names
from core.quiz1 import QuizSession
from data.db import QUIZ_MODE_FRET_TO_NOTE
from ui.audio import play_note_tone
from ui.kit import SkinButton
from ui.quiz_panel_base import QuizPanelBase


class Quiz1Panel(QuizPanelBase):
    QUIZ_MODE = QUIZ_MODE_FRET_TO_NOTE
    DURATION_PREF = "quiz1_duration"

    def _make_session(self):
        return QuizSession(self.fretboard, shuffle_enabled=True, shuffle_interval=1)

    def _build_answer_area(self, layout) -> None:
        grid = QGridLayout()
        grid.setSpacing(10)
        self.answer_buttons: list[SkinButton] = []
        for i in range(4):
            btn = SkinButton("", "answer")
            btn.setEnabled(False)
            btn.setMinimumHeight(54)
            btn.setToolTip(f"Shortcut: {i + 1}")
            btn.clicked.connect(lambda checked, idx=i: self._on_answer_clicked(idx))
            grid.addWidget(btn, i // 2, i % 2)
            self.answer_buttons.append(btn)
        layout.addLayout(grid)

        self._digit_shortcuts = []
        for i in range(4):
            sc = QShortcut(QKeySequence(str(i + 1)), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(lambda idx=i: self._on_answer_clicked(idx))
            self._digit_shortcuts.append(sc)

    def _extra_shortcuts_enabled(self, enabled: bool) -> None:
        for sc in getattr(self, "_digit_shortcuts", []):
            sc.setEnabled(enabled)

    def _present_question(self, question) -> None:
        self.fretboard_widget.set_highlighted_positions([(question.string, question.fret)])
        self.prompt_label.setText(f"What note is this? (String {question.string}, Fret {question.fret})")
        for btn, (_pc, name) in zip(self.answer_buttons, question.choices):
            btn.setText(name)
            btn.setEnabled(True)
            btn.set_tone(None)

    def _on_answer_clicked(self, index: int) -> None:
        # Guards double-answers (button already disabled) and paused/idle state.
        if not self.accepting_answers or not self.answer_buttons[index].isEnabled():
            return
        if self.session.current_question is None:
            return
        chosen_button = self.answer_buttons[index]
        chosen_name = chosen_button.text()
        q = self.session.current_question

        result = self.session.submit_answer(chosen_name)
        correct_names = "/".join(Note(midi=result.midi_note).names)
        canonical = pitch_class_names(name_to_pitch_class(chosen_name))[0]

        for btn in self.answer_buttons:
            btn.setEnabled(False)

        if result.correct:
            self._set_feedback("Correct!", "good")
            chosen_button.set_tone("good")
            play_note_tone(result.midi_note)
        else:
            self._set_feedback(f"Incorrect. The correct answer was {correct_names}.", "bad")
            chosen_button.set_tone("bad")

        self._record(
            result,
            f"String {q.string}, fret {q.fret}: was {correct_names}, you answered {chosen_name}",
            given_note_name=canonical,
        )

    def _on_quiz_stopped(self) -> None:
        for btn in self.answer_buttons:
            btn.setText("")
            btn.setEnabled(False)
            btn.set_tone(None)

    def _set_extra_hidden(self, hidden: bool) -> None:
        if hidden:
            self._saved_buttons = [(b.text(), b.isEnabled(), b._tone) for b in self.answer_buttons]
            for b in self.answer_buttons:
                b.setText("")
                b.setEnabled(False)
        else:
            for b, (text, enabled, tone) in zip(self.answer_buttons, getattr(self, "_saved_buttons", [])):
                b.setText(text)
                b.setEnabled(enabled)
                b.set_tone(tone)
