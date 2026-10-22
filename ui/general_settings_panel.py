"""
ui/general_settings_panel.py

General settings: sound (mute / volume / test) and the 3-2-1 pre-quiz
countdown. Values live in core.prefs; re-syncs each time it is shown so
the Ctrl+M mute shortcut stays in step.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from core.prefs import Prefs
from ui.audio import play_note_tone
from ui.kit import Card, SkinButton, SkinCheck
from ui.theme import SkinManager, skin


class GeneralSettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._prefs = Prefs.instance()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        sound = Card("Sound", "yellow")
        self.mute_checkbox = SkinCheck("Mute sound  (Ctrl+M)")
        self.mute_checkbox.toggled.connect(lambda v: self._prefs.set("sound_muted", v))
        sound.body.addWidget(self.mute_checkbox)

        row = QHBoxLayout()
        row.setSpacing(12)
        self._vol_title = QLabel("VOLUME")
        row.addWidget(self._vol_title)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setMinimumHeight(36)
        self.volume_slider.valueChanged.connect(self._on_volume)
        row.addWidget(self.volume_slider, stretch=1)
        self.volume_label = QLabel("")
        self.volume_label.setMinimumWidth(52)
        row.addWidget(self.volume_label)
        test = SkinButton("Test sound", "small")
        test.clicked.connect(lambda: play_note_tone(69, force=True))
        row.addWidget(test)
        sound.body.addLayout(row)
        root.addWidget(sound)

        quiz = Card("Quiz", "blue")
        self.precount_checkbox = SkinCheck("3-2-1 countdown before a quiz starts")
        self.precount_checkbox.toggled.connect(lambda v: self._prefs.set("precount_enabled", v))
        quiz.body.addWidget(self.precount_checkbox)
        root.addWidget(quiz)
        root.addStretch()

        self._apply_fonts()
        SkinManager.instance().skin_changed.connect(lambda _s: self._apply_fonts())
        self._sync()

    def _apply_fonts(self) -> None:
        self._vol_title.setFont(skin().font("display", 13))
        self.volume_label.setFont(skin().font("bold", 15))

    def _on_volume(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")
        self._prefs.set("sound_volume", value)

    def _sync(self) -> None:
        for w in (self.mute_checkbox, self.volume_slider, self.precount_checkbox):
            w.blockSignals(True)
        self.mute_checkbox.setChecked(bool(self._prefs.get("sound_muted")))
        self.volume_slider.setValue(int(self._prefs.get("sound_volume")))
        self.volume_label.setText(f"{self.volume_slider.value()}%")
        self.precount_checkbox.setChecked(bool(self._prefs.get("precount_enabled")))
        for w in (self.mute_checkbox, self.volume_slider, self.precount_checkbox):
            w.blockSignals(False)
            w.update()

    def showEvent(self, event) -> None:
        self._sync()
        super().showEvent(event)
