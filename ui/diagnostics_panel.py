"""
ui/diagnostics_panel.py

Diagnostics tab: surfaces "struggle points" from quiz history.

SCOPE (for now): position-based only -- a per-(string, fret) accuracy
heatmap, plus (Quiz Mode 2 only) a ranked list of which wrong position
tends to get clicked instead of the target. Note-name / music-theory
analysis is intentionally deferred (see core/diagnostics.py's docstring)
-- data/db.py already logs what's needed for it (given_note_name), so
adding that later is a new section here, not a restructuring of this file.

Timeframe and quiz-mode filters, and the heatmap's colors themselves, are
all driven by core/diagnostics.py and ui/theme.py respectively -- this
file is just the layout gluing them together.
"""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget,
)

from core.diagnostics import (
    position_accuracy, position_confusions, position_speed,
    rank_worst_cells, speed_heatmap_cells, weakest_positions,
)
from data.db import HistoryDB, QUIZ_MODE_FRET_TO_NOTE, QUIZ_MODE_NOTE_TO_FRET
from ui.fretboard_widget import FretboardWidget
from ui.kit import Card, Segmented, SkinButton, Stepper
from ui.selection_widgets import FretRangeSelector, StringSelector
from ui.shared_state import SharedFretboardState
from ui.theme import SkinManager, skin

MODE_ALL = "All modes"
MODE_FRET_TO_NOTE = "Fret \u2192 Note"
MODE_NOTE_TO_FRET = "Note \u2192 Fret"

_MODE_MAP = {
    MODE_ALL: None,
    MODE_FRET_TO_NOTE: QUIZ_MODE_FRET_TO_NOTE,
    MODE_NOTE_TO_FRET: QUIZ_MODE_NOTE_TO_FRET,
}

METRIC_ACCURACY = "Accuracy"
METRIC_SPEED = "Speed"
TIME_ALL = "All time"
TIME_RECENT = "Last N"


