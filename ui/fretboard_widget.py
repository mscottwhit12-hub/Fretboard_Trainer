"""
ui/fretboard_widget.py

The central visual element of the app: a flat, minimal fretboard graphic.
Deliberately NOT wood-textured or skeuomorphic, per the design spec.

Colors are theme-driven (see ui/theme.py) rather than hardcoded, so the
board recolors along with the rest of the UI when the user picks a theme
in Settings. Only the wrong-guess ring stays a fixed red -- that's a
semantic "incorrect" signal, not a decorative color.

This widget is reused, unmodified, by every quiz mode plus Diagnostics:
- Quiz Mode 1: highlights ONE prompted position (display-only)
- Quiz Mode 2: interactive -- the user clicks a position to answer, and
  the board shows the correct position(s) plus a wrong-guess ring if
  needed via `show_answer_feedback`.
- Diagnostics: `set_heatmap_data` colors every position by accuracy
  instead of showing highlight dots -- display-only, not interactive.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtWidgets import QToolTip

from core.fretboard import Fretboard
from ui.theme import SkinManager


# Standard single-dot fret markers, and the one double-dot fret (12).
SINGLE_DOT_FRETS = {3, 5, 7, 9, 15}
DOUBLE_DOT_FRETS = {12}

MARGIN_LEFT = 46
MARGIN_RIGHT = 24
MARGIN_TOP = 20
MARGIN_BOTTOM = 20
NOTE_RADIUS = 15
HEATMAP_DOT_RADIUS = 10
HEATMAP_NO_DATA_RADIUS = 4


class FretboardWidget(QWidget):
    # Emitted only when interactive mode is on -- (string, fret) nearest the click.
    position_clicked = pyqtSignal(int, int)

    def __init__(self, fretboard: Fretboard, parent=None):
        super().__init__(parent)
        self.fretboard = fretboard
        self.highlighted_positions: set[tuple[int, int]] = set()
        self._wrong_guess_position: tuple[int, int] | None = None
        self._interactive = False
        self._heatmap_stats: dict[tuple[int, int], object] | None = None
        self._heatmap_tooltips: dict[tuple[int, int], str] | None = None
        self._content_hidden = False   # quiz paused: hide the question
        self._dim_outside_range = False
        self.setMinimumSize(640, 205)
        self.setMouseTracking(True)

        self._skin_manager = SkinManager.instance()
        self._skin_manager.skin_changed.connect(lambda _s: self.update())

    # --- public interface -------------------------------------------------

    def set_interactive(self, enabled: bool) -> None:
        """Quiz Mode 2 clicks the board to answer; Quiz Mode 1 does not.
        Off by default so existing display-only usage is unaffected."""
        self._interactive = enabled

    def set_highlighted_positions(self, positions) -> None:
        """positions: iterable of (string, fret) tuples to highlight."""
        self.highlighted_positions = set(positions)
        self.update()

    def show_answer_feedback(self, correct_positions, guess_position=None) -> None:
        """Highlights every valid correct position in the accent color. If
        a wrong guess was made (not itself one of the correct positions),
        also rings it in red so the user sees both where they clicked and
        where the note actually was."""
        self.highlighted_positions = set(correct_positions)
        self._wrong_guess_position = (
            guess_position if guess_position not in self.highlighted_positions else None
        )
        self.update()

    def clear_highlights(self) -> None:
        self.highlighted_positions = set()
        self._wrong_guess_position = None
        self.update()

    def set_heatmap_data(self, stats: dict[tuple[int, int], object] | None) -> None:
        """stats: dict of (string, fret) -> an object exposing `.attempts`
        (int) and `.accuracy` (float, 0-1) -- either core/diagnostics.py's
        PositionStat (accuracy metric) or HeatmapCell (speed metric, where
        `.accuracy` is really a relative speed score, not a % correct).
        Pass None to turn the heatmap layer off. Renders as colored dots
        across every position on the board, regardless of which strings
        are currently toggled on/off, since this is showing historical
        data, not the current quiz setup."""
        self._heatmap_stats = stats
        self.update()

    def set_heatmap_tooltips(self, tooltips: dict[tuple[int, int], str] | None) -> None:
        """Hover text per (string, fret). Positions missing from the dict
        get a generic 'no data' tooltip. None turns tooltips off."""
        self._heatmap_tooltips = tooltips

    def set_content_hidden(self, hidden: bool) -> None:
        """Used while a quiz is paused: hides highlights/feedback and
        ignores clicks so the question can't be studied during a pause."""
        self._content_hidden = hidden
        self.update()

    def set_range_dimming(self, enabled: bool) -> None:
        """Fade frets outside fretboard.fret_min..fret_max."""
        self._dim_outside_range = enabled
        self.update()

    def refresh(self) -> None:
        """Call after changing fretboard.enabled_strings so the display updates."""
        self.update()

    # --- geometry helpers ---------------------------------------------------

    @property
    def _sk(self):
        return self._skin_manager.skin

    def _num_strings(self) -> int:
        return len(self.fretboard.tuning)

    def _max_fret(self) -> int:
        return self.fretboard.max_fret

    def _playable_width(self) -> float:
        return self.width() - MARGIN_LEFT - MARGIN_RIGHT

    def _playable_height(self) -> float:
        return self.height() - MARGIN_TOP - MARGIN_BOTTOM

    def _fret_spacing(self) -> float:
        return self._playable_width() / self._max_fret()

    def _string_spacing(self) -> float:
        n = self._num_strings()
        return self._playable_height() / (n - 1) if n > 1 else 0

    def _fret_line_x(self, fret: int) -> float:
        """X coordinate of the physical fret wire (0 = the nut)."""
        return MARGIN_LEFT + fret * self._fret_spacing()

    def _note_x(self, fret: int) -> float:
        """X coordinate where a note dot for this fret is drawn (between two fret wires)."""
        if fret == 0:
            return self._fret_line_x(0)  # open string: right on the nut
        return self._fret_line_x(fret - 1) + self._fret_spacing() / 2

    def _string_y(self, string: int) -> float:
        """String 1 (high E) is drawn at the top, string 6 (low E) at the bottom."""
        return MARGIN_TOP + (string - 1) * self._string_spacing()

    # --- painting -------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self._draw_fret_markers(painter)
        self._draw_fret_lines(painter)
        self._draw_strings(painter)
        self._draw_string_labels(painter)
        if self._dim_outside_range:
            self._draw_range_dim(painter)
        if not self._content_hidden:
            self._draw_highlights(painter)
            self._draw_wrong_guess(painter)
        self._draw_heatmap(painter)

    def _position_at(self, x: float, y: float, radius: float = 16.0):
        """Nearest (string, fret) within `radius` px of a point, else None."""
        best, best_d = None, radius
        for s in range(1, self._num_strings() + 1):
            for f in range(0, self._max_fret() + 1):
                d = ((self._note_x(f) - x) ** 2 + (self._string_y(s) - y) ** 2) ** 0.5
                if d <= best_d:
                    best, best_d = (s, f), d
        return best

    def mouseMoveEvent(self, event) -> None:
        if self._heatmap_tooltips is None or self._heatmap_stats is None:
            QToolTip.hideText()
            return
        pos = event.position()
        hit = self._position_at(pos.x(), pos.y())
        if hit is None:
            QToolTip.hideText()
            return
        text = self._heatmap_tooltips.get(hit)
        if text is None:
            names = "/".join(self.fretboard.note_at(*hit).names)
            text = f"String {hit[0]}, fret {hit[1]} ({names})\nNo data"
        QToolTip.showText(event.globalPosition().toPoint(), text, self)

    def _draw_range_dim(self, painter: QPainter) -> None:
        fb = self.fretboard
        color = QColor(self._sk.board_bg)
        color.setAlpha(190)
        top, height = 0, self.height()
        if fb.fret_min > 0:
            x1 = self._fret_line_x(fb.fret_min - 1)
            x0 = self._fret_line_x(0) - 12
            painter.fillRect(QRectF(x0, top, x1 - x0, height), color)
        if fb.fret_max < fb.max_fret:
            x0 = self._fret_line_x(fb.fret_max)
            painter.fillRect(QRectF(x0, top, self.width() - x0, height), color)

    def mousePressEvent(self, event) -> None:
        if not self._interactive or self._content_hidden:
            return
        pos = event.position()
        string = min(
            range(1, self._num_strings() + 1),
            key=lambda s: abs(self._string_y(s) - pos.y()),
        )
        fret = min(
            range(0, self._max_fret() + 1),
            key=lambda f: abs(self._note_x(f) - pos.x()),
        )
        self.position_clicked.emit(string, fret)

    def _draw_fret_lines(self, painter: QPainter) -> None:
        top = self._string_y(1)
        bottom = self._string_y(self._num_strings())
        for fret in range(0, self._max_fret() + 1):
            x = self._fret_line_x(fret)
            pen = QPen(QColor(self._sk.board_wire))
            pen.setWidth(6 if fret == 0 else 2)
            painter.setPen(pen)
            painter.drawLine(int(x), int(top), int(x), int(bottom))

    def _draw_strings(self, painter: QPainter) -> None:
        left = self._fret_line_x(0)
        right = self._fret_line_x(self._max_fret())
        enabled_color = QColor(self._sk.board_string)
        disabled_color = QColor(self._sk.board_string_off)
        for string in range(1, self._num_strings() + 1):
            y = self._string_y(string)
            enabled = self.fretboard.is_string_enabled(string)
            color = enabled_color if enabled else disabled_color
            # Thicker strings (lower pitch, higher string number) drawn slightly bolder.
            pen = QPen(color)
            pen.setWidth(2 + string // 3)
            painter.setPen(pen)
            painter.drawLine(int(left), int(y), int(right), int(y))

    def _draw_string_labels(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor(self._sk.board_label)))
        painter.setFont(self._sk.font("bold", 15))
        for string in range(1, self._num_strings() + 1):
            y = self._string_y(string)
            painter.drawText(
                QRectF(2, y - 10, MARGIN_LEFT - 22, 20),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                str(string),
            )

    def _draw_fret_markers(self, painter: QPainter) -> None:
        top = self._string_y(1)
        bottom = self._string_y(self._num_strings())
        mid = (top + bottom) / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(self._sk.board_marker)))
        for fret in range(1, self._max_fret() + 1):
            x = self._note_x(fret)
            if fret in DOUBLE_DOT_FRETS:
                painter.drawEllipse(QRectF(x - 7, mid - 26, 14, 14))
                painter.drawEllipse(QRectF(x - 7, mid + 12, 14, 14))
            elif fret in SINGLE_DOT_FRETS:
                painter.drawEllipse(QRectF(x - 7, mid - 7, 14, 14))

    def _draw_highlights(self, painter: QPainter) -> None:
        accent = QColor(self._sk.board_highlight)
        edge = QPen(QColor(self._sk.board_wire), 3)
        for string, fret in self.highlighted_positions:
            if not (0 <= fret <= self._max_fret()):
                continue
            x = self._note_x(fret)
            y = self._string_y(string)
            painter.setPen(edge)
            painter.setBrush(QBrush(accent))
            painter.drawEllipse(QRectF(x - NOTE_RADIUS, y - NOTE_RADIUS, NOTE_RADIUS * 2, NOTE_RADIUS * 2))

    def _draw_wrong_guess(self, painter: QPainter) -> None:
        if self._wrong_guess_position is None:
            return
        string, fret = self._wrong_guess_position
        if not (0 <= fret <= self._max_fret()):
            return
        x = self._note_x(fret)
        y = self._string_y(string)
        pen = QPen(QColor(self._sk.board_wrong))
        pen.setWidth(5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        r = NOTE_RADIUS + 5
        painter.drawEllipse(QRectF(x - r, y - r, r * 2, r * 2))

    def _draw_heatmap(self, painter: QPainter) -> None:
        if self._heatmap_stats is None:
            return
        no_data_color = QColor(self._sk.board_nodata)
        painter.setPen(Qt.PenStyle.NoPen)
        outline = QPen(QColor(self._sk.board_wire), 2)
        for string in range(1, self._num_strings() + 1):
            for fret in range(0, self._max_fret() + 1):
                x = self._note_x(fret)
                y = self._string_y(string)
                stat = self._heatmap_stats.get((string, fret))
                if stat is None or stat.attempts == 0:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(no_data_color))
                    r = HEATMAP_NO_DATA_RADIUS
                else:
                    painter.setPen(outline)
                    painter.setBrush(QBrush(QColor(self._sk.heatmap_color(stat.accuracy))))
                    r = HEATMAP_DOT_RADIUS
                painter.drawEllipse(QRectF(x - r, y - r, r * 2, r * 2))
