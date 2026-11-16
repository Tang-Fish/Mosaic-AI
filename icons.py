import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton


def _paint_vector(painter, name, color):
    pen = QPen(QColor(color), 3.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if name == "sidebar":
        painter.drawRoundedRect(QRectF(8, 10, 32, 28), 5.0, 5.0)
        painter.drawLine(QPointF(18, 10), QPointF(18, 38))

    elif name == "bot_mascot":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRectF(15, 9, 4, 5))
        painter.drawRect(QRectF(29, 9, 4, 5))
        painter.drawRoundedRect(QRectF(11, 14, 26, 17), 3.0, 3.0)
        painter.drawRect(QRectF(7, 19, 4, 8))
        painter.drawRect(QRectF(37, 19, 4, 8))
        painter.drawRect(QRectF(14, 31, 5, 7))
        painter.drawRect(QRectF(29, 31, 5, 7))
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.drawRect(QRectF(16, 20, 4, 4))
        painter.drawRect(QRectF(28, 20, 4, 4))
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    elif name == "terminal":
        painter.drawRoundedRect(QRectF(9, 10, 30, 28), 4.5, 4.5)
        arrow = QPainterPath()
        arrow.moveTo(15, 19)
        arrow.lineTo(20, 24)
        arrow.lineTo(15, 29)
        painter.drawPath(arrow)
        painter.drawLine(QPointF(23, 29), QPointF(31, 29))

    elif name == "models":
        painter.drawLine(QPointF(11, 13), QPointF(11, 35))
        painter.drawLine(QPointF(17, 13), QPointF(17, 35))
        poly = QPainterPath()
        poly.moveTo(23, 13)
        poly.lineTo(35, 17)
        poly.lineTo(35, 31)
        poly.lineTo(23, 35)
        poly.closeSubpath()
        painter.drawPath(poly)

    elif name == "compose":
        box = QPainterPath()
        box.moveTo(26, 10)
        box.lineTo(13, 10)
        box.quadTo(9, 10, 9, 14)
        box.lineTo(9, 35)
        box.quadTo(9, 39, 13, 39)
        box.lineTo(34, 39)
        box.quadTo(38, 39, 38, 35)
        box.lineTo(38, 22)
        painter.drawPath(box)

        pencil = QPainterPath()
        pencil.moveTo(22, 26)
        pencil.lineTo(36, 12)
        pencil.lineTo(40, 16)
        pencil.lineTo(26, 30)
        pencil.lineTo(20, 31)
        pencil.closeSubpath()
        painter.drawPath(pencil)

    elif name == "edit":
        pencil = QPainterPath()
        pencil.moveTo(12, 36)
        pencil.lineTo(14, 28)
        pencil.lineTo(31, 11)
        pencil.lineTo(37, 17)
        pencil.lineTo(20, 34)
        pencil.closeSubpath()
        painter.drawPath(pencil)
        painter.drawLine(QPointF(27, 15), QPointF(33, 21))

    elif name == "trash":
        painter.drawLine(QPointF(11, 14), QPointF(37, 14))
        painter.drawLine(QPointF(19, 10), QPointF(29, 10))
        bin_path = QPainterPath()
        bin_path.moveTo(14, 14)
        bin_path.lineTo(16, 37)
        bin_path.quadTo(16, 39, 18, 39)
        bin_path.lineTo(30, 39)
        bin_path.quadTo(32, 39, 32, 37)
        bin_path.lineTo(34, 14)
        painter.drawPath(bin_path)
        painter.drawLine(QPointF(21, 20), QPointF(21, 33))
        painter.drawLine(QPointF(27, 20), QPointF(27, 33))

    elif name == "sun":
        cx, cy = 24.0, 24.0
        painter.drawEllipse(QRectF(cx - 6.5, cy - 6.5, 13.0, 13.0))
        for i in range(8):
            angle = i * (math.pi / 4.0)
            x1 = cx + 11.0 * math.cos(angle)
            y1 = cy + 11.0 * math.sin(angle)
            x2 = cx + 15.5 * math.cos(angle)
            y2 = cy + 15.5 * math.sin(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    elif name == "moon":
        moon = QPainterPath()
        moon.moveTo(28, 10)
        moon.cubicTo(17, 11, 11, 20, 13, 30)
        moon.cubicTo(15, 38, 25, 41, 34, 36)
        moon.cubicTo(25, 36, 20, 29, 21, 20)
        moon.cubicTo(22, 15, 25, 12, 28, 10)
        moon.closeSubpath()
        painter.drawPath(moon)

    elif name == "dots":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        for x in (13, 24, 35):
            painter.drawEllipse(QPointF(x, 24), 2.5, 2.5)

    elif name == "folder_plus":
        folder = QPainterPath()
        folder.moveTo(8, 15)
        folder.lineTo(8, 34)
        folder.quadTo(8, 37, 11, 37)
        folder.lineTo(25, 37)
        painter.drawPath(folder)

        top = QPainterPath()
        top.moveTo(8, 15)
        top.quadTo(8, 12, 11, 12)
        top.lineTo(19, 12)
        top.lineTo(23, 16)
        top.lineTo(37, 16)
        top.quadTo(40, 16, 40, 19)
        top.lineTo(40, 24)
        painter.drawPath(top)

        painter.drawEllipse(QRectF(27, 26, 13, 13))
        painter.drawLine(QPointF(33.5, 29.5), QPointF(33.5, 35.5))
        painter.drawLine(QPointF(30.5, 32.5), QPointF(36.5, 32.5))

    elif name == "folder":
        folder = QPainterPath()
        folder.moveTo(8, 15)
        folder.quadTo(8, 12, 11, 12)
        folder.lineTo(19, 12)
        folder.lineTo(23, 16)
        folder.lineTo(37, 16)
        folder.quadTo(40, 16, 40, 19)
        folder.lineTo(40, 34)
        folder.quadTo(40, 37, 37, 37)
        folder.lineTo(11, 37)
        folder.quadTo(8, 37, 8, 34)
        folder.closeSubpath()
        painter.drawPath(folder)

    elif name == "search":
        painter.drawEllipse(QRectF(10, 10, 21, 21))
        painter.drawLine(QPointF(28.5, 28.5), QPointF(38, 38))

    elif name == "pin":
        painter.drawLine(QPointF(27, 9), QPointF(39, 21))
        painter.drawLine(QPointF(29, 11), QPointF(21, 20))
        painter.drawLine(QPointF(37, 19), QPointF(28, 27))
        painter.drawLine(QPointF(17, 19), QPointF(29, 31))
        painter.drawLine(QPointF(23, 25), QPointF(11, 37))

    elif name == "memory":
        left = QPainterPath()
        left.moveTo(24, 10)
        left.cubicTo(13, 10, 10, 17, 11, 23)
        left.cubicTo(9, 29, 13, 38, 24, 38)
        painter.drawPath(left)

        right = QPainterPath()
        right.moveTo(24, 10)
        right.cubicTo(35, 10, 38, 17, 37, 23)
        right.cubicTo(39, 29, 35, 38, 24, 38)
        painter.drawPath(right)

        painter.drawLine(QPointF(24, 11), QPointF(24, 37))
        painter.drawArc(QRectF(15, 16, 7, 7), 40 * 16, 170 * 16)
        painter.drawArc(QRectF(26, 16, 7, 7), -30 * 16, 170 * 16)
        painter.drawArc(QRectF(15, 26, 7, 7), 150 * 16, 170 * 16)
        painter.drawArc(QRectF(26, 26, 7, 7), 220 * 16, 170 * 16)

    elif name == "link":
        painter.drawRoundedRect(QRectF(9, 11, 20, 15), 3.0, 3.0)
        painter.drawLine(QPointF(15, 30), QPointF(22, 30))
        painter.drawRoundedRect(QRectF(23, 27, 16, 9), 4.5, 4.5)

    elif name == "settings":
        cx, cy = 24.0, 24.0
        painter.drawEllipse(QRectF(cx - 5.5, cy - 5.5, 11.0, 11.0))
        painter.drawEllipse(QRectF(cx - 12.5, cy - 12.5, 25.0, 25.0))
        for i in range(8):
            angle = i * (math.pi / 4.0)
            x1 = cx + 13.0 * math.cos(angle)
            y1 = cy + 13.0 * math.sin(angle)
            x2 = cx + 17.5 * math.cos(angle)
            y2 = cy + 17.5 * math.sin(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    elif name == "appearance":
        painter.drawArc(QRectF(10, 10, 28, 28), -30 * 16, 290 * 16)
        painter.drawEllipse(QRectF(17, 16, 3.5, 3.5))
        painter.drawEllipse(QRectF(26, 15, 3.5, 3.5))
        painter.drawEllipse(QRectF(15, 25, 3.5, 3.5))
        painter.drawEllipse(QRectF(25, 27, 5.0, 5.0))

    elif name == "chat_bubble":
        bubble = QPainterPath()
        bubble.moveTo(12, 11)
        bubble.lineTo(36, 11)
        bubble.quadTo(39, 11, 39, 14)
        bubble.lineTo(39, 30)
        bubble.quadTo(39, 33, 36, 33)
        bubble.lineTo(20, 33)
        bubble.lineTo(12, 39)
        bubble.lineTo(12, 33)
        bubble.quadTo(9, 33, 9, 30)
        bubble.lineTo(9, 14)
        bubble.quadTo(9, 11, 12, 11)
        painter.drawPath(bubble)

    elif name == "sliders":
        for y, knob_x in ((15, 18), (24, 30), (33, 21)):
            painter.drawLine(QPointF(10, y), QPointF(38, y))
            painter.drawEllipse(QPointF(knob_x, y), 3.5, 3.5)

    elif name == "pulse":
        wave = QPainterPath()
        wave.moveTo(8, 25)
        wave.lineTo(15, 25)
        wave.lineTo(20, 13)
        wave.lineTo(27, 35)
        wave.lineTo(32, 22)
        wave.lineTo(40, 22)
        painter.drawPath(wave)

    elif name == "hardware":
        painter.drawRoundedRect(QRectF(14, 14, 20, 20), 3.0, 3.0)
        painter.drawRect(QRectF(20, 20, 8, 8))
        for offset in (18, 24, 30):
            painter.drawLine(QPointF(offset, 9), QPointF(offset, 14))
            painter.drawLine(QPointF(offset, 34), QPointF(offset, 39))
            painter.drawLine(QPointF(9, offset), QPointF(14, offset))
            painter.drawLine(QPointF(34, offset), QPointF(39, offset))

    elif name == "user":
        painter.drawEllipse(QRectF(17, 11, 14, 14))
        arc = QPainterPath()
        arc.moveTo(11, 38)
        arc.quadTo(11, 29, 24, 29)
        arc.quadTo(37, 29, 37, 38)
        painter.drawPath(arc)

    elif name == "attach":
        path = QPainterPath()
        path.moveTo(29, 15)
        path.lineTo(29, 30)
        path.arcTo(QRectF(19, 25, 10, 10), 0, -180)
        path.lineTo(19, 15)
        path.arcTo(QRectF(19, 8, 15, 15), 180, -180)
        path.lineTo(34, 29)
        path.arcTo(QRectF(23, 24, 11, 11), 0, -180)
        path.lineTo(23, 17)
        painter.drawPath(path)

    elif name == "file":
        page = QPainterPath()
        page.moveTo(13, 8)
        page.lineTo(28, 8)
        page.lineTo(35, 15)
        page.lineTo(35, 40)
        page.lineTo(13, 40)
        page.closeSubpath()
        painter.drawPath(page)
        painter.drawLine(QPointF(28, 8), QPointF(28, 15))
        painter.drawLine(QPointF(28, 15), QPointF(35, 15))

    elif name == "refresh":
        painter.drawArc(QRectF(9.5, 9.5, 29.0, 29.0), 44 * 16, 294 * 16)
        tip = QPointF(35.0, 14.2)
        arrow = QPainterPath()
        arrow.moveTo(tip.x() - 7.2, tip.y())
        arrow.lineTo(tip.x(), tip.y())
        arrow.lineTo(tip.x(), tip.y() - 7.2)
        painter.drawPath(arrow)

    elif name == "copy":
        painter.drawRoundedRect(QRectF(18.0, 8.5, 18.0, 23.5), 4.5, 4.5)
        back = QPainterPath()
        back.moveTo(12.0, 16.5)
        back.lineTo(12.0, 34.0)
        back.quadTo(12.0, 39.0, 17.0, 39.0)
        back.lineTo(28.5, 39.0)
        painter.drawPath(back)

    elif name == "check":
        path = QPainterPath()
        path.moveTo(11, 25)
        path.lineTo(20, 34)
        path.lineTo(37, 15)
        painter.drawPath(path)

    elif name == "bulb":
        painter.drawArc(QRectF(13, 8, 22, 22), -42 * 16, 264 * 16)
        painter.drawLine(QPointF(16.2, 26.5), QPointF(19, 32))
        painter.drawLine(QPointF(31.8, 26.5), QPointF(29, 32))
        painter.drawLine(QPointF(19, 32), QPointF(29, 32))
        painter.drawLine(QPointF(19, 36.5), QPointF(29, 36.5))
        painter.drawLine(QPointF(21, 41), QPointF(27, 41))

    elif name == "code":
        left = QPainterPath()
        left.moveTo(17, 16)
        left.lineTo(9, 24)
        left.lineTo(17, 32)
        painter.drawPath(left)

        right = QPainterPath()
        right.moveTo(31, 16)
        right.lineTo(39, 24)
        right.lineTo(31, 32)
        painter.drawPath(right)

        painter.drawLine(QPointF(27, 13), QPointF(21, 35))

    elif name == "bug":
        painter.drawEllipse(QRectF(16, 15, 16, 22))
        painter.drawArc(QRectF(19, 10, 10, 9), 0, 180 * 16)
        painter.drawLine(QPointF(24, 16), QPointF(24, 37))
        painter.drawLine(QPointF(16, 20), QPointF(10, 17))
        painter.drawLine(QPointF(16, 26), QPointF(9, 26))
        painter.drawLine(QPointF(16, 32), QPointF(10, 35))
        painter.drawLine(QPointF(32, 20), QPointF(38, 17))
        painter.drawLine(QPointF(32, 26), QPointF(39, 26))
        painter.drawLine(QPointF(32, 32), QPointF(38, 35))

    elif name == "sparkle":
        star = QPainterPath()
        star.moveTo(24, 8)
        star.quadTo(24, 24, 40, 24)
        star.quadTo(24, 24, 24, 40)
        star.quadTo(24, 24, 8, 24)
        star.quadTo(24, 24, 24, 8)
        star.closeSubpath()
        painter.drawPath(star)


def make_pixmap(name, color="#64748b", size=16):
    pm = QPixmap(48, 48)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    _paint_vector(p, name, color)
    p.end()
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def make_icon(name, color="#64748b", hover_color=None):
    icon = QIcon()
    states = [(QIcon.Normal, color)]
    if hover_color:
        states.append((QIcon.Active, hover_color))
    for state, hex_col in states:
        pm = QPixmap(48, 48)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        _paint_vector(p, name, hex_col)
        p.end()
        icon.addPixmap(pm, state)
    return icon


class ToggleSwitch(QAbstractButton):

    def __init__(self, checked=False, active_color="#1d63ed", inactive_color="#cbd5e1", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._active_color = active_color
        self._inactive_color = inactive_color
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)

    def set_colors(self, active_color, inactive_color):
        self._active_color = active_color
        self._inactive_color = inactive_color
        self.update()

    def sizeHint(self):
        return QSize(40, 22)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)

        track_color = QColor(self._active_color if self.isChecked() else self._inactive_color)
        p.setBrush(track_color)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 11.0, 11.0)

        knob_x = self.width() - 19 if self.isChecked() else 3
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(knob_x, 3, 16, 16))
        p.end()