class _HeatmapLegend(QWidget):
    """Gradient bar previewing the skin's 0% -> 100% heatmap scale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        SkinManager.instance().skin_changed.connect(lambda _s: self.update())
        self.setFixedHeight(26)
        self.setMinimumWidth(160)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        sk = skin()
        w, h = self.width() - 6, self.height() - 6
        steps = 48
        for i in range(steps):
            x0 = 3 + i / steps * w
            painter.fillRect(QRectF(x0, 3, w / steps + 1, h), QColor(sk.heatmap_color((i + 0.5) / steps)))
        painter.setPen(QPen(QColor(sk.ink), 3))
        painter.drawRoundedRect(QRectF(2, 2, self.width() - 4, self.height() - 4), 6, 6)


class DiagnosticsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = HistoryDB()
        self._shared_strings = SharedFretboardState.instance()
        self.fretboard = self._shared_strings.fretboard
        self._shared_strings.strings_changed.connect(lambda _s: self._on_selection_changed())
        self._shared_strings.fret_range_changed.connect(lambda _a, _b: self._on_selection_changed())

        self._build_ui()
        self._refresh()

    # --- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        filters = QHBoxLayout()
        filters.setSpacing(14)
        metric_card = Card("Metric", "white")
        self.metric_combo = Segmented([METRIC_ACCURACY, METRIC_SPEED])
        self.metric_combo.currentTextChanged.connect(lambda _t: self._refresh())
        metric_card.body.addWidget(self.metric_combo)
        filters.addWidget(metric_card)

        mode_card = Card("Quiz mode", "white")
        self.mode_combo = Segmented([MODE_ALL, MODE_FRET_TO_NOTE, MODE_NOTE_TO_FRET])
        self.mode_combo.currentTextChanged.connect(lambda _t: self._refresh())
        mode_card.body.addWidget(self.mode_combo)
        filters.addWidget(mode_card, stretch=1)
        root.addLayout(filters)

        row2 = QHBoxLayout()
        row2.setSpacing(14)
        time_card = Card("Timeframe", "blue", badge="N = sessions")
        trow = QHBoxLayout()
        trow.setSpacing(10)
        self.timeframe = Segmented([TIME_ALL, TIME_RECENT])
        self.timeframe.currentTextChanged.connect(lambda _t: self._refresh())
        trow.addWidget(self.timeframe)
        self.session_spinbox = Stepper(1, 100, 5)
        self.session_spinbox.valueChanged.connect(self._on_session_count_changed)
        trow.addWidget(self.session_spinbox)
        time_card.body.addLayout(trow)
        row2.addWidget(time_card, stretch=1)
        row2.addWidget(FretRangeSelector(), stretch=1)
        root.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(14)
        self.string_selector = StringSelector()
        row3.addWidget(self.string_selector)
        row3.addStretch()
        export_btn = SkinButton("Export CSV", "secondary")
        export_btn.setMinimumWidth(130)
        export_btn.clicked.connect(self._export_csv)
        reset_btn = SkinButton("Reset history", "danger")
        reset_btn.setMinimumWidth(130)
        reset_btn.clicked.connect(self._reset_history)
        row3.addWidget(export_btn)
        row3.addWidget(reset_btn)
        root.addLayout(row3)

        board_card = Card("Heatmap", "white", pad=10)
        self.heatmap_widget = FretboardWidget(self.fretboard)
        self.heatmap_widget.set_range_dimming(True)
        board_card.body.addWidget(self.heatmap_widget)
        legend_row = QHBoxLayout()
        self._struggle = QLabel("STRUGGLING")
        self._master = QLabel("MASTERED")
        legend_row.addWidget(self._struggle)
        legend_row.addWidget(_HeatmapLegend(), stretch=1)
        legend_row.addWidget(self._master)
        board_card.body.addLayout(legend_row)
        self.no_data_note = QLabel("")
        board_card.body.addWidget(self.no_data_note)
        root.addWidget(board_card)

        summary_card = Card("Summary", "green")
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        summary_card.body.addWidget(self.summary_label)
        root.addWidget(summary_card)

        mix_card = Card("Position mix-ups", "pink", badge="Note \u2192 Fret only")
        self.confusions_note = QLabel(
            "Which wrong spot gets clicked instead of the target. Not shown for Fret \u2192 Note, "
            "since there's no position to guess there."
        )
        self.confusions_note.setWordWrap(True)
        mix_card.body.addWidget(self.confusions_note)
        self.confusions_label = QLabel("")
        self.confusions_label.setWordWrap(True)
        mix_card.body.addWidget(self.confusions_label)
        root.addWidget(mix_card)

        root.addStretch()

        self._apply_fonts()
        SkinManager.instance().skin_changed.connect(lambda _s: self._apply_fonts())

    def _apply_fonts(self) -> None:
        sk = skin()
        for lbl in (self._struggle, self._master):
            lbl.setFont(sk.font("display", 12))
        for lbl in (self.no_data_note, self.confusions_note):
            lbl.setFont(sk.font("body", 13))
        for lbl in (self.summary_label, self.confusions_label):
            lbl.setFont(sk.font("bold", 15))

    def _on_selection_changed(self) -> None:
        """Strings or fret range changed (from any tab)."""
        self.heatmap_widget.refresh()
        self._refresh()

    # --- history management ---------------------------------------------------

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export history", "fretboard_history.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            count = self.db.export_csv(path)
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        QMessageBox.information(self, "Export complete", f"Exported {count} attempts.")

    def _reset_history(self) -> None:
        total = self.db.count_attempts()
        if total == 0:
            QMessageBox.information(self, "Nothing to reset", "No history recorded yet.")
            return
        answer = QMessageBox.question(
            self, "Reset history",
            f"Permanently delete all {total} recorded attempts? This cannot be undone.\n"
            "(Tip: use Export CSV first if you want a backup.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self._refresh()

    def refresh(self) -> None:
        """Public: re-query (called when this tab is opened)."""
        self._refresh()

    # --- data flow -------------------------------------------------------------

    def _on_session_count_changed(self, _value: int) -> None:
        if self.timeframe.currentText() == TIME_RECENT:
            self._refresh()

    def _current_quiz_mode(self) -> str | None:
        return _MODE_MAP[self.mode_combo.currentText()]

    def _current_session_limit(self) -> int | None:
        return self.session_spinbox.value() if self.timeframe.currentText() == TIME_RECENT else None

    def _current_strings(self) -> set[int]:
        return set(self.fretboard.get_enabled_strings())

    def _current_frets(self) -> tuple[int, int]:
        return (self.fretboard.fret_min, self.fretboard.fret_max)

    def _refresh(self) -> None:
        if self.metric_combo.currentText() == METRIC_SPEED:
            self.no_data_note.setText(
                "Small dots = no correct answers logged yet for this position/filter. Hover a dot for details."
            )
            self._refresh_speed()
        else:
            self.no_data_note.setText("Small dots = not attempted yet in this view. Hover a dot for details.")
            self._refresh_accuracy()

        # Position confusions are Quiz Mode 2 only regardless of the mode
        # filter above -- see core/diagnostics.py's docstring for why.
        session_limit = self._current_session_limit()
        confusions = position_confusions(
            self.db, session_limit=session_limit, strings=self._current_strings(), frets=self._current_frets(), limit=8,
        )
        if not confusions:
            self.confusions_label.setText("No repeated mix-ups yet for this filter.")
        else:
            lines = [
                f"Target string {c.target_string} fret {c.target_fret} \u2192 "
                f"clicked string {c.given_string} fret {c.given_fret} ({c.count}\u00d7)"
                for c in confusions
            ]
            self.confusions_label.setText("\n".join(lines))

    def _pos_title(self, pos: tuple[int, int]) -> str:
        names = "/".join(self.fretboard.note_at(*pos).names)
        return f"String {pos[0]}, fret {pos[1]} ({names})"

    def _refresh_accuracy(self) -> None:
        quiz_mode = self._current_quiz_mode()
        session_limit = self._current_session_limit()
        strings = self._current_strings()
        frets = self._current_frets()

        stats = position_accuracy(
            self.db, quiz_mode=quiz_mode, session_limit=session_limit, strings=strings, frets=frets,
        )
        self.heatmap_widget.set_heatmap_data(stats)
        times = position_speed(
            self.db, quiz_mode=quiz_mode, session_limit=session_limit, strings=strings, frets=frets,
        )
        tips = {}
        for pos, st in stats.items():
            tip = f"{self._pos_title(pos)}\nAccuracy: {st.accuracy * 100:.0f}% ({st.correct}/{st.attempts})"
            if pos in times:
                tip += f"\nAvg time (correct): {times[pos].average_response_time_ms / 1000:.2f}s"
            tips[pos] = tip
        self.heatmap_widget.set_heatmap_tooltips(tips)

        attempted = [s for s in stats.values() if s.attempts > 0]
        if not attempted:
            self.summary_label.setText("No attempts recorded yet for this filter.")
            return

        total_attempts = sum(s.attempts for s in attempted)
        total_correct = sum(s.correct for s in attempted)
        overall = total_correct / total_attempts * 100
        worst = weakest_positions(
            self.db, quiz_mode=quiz_mode, session_limit=session_limit, strings=strings, frets=frets,
            min_attempts=2, limit=5,
        )
        if worst:
            worst_text = ", ".join(
                f"string {s.string} fret {s.fret} ({s.correct}/{s.attempts})" for s in worst
            )
        else:
            worst_text = "not enough repeated attempts at any single position yet"
        self.summary_label.setText(
            f"{total_attempts} attempts across {len(attempted)} positions -- "
            f"{overall:.0f}% overall accuracy.\nWeakest spots: {worst_text}"
        )

    def _refresh_speed(self) -> None:
        quiz_mode = self._current_quiz_mode()
        session_limit = self._current_session_limit()
        strings = self._current_strings()
        frets = self._current_frets()

        cells = speed_heatmap_cells(
            self.db, quiz_mode=quiz_mode, session_limit=session_limit, strings=strings, frets=frets,
        )
        self.heatmap_widget.set_heatmap_data(cells)
        speeds = position_speed(
            self.db, quiz_mode=quiz_mode, session_limit=session_limit, strings=strings, frets=frets,
        )
        self.heatmap_widget.set_heatmap_tooltips({
            pos: f"{self._pos_title(pos)}\nAvg time: {sp.average_response_time_ms / 1000:.2f}s "
                 f"({sp.correct_attempts} correct answers)"
            for pos, sp in speeds.items()
        })

        if not cells:
            self.summary_label.setText(
                "No correct answers recorded yet for this filter -- speed is only "
                "measured on correct answers."
            )
            return

        raw_times = position_speed(
            self.db, quiz_mode=quiz_mode, session_limit=session_limit, strings=strings, frets=frets,
        )
        fastest = min(raw_times.values(), key=lambda s: s.average_response_time_ms)
        slowest = max(raw_times.values(), key=lambda s: s.average_response_time_ms)
        worst = rank_worst_cells(cells, min_attempts=2, limit=5)
        if worst:
            worst_text = ", ".join(
                f"string {pos[0]} fret {pos[1]} (avg {raw_times[pos].average_response_time_ms:.0f}ms)"
                for pos, _cell in worst
            )
        else:
            worst_text = "not enough repeated correct answers at any single position yet"
        self.summary_label.setText(
            f"Fastest: string {fastest.string} fret {fastest.fret} "
            f"({fastest.average_response_time_ms:.0f}ms avg). "
            f"Slowest: string {slowest.string} fret {slowest.fret} "
            f"({slowest.average_response_time_ms:.0f}ms avg).\n"
            f"Slowest to answer: {worst_text}"
        )

    # --- lifecycle -------------------------------------------------------------

    def shutdown(self) -> None:
        self.db.close()
