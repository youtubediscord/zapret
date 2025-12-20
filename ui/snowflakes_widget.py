# ui/snowflakes_widget.py
"""
Мягко падающие снежинки.
Премиум-фича для украшения окна.
"""

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QEvent
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QRadialGradient
import random
import math


class Snowflake:
    """Одна снежинка"""
    
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        
        # Размер снежинки (маленькие падают медленнее)
        self.size = random.uniform(1.5, 4)
        
        # Скорость падения (зависит от размера)
        self.speed = 0.2 + self.size * 0.12
        
        # Горизонтальное покачивание
        self.wobble_phase = random.uniform(0, 2 * math.pi)
        self.wobble_amplitude = random.uniform(0.2, 0.6)
        self.wobble_speed = random.uniform(0.015, 0.04)
        
        # Прозрачность (более прозрачные снежинки)
        self.opacity = random.uniform(0.15, 0.4)
        
        # Вращение
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-2, 2)
        
    def update(self, max_height: int) -> bool:
        """Обновляет позицию снежинки. Возвращает False если вышла за экран."""
        # Падение
        self.y += self.speed
        
        # Покачивание
        self.wobble_phase += self.wobble_speed
        self.x += math.sin(self.wobble_phase) * self.wobble_amplitude
        
        # Вращение
        self.rotation += self.rotation_speed
        
        # Держим заметно дольше, чтобы точно пройти весь экран
        return self.y < max_height + 800


