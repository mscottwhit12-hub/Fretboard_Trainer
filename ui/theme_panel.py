"""
ui/theme_panel.py

Theme picker. Each entry is a complete skin (colors, shapes, shadows,
fonts, painting) -- not a color scheme.
"""

from PyQt6.QtWidgets import QButtonGroup, QLabel, QVBoxLayout, QWidget

from ui.kit import Card, SkinRadio
from ui.theme import SkinManager, skin


class ThemePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = SkinManager.instance()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = Card("Theme", "green")
        self._labels: list[QLabel] = []
        self._group = QButtonGroup(self)
        for name in self._manager.names():
            radio = SkinRadio(name)
            radio.setChecked(name == self._manager.skin.name)
            radio.toggled.connect(lambda checked, n=name: checked and self._manager.set_skin(n))
            self._group.addButton(radio)
            card.body.addWidget(radio)
        self._note = QLabel("More full themes are on the way.")
        card.body.addWidget(self._note)
        root.addWidget(card)
        root.addStretch()
        self._apply_fonts()
        self._manager.skin_changed.connect(lambda _s: self._apply_fonts())

    def _apply_fonts(self) -> None:
        self._note.setFont(skin().font("body", 14))
