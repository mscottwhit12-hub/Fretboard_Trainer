"""
ui/settings_panel.py

Settings page shell: a segmented switcher over General, Game Rules and
Theme. New sections slot in here without touching the sidebar.
"""

from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from ui.game_rules_panel import GameRulesPanel
from ui.general_settings_panel import GeneralSettingsPanel
from ui.kit import Segmented
from ui.theme_panel import ThemePanel


class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        names = ["General", "Game Rules", "Theme"]
        self.switcher = Segmented(names)
        self.stack = QStackedWidget()
        for page in (GeneralSettingsPanel(), GameRulesPanel(), ThemePanel()):
            self.stack.addWidget(page)
        self.switcher.currentTextChanged.connect(
            lambda _t: self.stack.setCurrentIndex(self.switcher.currentIndex()))
        root.addWidget(self.switcher)
        root.addWidget(self.stack)
        root.addStretch()
