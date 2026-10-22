"""
ui/quiz2_panel.py

Quiz Mode 2: Note -> Fret. Names a note on a string ("Find C# on string
3"); click the fretboard. Either valid fret (within the active fret range)
is accepted. Shared machinery lives in ui/quiz_panel_base.py.
"""

from core.notes import pitch_class_names
from core.quiz2 import QuizSession
from data.db import QUIZ_MODE_NOTE_TO_FRET
from ui.audio import play_note_tone
from ui.quiz_panel_base import QuizPanelBase


class Quiz2Panel(QuizPanelBase):
    QUIZ_MODE = QUIZ_MODE_NOTE_TO_FRET
    DURATION_PREF = "quiz2_duration"

    def _make_session(self):
        return QuizSession(self.fretboard)

    def _build_answer_area(self, layout) -> None:
        self.fretboard_widget.position_clicked.connect(self._on_fret_clicked)

    def _present_question(self, question) -> None:
        self.fretboard_widget.clear_highlights()
        self.fretboard_widget.set_interactive(True)
        self.prompt_label.setText(question.prompt_text)

    def _on_fret_clicked(self, string: int, fret: int) -> None:
        if not self.accepting_answers or self.session.current_question is None:
            return
        question = self.session.current_question  # capture before submit clears it
        correct_positions = [(question.string, f) for f in question.valid_frets]

        result = self.session.submit_answer(string, fret)
        clicked_note = self.fretboard.note_at(string, fret)
        canonical = pitch_class_names(clicked_note.pitch_class)[0]

        self.fretboard_widget.set_interactive(False)
        self.fretboard_widget.show_answer_feedback(correct_positions, (string, fret))

        clicked_names = "/".join(clicked_note.names)
        if result.correct:
            self._set_feedback("Correct!", "good")
            play_note_tone(result.midi_note)
        else:
            self._set_feedback(f"Incorrect. That note was {clicked_names}.", "bad")

        self._record(
            result,
            f"{question.prompt_text}: you clicked string {string}, fret {fret} ({clicked_names})",
            given_string=string, given_fret=fret, given_note_name=canonical,
        )