class SnowflakesWidget(QWidget):
    """
    Виджет снежинок.
    Покрывает всё окно и показывает мягко падающие снежинки.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.snowflakes = []
        self._enabled = False
        self._opacity = 0.0
        self._intensity = 15  # Количество снежинок для спавна
        self._cached_height = 0  # Кэшированная высота для корректного удаления
        
        # Таймер анимации
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._animate)
        
        # Таймер спавна новых снежинок
        self.spawn_timer = QTimer(self)
        self.spawn_timer.timeout.connect(self._spawn_snowflakes)
        
        # Анимация появления/исчезновения
        self._fade_animation = None
        
        # Настройки
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Скрываем по умолчанию
        self.hide()
        
    def showEvent(self, event):
        """При показе устанавливаем фильтр событий на родителя"""
        super().showEvent(event)
        if self.parent():
            self.parent().installEventFilter(self)
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
            self._cached_height = max(self._cached_height, self.parent().height())
        if self.window() and self.window() is not self.parent():
            self.window().installEventFilter(self)
            
    def eventFilter(self, obj, event):
        """Отслеживаем изменение размера родителя"""
        if event.type() == QEvent.Type.Resize:
            if obj == self.parent():
                self.setGeometry(0, 0, self.parent().width(), self.parent().height())
                self._cached_height = max(self._cached_height, self.parent().height())
            elif obj == self.window():
                self.setGeometry(0, 0, self.window().width(), self.window().height())
                self._cached_height = max(self._cached_height, self.window().height())
        return super().eventFilter(obj, event)

    def _spawn_snowflakes(self):
        """Создаёт новые снежинки сверху"""
        if not self._enabled:
            return
            
        width = self.width()
        height = self.height()
        
        # Если геометрия ещё не установлена, берём от родителя/окна
        if (width <= 0 or height <= 0) and self.parent():
            width = max(width, self.parent().width())
            height = max(height, self.parent().height())
        if (width <= 0 or height <= 0) and self.window():
            width = max(width, self.window().width())
            height = max(height, self.window().height())
        
        if width <= 0 or height <= 0:
            return
        
        # Обновляем кэш высоты
        self._cached_height = max(self._cached_height, height)
        
        # Спавним несколько снежинок
        for _ in range(random.randint(1, 3)):
            x = random.uniform(-20, width + 20)
            y = random.uniform(-30, -5)
            self.snowflakes.append(Snowflake(x, y))
        
        # Ограничиваем количество снежинок
        max_flakes = max(50, (width * height) // 8000)
        if len(self.snowflakes) > max_flakes:
            self.snowflakes = self.snowflakes[-max_flakes:]
            
    def set_enabled(self, enabled: bool):
        """Включает или выключает снежинки с анимацией"""
        if self._enabled == enabled:
            return
            
        self._enabled = enabled
        
        if enabled:
            self.snowflakes.clear()
            # Начальные снежинки по всему экрану
            self._generate_initial_snowflakes()
            self.show()
            self._fade_in()
            self.animation_timer.start(33)  # ~30 FPS
            self.spawn_timer.start(300)  # Новые снежинки каждые 300мс
        else:
            self._fade_out()
            
    def _generate_initial_snowflakes(self):
        """Генерирует начальные снежинки по всему экрану"""
        width = self.width()
        height = self.height()
        
        # Если геометрия ещё не установлена, берём от родителя/окна
        if (width <= 0 or height <= 0) and self.parent():
            width = max(width, self.parent().width())
            height = max(height, self.parent().height())
        if (width <= 0 or height <= 0) and self.window():
            width = max(width, self.window().width())
            height = max(height, self.window().height())
            
        if width <= 0 or height <= 0:
            return
        
        # Кэшируем высоту
        self._cached_height = max(self._cached_height, height)
            
        # Создаём снежинки по всей площади
        num_flakes = max(20, (width * height) // 15000)
        
        for _ in range(num_flakes):
            x = random.uniform(0, width)
            y = random.uniform(0, height)
            self.snowflakes.append(Snowflake(x, y))
            
    def _fade_in(self):
        """Плавное появление"""
        if self._fade_animation:
            self._fade_animation.stop()
            
        self._fade_animation = QPropertyAnimation(self, b"snow_opacity")
        self._fade_animation.setDuration(800)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.start()
        
    def _fade_out(self):
        """Плавное исчезновение"""
        if self._fade_animation:
            self._fade_animation.stop()
            
        self._fade_animation = QPropertyAnimation(self, b"snow_opacity")
        self._fade_animation.setDuration(500)
        self._fade_animation.setStartValue(self._opacity)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_animation.finished.connect(self._on_fade_out_finished)
        self._fade_animation.start()
        
    def _on_fade_out_finished(self):
        """Скрываем виджет после затухания"""
        self.animation_timer.stop()
        self.spawn_timer.stop()
        self.snowflakes.clear()
        self.hide()
        
    @pyqtProperty(float)
    def snow_opacity(self):
        return self._opacity
        
    @snow_opacity.setter
    def snow_opacity(self, value):
        self._opacity = value
        self.update()
        
    def _animate(self):
        """Обновляет состояние снежинок"""
        # Используем кэшированную высоту или текущую (берём максимум)
        current_h = self.height()
        
        parent_w = parent_h = 0
        window_w = window_h = 0
        
        # Если есть родитель, синхронизируем размер принудительно
        if self.parent():
            parent_w = self.parent().width()
            parent_h = self.parent().height()
            if parent_w != self.width() or parent_h != self.height():
                self.setGeometry(0, 0, parent_w, parent_h)
                current_h = self.height()
        
        # Если есть окно, учитываем его размер (на случай кастомного контейнера)
        if self.window():
            window_w = self.window().width()
            window_h = self.window().height()

        max_h = max(current_h, parent_h, window_h, self._cached_height, 800)  # Минимум 800px
        
        # Обновляем кэш если какая-либо из высот больше
        self._cached_height = max(self._cached_height, current_h, parent_h, window_h)
        
        # Обновляем и удаляем вышедшие за границы
        self.snowflakes = [sf for sf in self.snowflakes if sf.update(max_h)]
        self.update()
        
    def resizeEvent(self, event):
        """Обновляем границы при изменении размера"""
        super().resizeEvent(event)
        # Кэшируем высоту только если она больше 0
        if self.height() > 0:
            self._cached_height = max(self._cached_height, self.height())
            
    def paintEvent(self, event):
        """Отрисовка снежинок"""
        if not self.snowflakes or self._opacity <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for sf in self.snowflakes:
            # Общая прозрачность (мягкая, не яркая)
            alpha = int(180 * sf.opacity * self._opacity)
            
            # Лёгкое свечение (едва заметное)
            glow_size = sf.size * 1.5
            gradient = QRadialGradient(sf.x, sf.y, glow_size)
            gradient.setColorAt(0, QColor(255, 255, 255, alpha // 3))
            gradient.setColorAt(0.7, QColor(200, 220, 255, alpha // 6))
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(
                QRectF(sf.x - glow_size, sf.y - glow_size,
                       glow_size * 2, glow_size * 2)
            )
            
            # Сама снежинка (полупрозрачная)
            painter.setBrush(QColor(255, 255, 255, int(alpha * 0.7)))
            painter.drawEllipse(
                QRectF(sf.x - sf.size / 2, sf.y - sf.size / 2,
                       sf.size, sf.size)
            )
            
        painter.end()
        
    def is_enabled(self) -> bool:
        """Возвращает состояние снежинок"""
        return self._enabled

