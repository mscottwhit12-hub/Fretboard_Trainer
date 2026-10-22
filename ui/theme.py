"""
ui/theme.py

The skin system. A *skin* is a complete visual theme: it supplies the
colors, fonts, shapes, shadows AND the painting routines for every
component. The shared *format* (layout, which components exist, how they
behave) lives in ui/kit.py and the panels, and never changes between
skins -- a new skin only has to implement the paint_* methods below
(see ui/skins/pop.py for the reference implementation).
"""

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

from core.prefs import Prefs

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
DEFAULT_SKIN = "Schoolhouse Pop"


def mix(a: str, b: str, t: float) -> str:
    """Linear RGB blend of two #RRGGBB colors, t=0 -> a, t=1 -> b."""
    ca, cb = QColor(a), QColor(b)
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
    ).name()


class Skin:
    """Interface every skin implements. Tokens first, then painters."""

    name = "base"
    description = ""

    # --- tokens -------------------------------------------------------
    ink = "#000000"
    bg = "#FFFFFF"
    tones: dict[str, str] = {}
    accent = "#FF0000"       # primary highlight (question dot, primary button)
    good = "#00FF00"         # "correct" color
    bad = "#FF0000"          # "incorrect" color
    display_family = "Arial Black"
    body_family = "Segoe UI"
    heatmap_stops = ("#FF0000", "#FFFF00", "#00FF00")
    # board colors used by FretboardWidget
    board_bg = "#FFFFFF"
    board_wire = "#000000"
    board_string = "#000000"
    board_string_off = "#999999"
    board_label = "#000000"
    board_marker = "#DDDDDD"
    board_highlight = "#FF0000"
    board_wrong = "#E5242B"
    board_nodata = "#00000040"

    # --- helpers --------------------------------------------------------

    def tone_color(self, tone: str) -> str:
        return self.tones.get(tone, tone)

    def font(self, role: str, px: int) -> QFont:
        """role: 'display' (headings) | 'body' | 'bold' (body, bold)."""
        f = QFont(self.display_family if role == "display" else self.body_family)
        f.setPixelSize(px)
        if role == "bold":
            f.setWeight(QFont.Weight.Bold)
        elif role == "body":
            f.setWeight(QFont.Weight.Medium)
        return f

    def heatmap_color(self, t: float) -> str:
        """t in 0..1: 0 = struggling stop, 1 = mastered stop."""
        t = max(0.0, min(1.0, t))
        lo, mid, hi = self.heatmap_stops
        return mix(lo, mid, t * 2) if t < 0.5 else mix(mid, hi, (t - 0.5) * 2)

    def card_margins(self, pad: int = 16) -> tuple[int, int, int, int]:
        """Contents margins that keep child widgets inside a card's border/shadow."""
        return (pad, pad, pad, pad)

    def stylesheet(self) -> str:
        return ""

    # --- painters (QRectF is the widget's full rect) ----------------------
    def paint_background(self, p, rect): raise NotImplementedError
    def paint_sidebar(self, p, rect): raise NotImplementedError
    def paint_logo(self, p, rect): raise NotImplementedError
    def paint_card(self, p, rect, tone): raise NotImplementedError
    def paint_badge(self, p, rect, text, tone, font): raise NotImplementedError
    def paint_button(self, p, rect, text, kind, hover, pressed, enabled, tone, font): raise NotImplementedError
    def paint_chip(self, p, rect, text, checked, hover, enabled, font): raise NotImplementedError
    def paint_nav_item(self, p, rect, text, selected, hover, font): raise NotImplementedError
    def paint_segment(self, p, rect, text, selected, hover, enabled, font): raise NotImplementedError
    def paint_field(self, p, rect, text, enabled, font): raise NotImplementedError
    def paint_check(self, p, rect, checked, enabled, hover): raise NotImplementedError
    def paint_radio(self, p, rect, checked, enabled, hover): raise NotImplementedError
    def paint_tag(self, p, rect, text, kind, font): raise NotImplementedError


def _load_fonts() -> None:
    if not FONT_DIR.is_dir():
        return
    for path in FONT_DIR.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(path))


class SkinManager(QObject):
    skin_changed = pyqtSignal(object)
    _instance: "SkinManager | None" = None

    def __init__(self):
        super().__init__()
        from ui.skins import SKINS
        _load_fonts()
        self._skins = SKINS
        name = Prefs.instance().get("skin")
        self._skin: Skin = SKINS.get(name) or SKINS[DEFAULT_SKIN]
        self._apply()

    @classmethod
    def instance(cls) -> "SkinManager":
        if cls._instance is None:
            cls._instance = SkinManager()
        return cls._instance

    @property
    def skin(self) -> Skin:
        return self._skin

    def names(self) -> list[str]:
        return list(self._skins)

    def set_skin(self, name: str) -> None:
        if name not in self._skins or self._skins[name] is self._skin:
            return
        self._skin = self._skins[name]
        Prefs.instance().set("skin", name)
        self._apply()
        self.skin_changed.emit(self._skin)

    def _apply(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
            app.setFont(self._skin.font("body", 14))
            app.setStyleSheet(self._skin.stylesheet())


def skin() -> Skin:
    return SkinManager.instance().skin

ThemeManager = SkinManager  # backward-compat alias for older entry points
