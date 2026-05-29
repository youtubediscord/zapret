from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget


class PulsingDot(QWidget):
    """Animated status dot with a low-frequency timer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#aeb5c1")
        self._pulse_phase = 0.0
        self._is_pulsing = False

        self.setFixedSize(28, 28)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)

    def set_color(self, color: str) -> None:
        c = QColor(color)
        if c.isValid():
            self._color = c
        self.update()

    def start_pulse(self) -> None:
        if not self._is_pulsing:
            self._is_pulsing = True
            self._pulse_phase = 0.0
            if self.isVisible():
                self._timer.start()

    def stop_pulse(self) -> None:
        self._is_pulsing = False
        self._timer.stop()
        self._pulse_phase = 0.0
        self.update()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._is_pulsing and not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._timer.stop()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            window = self.window()
            if window and window.isMinimized():
                self._timer.stop()
            elif self._is_pulsing and not self._timer.isActive():
                self._timer.start()

    def _tick(self) -> None:
        self._pulse_phase = (self._pulse_phase + 0.08) % 1.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2
        base_r = 5

        if self._is_pulsing:
            for phase_offset in (0.0, 0.5):
                phase = (self._pulse_phase + phase_offset) % 1.0
                opacity = max(0.0, 0.5 * (1.0 - phase))
                radius = base_r + 10 * phase
                c = QColor(self._color)
                c.setAlphaF(opacity)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(c)
                r = int(radius)
                painter.drawEllipse(int(cx - r), int(cy - r), r * 2, r * 2)

        glow = QColor(self._color)
        glow.setAlphaF(0.3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            int(cx - base_r - 2),
            int(cy - base_r - 2),
            (base_r + 2) * 2,
            (base_r + 2) * 2,
        )

        painter.setBrush(self._color)
        painter.drawEllipse(int(cx - base_r), int(cy - base_r), base_r * 2, base_r * 2)

        painter.setBrush(QColor(255, 255, 255, 90))
        painter.drawEllipse(int(cx - 2), int(cy - 3), 3, 3)
