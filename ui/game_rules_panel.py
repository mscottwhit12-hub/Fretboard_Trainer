"""
ui/game_rules_panel.py

Game Rules page. First rule: how notes with two valid spellings
(e.g. C#/Db) are shown in quiz questions.
"""

from PyQt6.QtWidgets import QButtonGroup, QLabel, QVBoxLayout, QWidget

from core.settings import ACCIDENTAL_MODE_LABELS, AccidentalMode, GameRules
from ui.kit import Card, SkinRadio
from ui.theme import SkinManager, skin


class GameRulesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = GameRules.instance()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = Card("Sharps & flats", "pink")
        self._desc = QLabel(
            "Controls how notes with two valid spellings (e.g. C# / Db) are shown in both quiz modes."
        )
        self._desc.setWordWrap(True)
        card.body.addWidget(self._desc)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        for mode in AccidentalMode:
            radio = SkinRadio(ACCIDENTAL_MODE_LABELS[mode])
            radio.setChecked(mode is self._rules.accidental_mode)
            radio.toggled.connect(lambda checked, m=mode: self._on_mode_toggled(m, checked))
            self._button_group.addButton(radio)
            card.body.addWidget(radio)
        root.addWidget(card)
        root.addStretch()
        self._apply_fonts()
        SkinManager.instance().skin_changed.connect(lambda _s: self._apply_fonts())

    def _apply_fonts(self) -> None:
        self._desc.setFont(skin().font("body", 14))

    def _on_mode_toggled(self, mode: AccidentalMode, checked: bool) -> None:
        if checked:
            self._rules.accidental_mode = mode
