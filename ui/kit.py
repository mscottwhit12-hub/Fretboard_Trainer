"""
ui/kit.py

The shared component kit -- the *format* of the app. Every widget here
lays itself out the same way regardless of skin and delegates all
painting to the active skin (ui/theme.py -> Skin.paint_*). Panels are
built only from these components, so a new skin restyles the whole app
without touching any panel code.
"""

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPushButton, QRadioButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ui.theme import SkinManager, skin


def _painter(widget) -> QPainter:
    p = QPainter(widget)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return p


def _on_skin_change(widget, slot) -> None:
    SkinManager.instance().skin_changed.connect(lambda _s: slot())


class Backdrop(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _on_skin_change(self, self.update)

    def paintEvent(self, event) -> None:
        p = _painter(self)
        skin().paint_background(p, QRectF(self.rect()))


class Card(QWidget):
    """Titled, toned, shadowed container. Put content into `.body`."""

    def __init__(self, title: str = "", tone: str = "white", badge: str = "", pad: int = 16, parent=None):
        super().__init__(parent)
        self.tone, self.pad = tone, pad
        self.outer = QVBoxLayout(self)
        self.outer.setSpacing(10)
        self.title_label = QLabel(title.upper())
        self.badge = Badge(badge) if badge else None
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        if title or badge:
            header = QHBoxLayout()
            header.addWidget(self.title_label)
            header.addStretch()
            if self.badge:
                header.addWidget(self.badge)
            self.outer.addLayout(header)
        else:
            self.title_label.hide()
        self.outer.addLayout(self.body)
        self._restyle()
        _on_skin_change(self, self._restyle)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text.upper())

    def _restyle(self) -> None:
        sk = skin()
        self.outer.setContentsMargins(*sk.card_margins(self.pad))
        self.title_label.setFont(sk.font("display", 14))
        self.update()

    def paintEvent(self, event) -> None:
        p = _painter(self)
        skin().paint_card(p, QRectF(self.rect()), self.tone)


class Badge(QWidget):
    def __init__(self, text: str = "", tone: str = "white", parent=None):
        super().__init__(parent)
        self._text, self.tone = text, tone
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        _on_skin_change(self, lambda: (self.updateGeometry(), self.update()))

    def setText(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def _font(self):
        return skin().font("bold", 12)

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(self._font()).horizontalAdvance(self._text) + 28, 28)

    def paintEvent(self, event) -> None:
        skin().paint_badge(_painter(self), QRectF(self.rect()), self._text, self.tone, self._font())


class SkinButton(QPushButton):
    """kind: primary | secondary | danger | answer | small"""

    def __init__(self, text: str = "", kind: str = "secondary", parent=None):
        super().__init__(text, parent)
        self.kind = kind
        self._tone: str | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _on_skin_change(self, lambda: (self.updateGeometry(), self.update()))

    def set_tone(self, tone: str | None) -> None:
        self._tone = tone
        self.update()

    def _shown_text(self) -> str:
        return self.text().upper() if self.kind != "answer" else self.text()

    def _font(self):
        s = skin()
        return s.font("display", 20) if self.kind == "answer" else s.font("bold", 15 if self.kind != "small" else 18)

    def sizeHint(self) -> QSize:
        w = QFontMetrics(self._font()).horizontalAdvance(self._shown_text())
        return QSize(max(w + 44, 56 if self.kind == "small" else 120), 44 if self.kind == "small" else 58)

    def paintEvent(self, event) -> None:
        skin().paint_button(
            _painter(self), QRectF(self.rect()), self._shown_text(), self.kind,
            self.underMouse(), self.isDown(), self.isEnabled(), self._tone, self._font(),
        )


class ToggleChip(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _on_skin_change(self, lambda: (self.updateGeometry(), self.update()))

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(skin().font("bold", 14)).horizontalAdvance(self.text()) + 34, 40)

    def paintEvent(self, event) -> None:
        skin().paint_chip(_painter(self), QRectF(self.rect()), self.text(), self.isChecked(),
                          self.underMouse(), self.isEnabled(), skin().font("bold", 14))


class NavButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(54)
        _on_skin_change(self, self.update)

    def paintEvent(self, event) -> None:
        skin().paint_nav_item(_painter(self), QRectF(self.rect()), self.text(), self.isChecked(),
                              self.underMouse(), skin().font("bold", 16))


class _Seg(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _on_skin_change(self, lambda: (self.updateGeometry(), self.update()))

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(skin().font("bold", 13)).horizontalAdvance(self.text()) + 30, 34)

    def paintEvent(self, event) -> None:
        skin().paint_segment(_painter(self), QRectF(self.rect()), self.text(), self.isChecked(),
                             self.underMouse(), self.isEnabled(), skin().font("bold", 13))


class Segmented(QWidget):
    """A row of mutually exclusive options (replaces combo boxes / tabs)."""

    currentTextChanged = pyqtSignal(str)

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._buttons: list[_Seg] = []
        for i, text in enumerate(items):
            b = _Seg(text)
            b.clicked.connect(lambda _c=False, idx=i: self._select(idx, True))
            lay.addWidget(b)
            self._buttons.append(b)
        lay.addStretch()
        self._select(0, False)

    def _select(self, index: int, emit: bool) -> None:
        for i, b in enumerate(self._buttons):
            b.setChecked(i == index)
        if emit:
            self.currentTextChanged.emit(self.currentText())

    def currentText(self) -> str:
        return next((b.text() for b in self._buttons if b.isChecked()), "")

    def currentIndex(self) -> int:
        return next((i for i, b in enumerate(self._buttons) if b.isChecked()), 0)

    def setCurrentText(self, text: str) -> None:
        for i, b in enumerate(self._buttons):
            if b.text() == text:
                self._select(i, True)
                return


