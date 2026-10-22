"""
ui/main_window.py

Top-level shell: left sidebar navigation + page header + the four pages
(Fret -> Note, Note -> Fret, Diagnostics, Settings). Layout is identical
for every skin; the skin only decides how it is painted.
"""

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout, QMainWindow, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from core.prefs import Prefs
from ui.diagnostics_panel import DiagnosticsPanel
from ui.disclosure import AIDisclosureBanner
from ui.kit import Backdrop, PageHeader, Sidebar
from ui.quiz1_panel import Quiz1Panel
from ui.quiz2_panel import Quiz2Panel
from ui.settings_panel import SettingsPanel

PAGES = [
    ("Fret → Note", "Quiz mode 1", "Fret → Note"),
    ("Note → Fret", "Quiz mode 2", "Note → Fret"),
    ("Diagnostics", "Insights", "Diagnostics"),
    ("Settings", "Preferences", "Settings"),
]


def _scrolled(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.viewport().setAutoFillBackground(False)
    holder = QWidget()
    lay = QVBoxLayout(holder)
    lay.setContentsMargins(2, 2, 12, 6)
    lay.addWidget(widget)
    area.setWidget(holder)
    holder.setAutoFillBackground(False)  # let the cream backdrop show through
    return area


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fretboard Trainer")
        self.resize(1180, 960)
        self.setMinimumSize(1100, 640)
        self._restore_geometry()

        self.quiz1_panel = Quiz1Panel()
        self.quiz2_panel = Quiz2Panel()
        self.diagnostics_panel = DiagnosticsPanel()
        self.settings_panel = SettingsPanel()

        central = Backdrop()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.sidebar = Sidebar("Fretboard Trainer", [p[0] for p in PAGES], footer=AIDisclosureBanner())
        h.addWidget(self.sidebar)

        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(28, 18, 16, 8)
        v.setSpacing(14)
        self.header = PageHeader()
        v.addWidget(self.header)
        self.stack = QStackedWidget()
        for panel in (self.quiz1_panel, self.quiz2_panel, self.diagnostics_panel, self.settings_panel):
            self.stack.addWidget(_scrolled(panel))
        v.addWidget(self.stack)
        h.addWidget(content, stretch=1)
        self.setCentralWidget(central)

        self.sidebar.page_selected.connect(self.show_page)
        self.show_page(0)

        # Ctrl+1..4 jump between pages; Ctrl+M toggles mute.
        for i in range(len(PAGES)):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self).activated.connect(lambda idx=i: self.show_page(idx))
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._toggle_mute)

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.select(index)
        _label, kicker, title = PAGES[index]
        self.header.set_page(kicker, title)
        if index == 2:
            self.diagnostics_panel.refresh()  # pick up quizzes finished since last view

    def _toggle_mute(self) -> None:
        prefs = Prefs.instance()
        prefs.set("sound_muted", not prefs.get("sound_muted"))
        self.statusBar().showMessage("Sound muted" if prefs.get("sound_muted") else "Sound on", 2000)

    def _restore_geometry(self) -> None:
        saved = Prefs.instance().get("window_geometry")
        if saved:
            try:
                self.restoreGeometry(QByteArray.fromHex(saved.encode("ascii")))
            except (ValueError, UnicodeError):
                pass

    def closeEvent(self, event) -> None:
        Prefs.instance().set("window_geometry", bytes(self.saveGeometry().toHex()).decode("ascii"))
        self.quiz1_panel.shutdown()
        self.quiz2_panel.shutdown()
        self.diagnostics_panel.shutdown()
        super().closeEvent(event)
