"""
ui/selection_widgets.py

Active Strings and Fret Range cards, shared by Quiz 1, Quiz 2 and
Diagnostics. Bound to SharedFretboardState, so changing one anywhere
updates all of them. Both lock while a quiz is running.
"""

from PyQt6.QtWidgets import QHBoxLayout, QLabel

from ui.kit import Card, Stepper, ToggleChip
from ui.shared_state import SharedFretboardState
from ui.theme import skin


class StringSelector(Card):
    def __init__(self, parent=None):
        super().__init__("Active strings", "white", parent=parent)
        self._state = SharedFretboardState.instance()
        row = QHBoxLayout()
        row.setSpacing(8)
        self.checkboxes: dict[int, ToggleChip] = {}
        for string in range(1, 7):
            chip = ToggleChip(f"{string}")
            chip.setChecked(self._state.fretboard.is_string_enabled(string))
            chip.setMinimumWidth(44)
            chip.toggled.connect(lambda checked, s=string: self._state.set_string_enabled(s, checked))
            row.addWidget(chip)
            self.checkboxes[string] = chip
        row.addStretch()
        self.body.addLayout(row)
        self._state.strings_changed.connect(self._sync)
        self._state.quiz_running_changed.connect(lambda running: self.setEnabled(not running))
        self.setEnabled(not self._state.quiz_running)

    def _sync(self, enabled: set) -> None:
        for string, chip in self.checkboxes.items():
            chip.blockSignals(True)
            chip.setChecked(string in enabled)
            chip.blockSignals(False)
            chip.update()


class FretRangeSelector(Card):
    def __init__(self, parent=None):
        super().__init__("Fret range", "pink", parent=parent)
        self._state = SharedFretboardState.instance()
        fb = self._state.fretboard
        row = QHBoxLayout()
        row.setSpacing(8)
        self.min_spin = Stepper(0, fb.max_fret, fb.fret_min)
        self.max_spin = Stepper(0, fb.max_fret, fb.fret_max)
        self._to = QLabel("TO")
        self._to.setFont(skin().font("display", 13))
        row.addWidget(self.min_spin)
        row.addWidget(self._to)
        row.addWidget(self.max_spin)
        row.addStretch()
        self.body.addLayout(row)
        self.min_spin.valueChanged.connect(self._on_min)
        self.max_spin.valueChanged.connect(self._on_max)
        self._state.fret_range_changed.connect(self._sync)
        self._state.quiz_running_changed.connect(lambda running: self.setEnabled(not running))
        self.setEnabled(not self._state.quiz_running)

    def _on_min(self, lo: int) -> None:
        self._state.set_fret_range(lo, max(lo, self.max_spin.value()))

    def _on_max(self, hi: int) -> None:
        self._state.set_fret_range(min(hi, self.min_spin.value()), hi)

    def _sync(self, lo: int, hi: int) -> None:
        for spin, value in ((self.min_spin, lo), (self.max_spin, hi)):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
            spin.field.update()
