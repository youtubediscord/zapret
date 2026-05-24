"""Лёгкая skeleton-загрузка для списка профилей."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ui.theme import get_theme_tokens


class ProfileLoadingSkeleton(QWidget):
    """Анимированные строки-заглушки на месте будущего списка profile-ов."""

    _ROW_HEIGHT = 44
    _ROW_GAP = 8
    _TOP_MARGIN = 4

    def __init__(self, parent=None, *, rows: int = 5):
        super().__init__(parent)
        self._rows = max(1, int(rows))
        self._phase = 0.0
        self._active = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._active = True
        self.show()
        if self.isVisible() and not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        self.hide()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._active and not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._timer.stop()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        window = self.window()
        if window is not None and window.isMinimized():
            self._timer.stop()
        elif self._active and self.isVisible() and not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.06) % 1.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            is_light = get_theme_tokens().is_light
        except Exception:
            is_light = False

        if is_light:
            row_color = QColor(0, 0, 0, 14)
            bar_color = QColor(0, 0, 0, 26)
            border_color = QColor(0, 0, 0, 18)
            shimmer_color = QColor(255, 255, 255, 95)
        else:
            row_color = QColor(255, 255, 255, 15)
            bar_color = QColor(255, 255, 255, 32)
            border_color = QColor(255, 255, 255, 22)
            shimmer_color = QColor(255, 255, 255, 42)

        width = max(1, self.width())
        row_height = self._ROW_HEIGHT
        gap = self._ROW_GAP
        top = self._TOP_MARGIN
        for index in range(self._visible_row_count(self.height())):
            y = top + index * (row_height + gap)
            row_rect = QRectF(0, y, max(1, width - 2), row_height)
            painter.setPen(QPen(border_color, 1))
            painter.setBrush(row_color)
            painter.drawRoundedRect(row_rect, 8, 8)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bar_color)
            title_width = max(96, int(width * (0.26 + 0.04 * (index % 3))))
            meta_width = max(70, int(width * (0.12 + 0.03 * ((index + 1) % 3))))
            painter.drawRoundedRect(QRectF(16, y + 13, title_width, 9), 4, 4)
            painter.drawRoundedRect(QRectF(max(16, width - meta_width - 78), y + 13, meta_width, 9), 4, 4)
            painter.drawEllipse(QRectF(max(16, width - 34), y + 15, 8, 8))

            self._paint_shimmer(painter, row_rect, shimmer_color)

    def _visible_row_count(self, height: int) -> int:
        available_height = max(0, int(height) - self._TOP_MARGIN)
        row_step = self._ROW_HEIGHT + self._ROW_GAP
        return max(self._rows, (available_height + self._ROW_GAP) // row_step)

    def _paint_shimmer(self, painter: QPainter, row_rect: QRectF, color: QColor) -> None:
        width = max(1.0, float(self.width()))
        shimmer_width = max(100.0, width * 0.22)
        x = -shimmer_width + self._phase * (width + shimmer_width * 2)
        gradient = QLinearGradient(x, 0, x + shimmer_width, 0)
        transparent = QColor(color)
        transparent.setAlpha(0)
        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(0.5, color)
        gradient.setColorAt(1.0, transparent)

        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(row_rect, 8, 8)
        painter.setClipPath(clip_path)
        painter.fillRect(QRectF(x, row_rect.top(), shimmer_width, row_rect.height()), gradient)
        painter.restore()
