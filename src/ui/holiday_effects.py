"""Holiday visual effects for the Fluent main window."""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QRectF, QTimer, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient, QRegion
from PyQt6.QtWidgets import QWidget

from ui.animation_policy import register_managed_animation, start_managed_animation


class _GarlandLight:
    COLORS = (
        (255, 80, 80),
        (80, 235, 110),
        (80, 150, 255),
        (255, 200, 90),
        (245, 140, 215),
        (100, 240, 255),
    )

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.r, self.g, self.b = random.choice(self.COLORS)
        self.brightness = random.uniform(0.35, 1.0)
        self.target_brightness = random.uniform(0.25, 1.0)
        self.size = random.uniform(5.0, 8.5)
        self.phase = random.uniform(0.0, math.tau)

    def step(self) -> None:
        self.brightness += (self.target_brightness - self.brightness) * 0.12
        if random.random() < 0.03:
            self.target_brightness = random.uniform(0.25, 1.0)
        self.phase += 0.18
        if self.phase >= math.tau:
            self.phase -= math.tau

    def color(self, alpha: float) -> QColor:
        flicker = 0.68 + 0.32 * math.sin(self.phase)
        factor = max(0.0, min(1.0, self.brightness * flicker))
        return QColor(
            int(self.r * factor),
            int(self.g * factor),
            int(self.b * factor),
            int(255 * alpha),
        )


