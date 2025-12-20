# ui/garland_widget.py
"""
Новогодняя гирлянда с анимированными огоньками.
Премиум-фича для украшения окна.
"""

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen, QPainterPath
import random
import math


class GarlandLight:
    """Один огонёк гирлянды"""
    
    COLORS = [
        QColor(255, 50, 50),    # Красный
        QColor(50, 255, 50),    # Зелёный
        QColor(50, 100, 255),   # Синий
        QColor(255, 200, 50),   # Жёлтый/золотой
        QColor(255, 100, 200),  # Розовый
        QColor(50, 255, 255),   # Голубой
        QColor(255, 150, 50),   # Оранжевый
    ]
    
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.color = random.choice(self.COLORS)
        self.brightness = random.uniform(0.3, 1.0)
        self.target_brightness = random.uniform(0.3, 1.0)
        self.size = random.uniform(6, 10)
        self.phase = random.uniform(0, 2 * math.pi)  # Для эффекта мерцания
        
    def update(self):
        """Плавное изменение яркости"""
        # Плавный переход к целевой яркости
        diff = self.target_brightness - self.brightness
        self.brightness += diff * 0.1
        
        # Случайно меняем цель
        if random.random() < 0.02:  # 2% шанс каждый тик
            self.target_brightness = random.uniform(0.2, 1.0)
            
    def get_current_color(self) -> QColor:
        """Возвращает цвет с учётом яркости"""
        color = QColor(self.color)
        # Добавляем мерцание через синус
        flicker = 0.7 + 0.3 * math.sin(self.phase)
        self.phase += 0.15
        
        factor = self.brightness * flicker
        return QColor(
            int(color.red() * factor),
            int(color.green() * factor),
            int(color.blue() * factor),
            255
        )


class GarlandWidget(QWidget):
    """
    Виджет новогодней гирлянды.
    Располагается в верхней части окна и показывает анимированные огоньки.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.lights = []
        self._enabled = False
        self._opacity = 0.0
        
        # Таймер анимации
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._animate)
        
        # Анимация появления/исчезновения
        self._fade_animation = None
        
        # Настройки
        self.setFixedHeight(20)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Скрываем по умолчанию
        self.hide()
        
    def _generate_lights(self):
        """Генерирует огоньки вдоль ширины виджета"""
        self.lights.clear()
        
        width = self.width()
        if width <= 0:
            return
            
        # Количество огоньков зависит от ширины
        num_lights = max(10, width // 25)
        
        # Создаём "провисающую" линию гирлянды
        for i in range(num_lights):
            x = (i + 0.5) * width / num_lights
            # Синусоидальное провисание
            progress = i / (num_lights - 1) if num_lights > 1 else 0.5
            sag = 8 * math.sin(progress * math.pi)  # Провисание в центре
            y = 6 + sag + random.uniform(-2, 2)
            
            self.lights.append(GarlandLight(x, y))
            
    def set_enabled(self, enabled: bool):
        """Включает или выключает гирлянду с анимацией"""
        if self._enabled == enabled:
            return
            
        self._enabled = enabled
        
        if enabled:
            self._generate_lights()
            self.show()
            self._fade_in()
            self.animation_timer.start(50)  # 20 FPS
        else:
            self._fade_out()
            
    def _fade_in(self):
        """Плавное появление"""
        if self._fade_animation:
            self._fade_animation.stop()
            
        self._fade_animation = QPropertyAnimation(self, b"garland_opacity")
        self._fade_animation.setDuration(500)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.start()
        
    def _fade_out(self):
        """Плавное исчезновение"""
        if self._fade_animation:
            self._fade_animation.stop()
            
        self._fade_animation = QPropertyAnimation(self, b"garland_opacity")
        self._fade_animation.setDuration(300)
        self._fade_animation.setStartValue(self._opacity)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_animation.finished.connect(self._on_fade_out_finished)
        self._fade_animation.start()
        
    def _on_fade_out_finished(self):
        """Скрываем виджет после затухания"""
        self.animation_timer.stop()
        self.hide()
        
    @pyqtProperty(float)
    def garland_opacity(self):
        return self._opacity
        
    @garland_opacity.setter
    def garland_opacity(self, value):
        self._opacity = value
        self.update()
        
    def _animate(self):
        """Обновляет состояние огоньков"""
        for light in self.lights:
            light.update()
        self.update()
        
    def resizeEvent(self, event):
        """Перегенерируем огоньки при изменении размера"""
        super().resizeEvent(event)
        if self._enabled:
            self._generate_lights()
            
    def paintEvent(self, event):
        """Отрисовка гирлянды"""
        if not self.lights or self._opacity <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)
        
        # Рисуем "провод" гирлянды
        if len(self.lights) >= 2:
            path = QPainterPath()
            path.moveTo(0, 10)
            
            for i, light in enumerate(self.lights):
                if i == 0:
                    path.lineTo(light.x, light.y)
                else:
                    # Сглаженная линия
                    prev = self.lights[i - 1]
                    ctrl_x = (prev.x + light.x) / 2
                    path.quadTo(ctrl_x, (prev.y + light.y) / 2 + 2, light.x, light.y)
            
            path.lineTo(self.width(), 10)
            
            # Рисуем провод
            wire_pen = QPen(QColor(40, 40, 40, int(200 * self._opacity)))
            wire_pen.setWidth(2)
            painter.setPen(wire_pen)
            painter.drawPath(path)
        
        # Рисуем огоньки
        for light in self.lights:
            color = light.get_current_color()
            
            # Свечение (glow)
            glow_size = light.size * 2.5
            gradient = QRadialGradient(light.x, light.y, glow_size)
            glow_color = QColor(color)
            glow_color.setAlpha(int(80 * self._opacity))
            gradient.setColorAt(0, glow_color)
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(
                QRectF(light.x - glow_size, light.y - glow_size, 
                       glow_size * 2, glow_size * 2)
            )
            
            # Сам огонёк
            painter.setBrush(color)
            painter.drawEllipse(
                QRectF(light.x - light.size / 2, light.y - light.size / 2,
                       light.size, light.size)
            )
            
            # Блик
            highlight = QColor(255, 255, 255, int(150 * light.brightness * self._opacity))
            painter.setBrush(highlight)
            painter.drawEllipse(
                QRectF(light.x - light.size / 4, light.y - light.size / 3,
                       light.size / 3, light.size / 4)
            )
            
        painter.end()
        
    def is_enabled(self) -> bool:
        """Возвращает состояние гирлянды"""
        return self._enabled