class _Field(QWidget):
    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self._owner = owner
        self.setMinimumWidth(60)
        self.setFixedHeight(44)

    def paintEvent(self, event) -> None:
        o = self._owner
        skin().paint_field(_painter(self), QRectF(self.rect()), f"{o.value()}{o._suffix}",
                           o.isEnabled(), skin().font("bold", 16))


class Stepper(QWidget):
    """[-] value [+]  (replaces QSpinBox)."""

    valueChanged = pyqtSignal(int)

    def __init__(self, minimum: int = 0, maximum: int = 100, value: int = 0, parent=None):
        super().__init__(parent)
        self._min, self._max, self._value, self._step, self._suffix = minimum, maximum, value, 1, ""
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.minus = SkinButton("−", "small")
        self.plus = SkinButton("+", "small")
        for b in (self.minus, self.plus):
            b.setFixedWidth(44)
            b.setAutoRepeat(True)
            b.setAutoRepeatDelay(350)
            b.setAutoRepeatInterval(80)
        self.minus.clicked.connect(lambda: self.setValue(self._value - self._step))
        self.plus.clicked.connect(lambda: self.setValue(self._value + self._step))
        self.field = _Field(self)
        lay.addWidget(self.minus)
        lay.addWidget(self.field)
        lay.addWidget(self.plus)

    def value(self) -> int:
        return self._value

    def setValue(self, v: int) -> None:
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self.field.update()
            self.valueChanged.emit(v)

    def setRange(self, lo: int, hi: int) -> None:
        self._min, self._max = lo, hi
        self._value = max(lo, min(hi, self._value))
        self.field.update()

    def setSingleStep(self, step: int) -> None:
        self._step = step

    def setSuffix(self, text: str) -> None:
        self._suffix = text
        self.field.update()

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self.field.update()


class SkinCheck(QCheckBox):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(skin().font("bold", 15)).horizontalAdvance(self.text()) + 44, 34)

    def paintEvent(self, event) -> None:
        p = _painter(self)
        box = QRectF(2, (self.height() - 26) / 2, 26, 26)
        skin().paint_check(p, box, self.isChecked(), self.isEnabled(), self.underMouse())
        p.setFont(skin().font("bold", 15))
        p.setPen(QColor(skin().ink))
        p.drawText(QRectF(40, 0, self.width() - 40, self.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())


class SkinRadio(QRadioButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(skin().font("bold", 15)).horizontalAdvance(self.text()) + 44, 34)

    def paintEvent(self, event) -> None:
        p = _painter(self)
        box = QRectF(2, (self.height() - 26) / 2, 26, 26)
        skin().paint_radio(p, box, self.isChecked(), self.isEnabled(), self.underMouse())
        p.setFont(skin().font("bold", 15))
        p.setPen(QColor(skin().ink))
        p.drawText(QRectF(40, 0, self.width() - 40, self.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())


class FeedbackTag(QLabel):
    """Right/wrong message shown as a dark tag. Reserves its height when empty."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.kind = ""
        self.setFixedHeight(44)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_feedback(self, text: str, kind: str = "") -> None:
        self.kind = kind
        self.setText(text)
        self.update()

    def paintEvent(self, event) -> None:
        if not self.text():
            return
        p = _painter(self)
        font = skin().font("bold", 15)
        w = QFontMetrics(font).horizontalAdvance(self.text()) + 40
        r = QRectF((self.width() - w) / 2, 4, w, self.height() - 8)
        skin().paint_tag(p, r, self.text(), self.kind, font)


class LogoMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 52)

    def paintEvent(self, event) -> None:
        skin().paint_logo(_painter(self), QRectF(self.rect()))


class Sidebar(QWidget):
    """Left navigation. Emits page_selected(index)."""

    page_selected = pyqtSignal(int)

    def __init__(self, title: str, items: list[str], footer: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.setFixedWidth(232)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 22, 18, 18)
        lay.setSpacing(8)

        brand = QHBoxLayout()
        brand.addWidget(LogoMark())
        self.brand_label = QLabel(title.upper())
        self.brand_label.setWordWrap(True)
        brand.addWidget(self.brand_label, stretch=1)
        lay.addLayout(brand)
        lay.addSpacing(18)

        self.buttons: list[NavButton] = []
        for i, text in enumerate(items):
            b = NavButton(text)
            b.clicked.connect(lambda _c=False, idx=i: self.page_selected.emit(idx))
            lay.addWidget(b)
            self.buttons.append(b)
        self.buttons[0].setChecked(True)
        lay.addStretch()
        if footer is not None:
            lay.addWidget(footer, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._restyle()
        _on_skin_change(self, self._restyle)

    def select(self, index: int) -> None:
        self.buttons[index].setChecked(True)

    def _restyle(self) -> None:
        self.brand_label.setFont(skin().font("display", 17))
        self.update()

    def paintEvent(self, event) -> None:
        skin().paint_sidebar(_painter(self), QRectF(self.rect()))


class PageHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 0, 0)
        lay.setSpacing(6)
        self.kicker = Badge("", "ink")
        lay.addWidget(self.kicker, alignment=Qt.AlignmentFlag.AlignLeft)
        self.title = QLabel("")
        lay.addWidget(self.title)
        self._restyle()
        _on_skin_change(self, self._restyle)

    def set_page(self, kicker: str, title: str) -> None:
        self.kicker.setText(kicker.upper())
        self.title.setText(title.upper())

    def _restyle(self) -> None:
        self.title.setFont(skin().font("display", 30))