class GarlandOverlay(QWidget):
    """Top overlay with animated garland lights."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._lights: list[_GarlandLight] = []
        self._enabled = False
        self._opacity = 0.0
        self._fade_target = 0.0
        self._fade: QPropertyAnimation | None = None
        self._last_width = 0

        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._animate)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()

    @pyqtProperty(float)
    def overlayOpacity(self) -> float:  # noqa: N802 - Qt property style
        return float(self._opacity)

    @overlayOpacity.setter
    def overlayOpacity(self, value: float) -> None:  # noqa: N802 - Qt property style
        self._opacity = max(0.0, min(1.0, float(value)))
        self.update()

    def is_enabled(self) -> bool:
        return bool(self._enabled)

    def shutdown(self) -> None:
        self._enabled = False
        self._fade_target = 0.0
        if self._fade is not None:
            self._fade.stop()
            self._fade = None
        self._timer.stop()
        self._lights.clear()
        self._opacity = 0.0
        self.hide()

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._enabled == enabled:
            if enabled:
                self.sync_geometry()
            return

        self._enabled = enabled
        if enabled:
            self.sync_geometry()
            self._generate_lights()
            self.show()
            self.raise_()
            if not self._timer.isActive():
                self._timer.start()
            self._start_fade(1.0, 420)
        else:
            self._start_fade(0.0, 240)

    def sync_geometry(self) -> None:
        host = self.parentWidget()
        if host is None:
            return

        width = int(host.width())
        if width <= 0:
            return

        title_bar = getattr(host, "titleBar", None)
        top_offset = int(title_bar.height()) if title_bar is not None else 0
        top_offset = max(0, top_offset)

        target_height = 28
        if (
            self.x() != 0
            or self.y() != top_offset
            or self.width() != width
            or self.height() != target_height
        ):
            self.setGeometry(0, top_offset, width, target_height)

        if self._last_width != width:
            self._last_width = width
            if self._enabled:
                self._generate_lights()

        if self._enabled:
            self.raise_()

    def _start_fade(self, target: float, duration_ms: int) -> None:
        self._fade_target = float(target)
        if self._fade is not None:
            self._fade.stop()

        anim = register_managed_animation(
            QPropertyAnimation(self, b"overlayOpacity", self),
            int(duration_ms),
        )
        anim.setStartValue(float(self._opacity))
        anim.setEndValue(float(target))
        anim.setEasingCurve(
            QEasingCurve.Type.OutCubic if target > self._opacity else QEasingCurve.Type.InCubic
        )
        if target <= 0.0:
            anim.finished.connect(self._finish_fade_out)
        start_managed_animation(anim)
        self._fade = anim

    def _finish_fade_out(self) -> None:
        if self._enabled or self._fade_target > 0.0:
            return
        self._timer.stop()
        self._lights.clear()
        self.hide()

    def _generate_lights(self) -> None:
        self._lights.clear()
        width = int(self.width())
        if width <= 0:
            return

        count = max(12, width // 24)
        for index in range(count):
            x = (index + 0.5) * width / count
            progress = index / (count - 1) if count > 1 else 0.5
            sag = 7.0 * math.sin(progress * math.pi)
            y = 7.0 + sag + random.uniform(-1.0, 1.0)
            self._lights.append(_GarlandLight(x, y))

    def _animate(self) -> None:
        for light in self._lights:
            light.step()
        self.update()

    def paintEvent(self, event) -> None:
        if self._opacity <= 0.0 or not self._lights:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(float(self._opacity))

        if len(self._lights) > 1:
            path = QPainterPath()
            path.moveTo(0.0, 9.0)
            for idx, light in enumerate(self._lights):
                if idx == 0:
                    path.lineTo(light.x, light.y)
                    continue
                prev = self._lights[idx - 1]
                control_x = (prev.x + light.x) * 0.5
                control_y = (prev.y + light.y) * 0.5 + 1.2
                path.quadTo(control_x, control_y, light.x, light.y)
            path.lineTo(float(self.width()), 9.0)

            pen = QPen(QColor(38, 38, 38, int(205 * self._opacity)))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawPath(path)

        painter.setPen(Qt.PenStyle.NoPen)
        for light in self._lights:
            color = light.color(self._opacity)
            glow_radius = light.size * 2.2

            gradient = QRadialGradient(light.x, light.y, glow_radius)
            glow_color = QColor(color)
            glow_color.setAlpha(int(88 * self._opacity))
            gradient.setColorAt(0.0, glow_color)
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(gradient)
            painter.drawEllipse(
                QRectF(
                    light.x - glow_radius,
                    light.y - glow_radius,
                    glow_radius * 2.0,
                    glow_radius * 2.0,
                )
            )

            painter.setBrush(color)
            painter.drawEllipse(
                QRectF(
                    light.x - light.size * 0.5,
                    light.y - light.size * 0.5,
                    light.size,
                    light.size,
                )
            )


class _Snowflake:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.size = random.uniform(1.5, 3.8)
        self.speed = 0.35 + self.size * 0.16
        self.swing_phase = random.uniform(0.0, math.tau)
        self.swing_speed = random.uniform(0.02, 0.05)
        self.swing_width = random.uniform(0.3, 1.2)
        self.opacity = random.uniform(0.18, 0.42)

    def step(self, max_height: int) -> bool:
        self.y += self.speed
        self.swing_phase += self.swing_speed
        if self.swing_phase >= math.tau:
            self.swing_phase -= math.tau
        self.x += math.sin(self.swing_phase) * self.swing_width
        return self.y < max_height + 28


class SnowflakesOverlay(QWidget):
    """Full-window overlay with falling snow particles."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._flakes: list[_Snowflake] = []
        self._enabled = False
        self._opacity = 0.0
        self._fade_target = 0.0
        self._fade: QPropertyAnimation | None = None
        self._cached_height = 0

        self._animate_timer = QTimer(self)
        self._animate_timer.setInterval(33)
        self._animate_timer.timeout.connect(self._animate)

        self._spawn_timer = QTimer(self)
        self._spawn_timer.setInterval(240)
        self._spawn_timer.timeout.connect(self._spawn)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()

    @pyqtProperty(float)
    def overlayOpacity(self) -> float:  # noqa: N802 - Qt property style
        return float(self._opacity)

    @overlayOpacity.setter
    def overlayOpacity(self, value: float) -> None:  # noqa: N802 - Qt property style
        self._opacity = max(0.0, min(1.0, float(value)))
        self.update()

    def is_enabled(self) -> bool:
        return bool(self._enabled)

    def shutdown(self) -> None:
        self._enabled = False
        self._fade_target = 0.0
        if self._fade is not None:
            self._fade.stop()
            self._fade = None
        self._animate_timer.stop()
        self._spawn_timer.stop()
        self._flakes.clear()
        self._opacity = 0.0
        self.hide()

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._enabled == enabled:
            if enabled:
                self.sync_geometry()
            return

        self._enabled = enabled
        if enabled:
            self.sync_geometry()
            self._flakes.clear()
            self._seed_visible_flakes()
            self.show()
            self.raise_()
            if not self._animate_timer.isActive():
                self._animate_timer.start()
            if not self._spawn_timer.isActive():
                self._spawn_timer.start()
            self._start_fade(1.0, 500)
        else:
            self._start_fade(0.0, 320)

    def sync_geometry(self) -> None:
        host = self.parentWidget()
        if host is None:
            return

        width = int(host.width())
        height = int(host.height())
        if width <= 0 or height <= 0:
            return

        if self.x() != 0 or self.y() != 0 or self.width() != width or self.height() != height:
            self.setGeometry(0, 0, width, height)

        self._cached_height = max(self._cached_height, height)
        if self._enabled:
            self.raise_()

    def _start_fade(self, target: float, duration_ms: int) -> None:
        self._fade_target = float(target)
        if self._fade is not None:
            self._fade.stop()

        anim = register_managed_animation(
            QPropertyAnimation(self, b"overlayOpacity", self),
            int(duration_ms),
        )
        anim.setStartValue(float(self._opacity))
        anim.setEndValue(float(target))
        anim.setEasingCurve(
            QEasingCurve.Type.OutCubic if target > self._opacity else QEasingCurve.Type.InCubic
        )
        if target <= 0.0:
            anim.finished.connect(self._finish_fade_out)
        start_managed_animation(anim)
        self._fade = anim

    def _finish_fade_out(self) -> None:
        if self._enabled or self._fade_target > 0.0:
            return
        self._animate_timer.stop()
        self._spawn_timer.stop()
        self._flakes.clear()
        self.hide()

    def _seed_visible_flakes(self) -> None:
        width = max(1, int(self.width()))
        height = max(1, int(self.height()))
        initial_count = max(24, (width * height) // 22000)
        for _ in range(initial_count):
            self._flakes.append(
                _Snowflake(
                    random.uniform(0.0, float(width)),
                    random.uniform(0.0, float(height)),
                )
            )

    def _spawn(self) -> None:
        if not self._enabled:
            return

        width = int(self.width())
        height = int(self.height())
        if width <= 0 or height <= 0:
            return

        self._cached_height = max(self._cached_height, height)
        max_count = max(70, (width * height) // 9000)
        free_slots = max_count - len(self._flakes)
        if free_slots <= 0:
            return

        spawn_count = min(random.randint(1, 3), free_slots)
        for _ in range(spawn_count):
            self._flakes.append(
                _Snowflake(
                    random.uniform(-24.0, float(width) + 24.0),
                    random.uniform(-32.0, -4.0),
                )
            )

    def _animate(self) -> None:
        self.sync_geometry()
        max_height = max(1, self._cached_height, int(self.height()))

        dirty_region = QRegion()
        visible_flakes: list[_Snowflake] = []
        for flake in self._flakes:
            old_x = flake.x
            old_y = flake.y
            if flake.step(max_height):
                visible_flakes.append(flake)
            dirty_region = dirty_region.united(QRegion(self._snowflake_motion_rect(flake, old_x, old_y)))

        self._flakes = visible_flakes
        if dirty_region.isEmpty():
            return
        self.update(dirty_region)

    def _snowflake_paint_rect(self, flake: _Snowflake) -> QRect:
        glow_size = flake.size * 1.45
        return QRectF(
            flake.x - glow_size,
            flake.y - glow_size,
            glow_size * 2.0,
            glow_size * 2.0,
        ).toAlignedRect().adjusted(-2, -2, 2, 2)

    def _snowflake_motion_rect(self, flake: _Snowflake, old_x: float, old_y: float) -> QRect:
        current_x = flake.x
        current_y = flake.y
        flake.x = old_x
        flake.y = old_y
        old_rect = self._snowflake_paint_rect(flake)
        flake.x = current_x
        flake.y = current_y
        return old_rect.united(self._snowflake_paint_rect(flake))

    def paintEvent(self, event) -> None:
        if self._opacity <= 0.0 or not self._flakes:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        dirty_region = event.region()

        for flake in self._flakes:
            if not dirty_region.intersects(self._snowflake_paint_rect(flake)):
                continue

            alpha = int(180 * flake.opacity * self._opacity)

            glow_size = flake.size * 1.45
            gradient = QRadialGradient(flake.x, flake.y, glow_size)
            gradient.setColorAt(0.0, QColor(255, 255, 255, alpha // 3))
            gradient.setColorAt(0.75, QColor(200, 220, 255, alpha // 7))
            gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(gradient)
            painter.drawEllipse(
                QRectF(
                    flake.x - glow_size,
                    flake.y - glow_size,
                    glow_size * 2.0,
                    glow_size * 2.0,
                )
            )

            painter.setBrush(QColor(255, 255, 255, int(alpha * 0.72)))
            painter.drawEllipse(
                QRectF(
                    flake.x - flake.size * 0.5,
                    flake.y - flake.size * 0.5,
                    flake.size,
                    flake.size,
                )
            )


class HolidayEffectsManager:
    """Owns holiday overlays and keeps them in sync with main window."""

    def __init__(self, host_window: QWidget):
        self._garland = GarlandOverlay(host_window)
        self._snowflakes = SnowflakesOverlay(host_window)

    def set_garland_enabled(self, enabled: bool) -> None:
        self._garland.set_enabled(bool(enabled))
        self._raise_overlays()

    def set_snowflakes_enabled(self, enabled: bool) -> None:
        self._snowflakes.set_enabled(bool(enabled))
        self._raise_overlays()

    def sync_geometry(self) -> None:
        self._snowflakes.sync_geometry()
        self._garland.sync_geometry()
        self._raise_overlays()

    def cleanup(self) -> None:
        self._garland.shutdown()
        self._snowflakes.shutdown()
        self._garland.deleteLater()
        self._snowflakes.deleteLater()

    def _raise_overlays(self) -> None:
        if self._snowflakes.isVisible():
            self._snowflakes.raise_()
        if self._garland.isVisible():
            self._garland.raise_()
