"""
ui/shared_state.py

A single Fretboard instance shared by Quiz 1, Quiz 2 and Diagnostics, so
the active strings AND the active fret range stay in sync everywhere.
Both are persisted via core.prefs. Also tracks whether a quiz is running,
so selectors in every tab lock while one is (and a second quiz can't be
started at the same time).
"""

from PyQt6.QtCore import QObject, pyqtSignal

from core.fretboard import Fretboard
from core.prefs import Prefs


class SharedFretboardState(QObject):
    strings_changed = pyqtSignal(set)        # new set of enabled strings
    fret_range_changed = pyqtSignal(int, int)  # (fret_min, fret_max)
    quiz_running_changed = pyqtSignal(bool)

    _instance: "SharedFretboardState | None" = None

    def __init__(self):
        super().__init__()
        self.fretboard = Fretboard()
        self.quiz_running = False
        prefs = Prefs.instance()

        saved = prefs.get("enabled_strings")
        valid = {s for s in saved if isinstance(s, int) and s in self.fretboard.tuning}
        self.fretboard.enabled_strings = valid  # an empty set is a legal saved state
        self.fretboard.set_fret_range(prefs.get("fret_min"), prefs.get("fret_max"))

    @classmethod
    def instance(cls) -> "SharedFretboardState":
        if cls._instance is None:
            cls._instance = SharedFretboardState()
        return cls._instance

    def set_string_enabled(self, string: int, enabled: bool) -> bool:
        try:
            self.fretboard.set_string_enabled(string, enabled)
        except ValueError:
            return False
        Prefs.instance().set("enabled_strings", self.fretboard.get_enabled_strings())
        self.strings_changed.emit(set(self.fretboard.enabled_strings))
        return True

    def set_fret_range(self, lo: int, hi: int) -> None:
        self.fretboard.set_fret_range(lo, hi)
        prefs = Prefs.instance()
        prefs.set("fret_min", self.fretboard.fret_min)
        prefs.set("fret_max", self.fretboard.fret_max)
        self.fret_range_changed.emit(self.fretboard.fret_min, self.fretboard.fret_max)

    def set_quiz_running(self, running: bool) -> None:
        if self.quiz_running != running:
            self.quiz_running = running
            self.quiz_running_changed.emit(running)
