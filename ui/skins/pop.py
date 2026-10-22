"""
ui/skins/pop.py

"Schoolhouse Pop": cream dotted paper, flat contrast-color cards, thick
black outlines, hard offset black drop shadows, heavy display type.
Reference implementation of the Skin interface.
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QBrush, QPainterPath, QPen

from ui.theme import Skin

INK = "#0B0B0B"


class PopSkin(Skin):
    name = "Schoolhouse Pop"
    description = "Cream paper, bold contrast colors, black outlines and hard drop shadows."

    ink = INK
    bg = "#FFF0D1"
    dot = "#EBD7AE"
    sidebar = "#FF6B3D"
    tones = {
        "white": "#FFFFFF", "pink": "#FFB8F2", "blue": "#8CD8FF",
        "green": "#C6F26B", "yellow": "#FFDB4D", "cream": "#FFF0D1",
        "orange": "#FF6B3D", "hot": "#FF4F8B",
    }
    accent = "#FF4F8B"
    good = "#C6F26B"
    bad = "#FF4F8B"
    display_family = "Archivo Black"
    body_family = "Space Grotesk"
    heatmap_stops = ("#FF4F8B", "#FFDB4D", "#9BE23B")

    border = 3
    shadow = 5
    radius = 14

    board_bg = "#FFFFFF"
    board_wire = INK
    board_string = INK
    board_string_off = "#C9BFA8"
    board_label = INK
    board_marker = "#FFB8F2"
    board_highlight = "#FF4F8B"
    board_wrong = "#E5242B"
    board_nodata = "#0B0B0B55"

    DISABLED_FILL = "#EDE3CC"
    DISABLED_INK = "#9A8F76"

    # --- helpers --------------------------------------------------------

    def card_margins(self, pad: int = 16):
        # 2px lift allowance + border on the left/top; shadow + border right/bottom.
        return (2 + self.border + pad, 2 + self.border + pad,
                self.shadow + self.border + pad, self.shadow + self.border + pad)

    def _box(self, p, rect, fill, radius, *, bw=None, sh=None, lift=False, pressed=False,
             ink=INK, shadow_color=INK):
        """Outlined rounded box with a hard offset shadow. Returns the body rect."""
        bw = self.border if bw is None else bw
        sh = self.shadow if sh is None else sh
        base = QRectF(rect).adjusted(2 + bw / 2, 2 + bw / 2, -(sh + bw / 2), -(sh + bw / 2))
        body = QRectF(base)
        if pressed:
            body.translate(sh, sh)
        elif lift:
            body.translate(-2, -2)
        radius = min(radius, body.height() / 2, body.width() / 2)
        if sh > 0 and not pressed:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(shadow_color))
            s = base.translated(sh, sh).adjusted(-bw / 2, -bw / 2, bw / 2, bw / 2)
            p.drawRoundedRect(s, radius + bw / 2, radius + bw / 2)
        pen = QPen(QColor(ink), bw)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(QColor(fill))
        p.drawRoundedRect(body, radius, radius)
        return body

    def _text(self, p, rect, text, font, color=INK, align=Qt.AlignmentFlag.AlignCenter):
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(rect, int(align), text)

    # --- painters ---------------------------------------------------------

    def paint_background(self, p, rect):
        p.fillRect(rect, QColor(self.bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.dot))
        step = 18
        y = 9
        while y < rect.height():
            x = 9
            while x < rect.width():
                p.drawEllipse(QPointF(x, y), 1.3, 1.3)
                x += step
            y += step

    def paint_sidebar(self, p, rect):
        p.fillRect(rect, QColor(self.sidebar))
        p.fillRect(QRectF(rect.right() - self.border, rect.top(), self.border, rect.height()), QColor(INK))

    def paint_logo(self, p, rect):
        body = self._box(p, rect, self.tones["yellow"], 12, sh=4)
        c = body.center()
        w, h = body.width() * 0.42, body.height() * 0.5
        path = QPainterPath()
        path.moveTo(c.x(), c.y() + h * 0.6)
        path.cubicTo(c.x() - w * 1.1, c.y() - h * 0.1, c.x() - w * 0.8, c.y() - h * 0.75, c.x(), c.y() - h * 0.6)
        path.cubicTo(c.x() + w * 0.8, c.y() - h * 0.75, c.x() + w * 1.1, c.y() - h * 0.1, c.x(), c.y() + h * 0.6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawPath(path)

    def paint_card(self, p, rect, tone):
        self._box(p, rect, self.tone_color(tone), self.radius)

    def paint_badge(self, p, rect, text, tone, font):
        dark = tone == "ink"
        body = self._box(p, rect, INK if dark else self.tone_color(tone), 99, bw=2.5, sh=0)
        self._text(p, body, text, font, "#FFF0D1" if dark else INK)

    def paint_button(self, p, rect, text, kind, hover, pressed, enabled, tone, font):
        fills = {"primary": self.accent, "danger": self.tones["orange"]}
        fill = fills.get(kind, "#FFFFFF")
        if tone == "good":
            fill = self.good
        elif tone == "bad":
            fill = self.bad
        elif hover and enabled and kind in ("secondary", "answer", "small"):
            fill = self.tones["yellow"]
        sh = 3 if kind == "small" else self.shadow
        if not enabled and tone is None:
            body = self._box(p, rect, self.DISABLED_FILL, 12, bw=2.5, sh=sh,
                             ink=self.DISABLED_INK, shadow_color="#CDBF9E")
            self._text(p, body, text, font, self.DISABLED_INK)
            return
        body = self._box(p, rect, fill, 12, sh=sh, lift=hover and enabled and not pressed, pressed=pressed)
        self._text(p, body, text, font)

    def paint_chip(self, p, rect, text, checked, hover, enabled, font):
        if not enabled:
            body = self._box(p, rect, self.good if checked else self.DISABLED_FILL, 10, bw=2.5, sh=3,
                             ink=self.DISABLED_INK, shadow_color="#CDBF9E")
            self._text(p, body, text, font, self.DISABLED_INK)
            return
        fill = self.good if checked else ("#FFFFFF" if not hover else self.tones["yellow"])
        body = self._box(p, rect, fill, 10, bw=2.5, sh=3, lift=hover)
        self._text(p, body, text, font)

    def paint_nav_item(self, p, rect, text, selected, hover, font):
        if selected:
            body = self._box(p, rect, "#FFFFFF", 12, sh=4)
        else:
            body = QRectF(rect).adjusted(2, 2, -6, -6)
            if hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#FF8A63"))
                p.drawRoundedRect(body, 12, 12)
        self._text(p, body.adjusted(16, 0, 0, 0), text, font, INK,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

    def paint_segment(self, p, rect, text, selected, hover, enabled, font):
        fill = INK if selected else ("#FFFFFF" if not hover else self.tones["yellow"])
        body = self._box(p, rect, fill, 99, bw=2.5, sh=0,
                         ink=INK if enabled else self.DISABLED_INK)
        color = "#FFF0D1" if selected else (INK if enabled else self.DISABLED_INK)
        self._text(p, body, text, font, color)

    def paint_field(self, p, rect, text, enabled, font):
        body = self._box(p, rect, "#FFFFFF" if enabled else self.DISABLED_FILL, 10, bw=2.5, sh=0,
                         ink=INK if enabled else self.DISABLED_INK)
        self._text(p, body, text, font, INK if enabled else self.DISABLED_INK)

    def paint_check(self, p, rect, checked, enabled, hover):
        ink = INK if enabled else self.DISABLED_INK
        fill = (self.good if checked else "#FFFFFF") if enabled else self.DISABLED_FILL
        body = self._box(p, rect, fill, 6, bw=2.5, sh=0, ink=ink)
        if checked:
            pen = QPen(QColor(ink), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            c, w = body.center(), body.width()
            p.drawPolyline([QPointF(c.x() - w * 0.24, c.y()), QPointF(c.x() - w * 0.05, c.y() + w * 0.2),
                            QPointF(c.x() + w * 0.27, c.y() - w * 0.2)])

    def paint_radio(self, p, rect, checked, enabled, hover):
        ink = INK if enabled else self.DISABLED_INK
        body = self._box(p, rect, "#FFFFFF" if enabled else self.DISABLED_FILL, 99, bw=2.5, sh=0, ink=ink)
        if checked:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self.accent))
            r = body.width() * 0.28
            p.drawEllipse(body.center(), r, r)

    def paint_tag(self, p, rect, text, kind, font):
        color = {"good": self.good, "bad": "#FF8FB5"}.get(kind, "#FFF0D1")
        body = self._box(p, rect, INK, 10, bw=2, sh=0)
        self._text(p, body, text, font, color)

    # --- app-wide stylesheet for stock widgets (dialogs, lists, sliders...) ----

    def stylesheet(self) -> str:
        ink, bg = INK, self.bg
        return f"""
        QWidget {{ color: {ink}; }}
        QLabel {{ background: transparent; }}
        QDialog, QMessageBox {{ background: {bg}; }}
        QStatusBar {{ background: {bg}; color: {ink}; font-weight: 700; }}
        QToolTip {{
            background: {ink}; color: #FFF0D1; border: 2px solid {ink};
            padding: 6px 8px; font-size: 13px;
        }}
        QMessageBox QPushButton, QFileDialog QPushButton {{
            background: #FFFFFF; border: 3px solid {ink}; border-radius: 10px;
            padding: 6px 18px; font-weight: 700; min-width: 64px;
        }}
        QMessageBox QPushButton:hover, QFileDialog QPushButton:hover {{ background: {self.tones['yellow']}; }}
        QMessageBox QPushButton:pressed, QFileDialog QPushButton:pressed {{ background: {self.accent}; }}
        QListWidget {{
            background: #FFFFFF; border: 3px solid {ink}; border-radius: 10px; padding: 4px;
        }}
        QListWidget::item {{ padding: 4px; }}
        QListWidget::item:selected, QListWidget::item:selected:!active {{ background: {self.tones['yellow']}; color: {ink}; }}
        QScrollArea {{ background: transparent; border: none; }}
        QScrollBar:vertical {{ background: transparent; width: 16px; margin: 2px; }}
        QScrollBar::handle:vertical {{
            background: #FFFFFF; border: 3px solid {ink}; border-radius: 6px; min-height: 40px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QSlider::groove:horizontal {{
            height: 10px; background: #FFFFFF; border: 3px solid {ink}; border-radius: 8px; margin: 0 4px;
        }}
        QSlider::sub-page:horizontal {{ background: {self.accent}; border-radius: 5px; }}
        QSlider::handle:horizontal {{
            width: 20px; height: 20px; margin: -9px -4px; border-radius: 13px;
            background: {self.tones['yellow']}; border: 3px solid {ink};
        }}
        """
