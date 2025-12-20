# ui/splash_screen.py
"""
Splash Screen в стиле Windows 11 Fluent Design.
Мягкие цвета, плавные анимации, полупрозрачность.
"""
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRectF
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QGraphicsOpacityEffect, QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QIcon, QTransform, QPen, QPainterPath
import qtawesome as qta
import os
import math
import random
import threading
from config import APP_VERSION, CHANNEL, ICON_PATH, ICON_TEST_PATH, get_wall_animation_enabled
from log import log

# ═══════════════════════════════════════════════════════════════════════════════
# ЦВЕТОВАЯ ПАЛИТРА - Windows 11 Fluent (мягкие, приглушённые тона)
# ═══════════════════════════════════════════════════════════════════════════════
FLUENT_ACCENT = "#4c8ee7"           # Мягкий синий (как в теме)
FLUENT_ACCENT_LIGHT = "#6ba3f0"     # Светлее для hover/glow
FLUENT_ACCENT_DARK = "#3a7bd5"      # Темнее для pressed
FLUENT_BG = "22, 24, 28"            # Тёмный фон (как в теме)
FLUENT_BG_LIGHT = "30, 32, 36"      # Чуть светлее для градиента
FLUENT_BORDER = "60, 63, 68"        # Мягкая рамка
FLUENT_TEXT = "#ffffff"             # Белый текст
FLUENT_TEXT_SECONDARY = "rgba(255, 255, 255, 0.6)"  # Вторичный текст


class WallBrick:
    """Отдельный кирпич стены блокировок"""
    
    def __init__(self, x, y, width, height, index):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.index = index
        
        # Состояние кирпича
        self.integrity = 1.0  # 1.0 = целый, 0.0 = разрушен
        self.crack_level = 0.0  # Уровень трещин
        
        # Физика разлёта
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.rotation = 0.0
        self.rotation_speed = 0.0
        self.is_flying = False
        self.opacity = 1.0
        
        # Время разрушения (когда должен начать разрушаться)
        self.destruction_threshold = random.uniform(0.05, 0.95)
        
        # Вариации цвета для реалистичности
        self.color_variation = random.uniform(-15, 15)
        
        # Трещины (линии)
        self.cracks = []
        
    def start_destruction(self):
        """Запускает разлёт кирпича"""
        if not self.is_flying:
            self.is_flying = True
            # Случайное направление разлёта (в основном вниз и в стороны)
            self.velocity_x = random.uniform(-8, 8)
            self.velocity_y = random.uniform(2, 12)
            self.rotation_speed = random.uniform(-15, 15)
            
            # Генерируем трещины
            self._generate_cracks()
            
    def _generate_cracks(self):
        """Генерирует линии трещин (упрощённо)"""
        num_cracks = random.randint(1, 3)
        for _ in range(num_cracks):
            start_x = self.width / 2 + random.uniform(-self.width/4, self.width/4)
            start_y = self.height / 2 + random.uniform(-self.height/4, self.height/4)
            
            angle = random.uniform(0, 2 * math.pi)
            length = random.uniform(self.width/4, self.width * 0.7)
            
            end_x = start_x + math.cos(angle) * length
            end_y = start_y + math.sin(angle) * length
            
            self.cracks.append((start_x, start_y, end_x, end_y))
            
    def update(self):
        """Обновляет физику кирпича (оптимизировано)"""
        if self.is_flying:
            # Гравитация сильнее
            self.velocity_y += 0.7
            
            # Движение
            self.x += self.velocity_x
            self.y += self.velocity_y
            self.rotation += self.rotation_speed
            
            # Быстрее исчезают
            self.opacity = max(0, self.opacity - 0.04)
            self.integrity = max(0, self.integrity - 0.05)


class WallDestructionOverlay(QWidget):
    """Эффект разрушения стены блокировок ТСПУ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # ✅ Защита от конкурентного рисования
        self._paint_lock = threading.Lock()
        self._is_painting = False
        self._is_destroyed = False
        
        # ⚙️ Настройка анимации кирпичей (можно отключить для производительности)
        self.animation_enabled = get_wall_animation_enabled()
        log(f"Анимация стены: {'включена' if self.animation_enabled else 'отключена'}", "DEBUG")
        
        # Прогресс разрушения (0-100)
        self.progress = 0
        self.displayed_progress = 0.0
        
        # Автономный прогресс разрушения (не зависит от застревания)
        self.autonomous_progress = 0.0
        self.min_destruction_speed = 0.4  # Минимальная скорость разрушения - БЫСТРЕЕ
        self.frame_time = 16 / 1000.0  # ~16ms в секундах
        
        # Shimmer позиция (энергия разрушения)
        self.shimmer_pos = -0.5
        self.shimmer_speed = 0.015
        
        # Кирпичи стены (только если анимация включена)
        self.bricks = []
        self.bricks_initialized = False
        
        # Частицы/осколки (только если анимация включена)
        self.particles = []
        
        # Пульсация энергии
        self.energy_pulse = 0.0
        
        # Флаг начала загрузки (чтобы анимация началась сразу)
        self.started = False
        
        # Таймер анимации
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(16)  # ~60 FPS
        
    def _init_bricks(self):
        """Инициализирует кирпичи стены (оптимизировано)"""
        if self.bricks_initialized:
            return
            
        width = self.width()
        height = self.height()
        
        if width == 0 or height == 0:
            return
            
        self.bricks_initialized = True
        self.bricks = []
        
        # Параметры сетки кирпичей - для большего окна
        brick_width = 95
        brick_height = 38
        gap = 4
        
        # Создаём стену в верхней части экрана
        wall_height = int(height * 0.6)
        
        row = 0
        y = 0
        while y < wall_height:
            offset = (brick_width // 2 + gap // 2) if row % 2 else 0
            
            x = -offset
            while x < width + brick_width:
                brick = WallBrick(
                    x=x,
                    y=y,
                    width=brick_width,
                    height=brick_height,
                    index=len(self.bricks)
                )
                self.bricks.append(brick)
                x += brick_width + gap
            
            y += brick_height + gap
            row += 1
            
        # Распределяем пороги - нижние кирпичи разрушаются раньше
        for brick in self.bricks:
            height_factor = 1.0 - (brick.y / wall_height)
            # Начинаем раньше (от 0.02) для быстрого старта
            brick.destruction_threshold = 0.02 + height_factor * 0.75 + random.uniform(-0.05, 0.05)
            brick.destruction_threshold = max(0.01, min(0.85, brick.destruction_threshold))
            
    def _spawn_particles(self, x, y, count=2):
        """Создаёт частицы в точке - мягкие цвета"""
        if len(self.particles) > 60:  # Меньше лимит для производительности
            return
        for _ in range(count):
            particle = {
                'x': x + random.uniform(-10, 10),
                'y': y + random.uniform(-10, 10),
                'vx': random.uniform(-2, 2),
                'vy': random.uniform(-4, 2),
                'size': random.uniform(2, 4),
                'opacity': 0.8,
                # Мягкие цвета вместо кислотных красных
                'color': random.choice(['#e06c75', '#d19a66', '#c67878'])
            }
            self.particles.append(particle)
            
    def _update_animation(self):
        """Обновление анимации"""
        # Инициализируем кирпичи если нужно (только если анимация включена)
        if self.animation_enabled and not self.bricks_initialized:
            self._init_bricks()
        
        # Автономное разрушение - продолжается даже если прогресс застыл
        if self.started and self.autonomous_progress < 100:
            speed = self.min_destruction_speed
            
            # Если реальный прогресс впереди - догоняем быстрее
            if self.progress > self.autonomous_progress:
                speed = max(speed, (self.progress - self.autonomous_progress) * 0.15)
            
            # Разрешаем опережать на 25% для плавности
            max_ahead = 25
            if self.autonomous_progress < self.progress + max_ahead:
                self.autonomous_progress = min(100, self.autonomous_progress + speed)
            
        # Плавное изменение отображаемого прогресса
        target = self.autonomous_progress
        if self.displayed_progress < target:
            self.displayed_progress = min(self.displayed_progress + 0.8, target)
            
        # Shimmer эффект
        self.shimmer_pos += self.shimmer_speed
        if self.shimmer_pos > 1.5:
            self.shimmer_pos = -0.5
            
        # Пульсация энергии
        self.energy_pulse += 0.1
        
        # Обновляем состояние кирпичей (только если анимация включена)
        if self.animation_enabled:
            destruction_progress = self.displayed_progress / 100.0
            
            for brick in self.bricks:
                # Проверяем, должен ли кирпич начать разрушаться
                if not brick.is_flying and destruction_progress >= brick.destruction_threshold:
                    brick.start_destruction()
                    # Создаём частицы при разрушении (меньше)
                    if random.random() < 0.5:  # Только 50% кирпичей создают частицы
                        self._spawn_particles(
                            brick.x + brick.width/2,
                            brick.y + brick.height/2,
                            count=2
                        )
                    
                # Трещины - упрощённо
                if not brick.is_flying and destruction_progress > brick.destruction_threshold * 0.8:
                    brick.crack_level = min(1.0, brick.crack_level + 0.04)
                    if len(brick.cracks) == 0 and brick.crack_level > 0.5:
                        brick._generate_cracks()
                        
                brick.update()
                
            # Обновляем частицы (оптимизировано)
            new_particles = []
            for particle in self.particles:
                particle['vy'] += 0.4  # Гравитация сильнее - быстрее исчезают
                particle['x'] += particle['vx']
                particle['y'] += particle['vy']
                particle['opacity'] -= 0.025  # Быстрее исчезают
                
                if particle['opacity'] > 0 and particle['y'] < self.height() + 30:
                    new_particles.append(particle)
            self.particles = new_particles[-80:]  # Жёсткий лимит
            
        self.update()
        
    def set_progress(self, value: int):
        """Устанавливает прогресс разрушения"""
        self.progress = max(0, min(100, value))
        
        # Запускаем автономное разрушение при первом прогрессе
        if value > 0 and not self.started:
            self.started = True
            
        # Если реальный прогресс достиг 100 - форсируем завершение
        if value >= 100:
            self.autonomous_progress = 100
        
    def paintEvent(self, event):
        """Отрисовка разрушающейся стены"""
        # ✅ Защита от конкурентного рисования
        if self._is_destroyed:
            return
            
        if not self._paint_lock.acquire(blocking=False):
            # Другой поток уже рисует - пропускаем
            return
            
        try:
            self._is_painting = True
            
            painter = QPainter(self)
            if not painter.isActive():
                return
                
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            width = self.width()
            height = self.height()
            
            # Инициализируем кирпичи если нужно
            if not self.bricks_initialized:
                self._init_bricks()
                
            # === СЛОЙ 0: Тёмный overlay для драматичности ===
            overlay_opacity = int(30 * (1 - self.displayed_progress / 100.0))
            painter.fillRect(0, 0, width, height, QColor(0, 0, 0, overlay_opacity))
            
            # === СЛОЙ 1: Рисуем стену из кирпичей (или упрощённую версию) ===
            if self.animation_enabled:
                # Полная анимация с кирпичами
                for brick in self.bricks:
                    if brick.opacity <= 0:
                        continue
                    
                    painter.save()
                    
                    # Трансформация для летящих кирпичей
                    if brick.is_flying:
                        painter.translate(brick.x + brick.width/2, brick.y + brick.height/2)
                        painter.rotate(brick.rotation)
                        painter.translate(-brick.width/2, -brick.height/2)
                    else:
                        painter.translate(brick.x, brick.y)
                        
                    # Основной цвет кирпича (красный - цвет блокировки)
                    base_r = 180 + int(brick.color_variation)
                    base_g = 50 + int(brick.color_variation * 0.3)
                    base_b = 50 + int(brick.color_variation * 0.3)
                    
                    opacity = int(255 * brick.opacity * brick.integrity)
                    brick_color = QColor(base_r, base_g, base_b, opacity)
                    
                    # Градиент для объёма
                    brick_gradient = QLinearGradient(0, 0, 0, brick.height)
                    brick_gradient.setColorAt(0.0, brick_color.lighter(120))
                    brick_gradient.setColorAt(0.3, brick_color)
                    brick_gradient.setColorAt(1.0, brick_color.darker(130))
                    
                    # Рисуем кирпич
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(brick_gradient)
                    painter.drawRoundedRect(0, 0, int(brick.width), int(brick.height), 2, 2)
                    
                    # Граница кирпича
                    border_color = QColor(100, 30, 30, int(180 * brick.opacity))
                    painter.setPen(QPen(border_color, 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(0, 0, int(brick.width), int(brick.height), 2, 2)
                    
                    # Рисуем трещины
                    if brick.cracks and brick.crack_level > 0:
                        crack_opacity = int(255 * brick.crack_level * brick.opacity)
                        crack_pen = QPen(QColor(30, 10, 10, crack_opacity), 2)
                        painter.setPen(crack_pen)
                        
                        for crack in brick.cracks:
                            start_x, start_y, end_x, end_y = crack
                            # Анимируем длину трещины
                            current_end_x = start_x + (end_x - start_x) * brick.crack_level
                            current_end_y = start_y + (end_y - start_y) * brick.crack_level
                            painter.drawLine(
                                int(start_x), int(start_y),
                                int(current_end_x), int(current_end_y)
                            )
                            
                    painter.restore()
                
            # === СЛОЙ 2: Частицы/осколки ===
            if self.animation_enabled:
                for particle in self.particles:
                    color = QColor(particle['color'])
                    color.setAlpha(int(255 * particle['opacity']))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(color)
                    size = particle['size']
                    painter.drawEllipse(
                        int(particle['x'] - size/2),
                        int(particle['y'] - size/2),
                        int(size), int(size)
                    )
                
            # === СЛОЙ 3: Энергия разрушения (shimmer) - мягкий синий Fluent ===
            if self.displayed_progress > 5:
                # Горизонтальная волна энергии
                wave_y = height * (1 - self.displayed_progress / 100.0)
                wave_height = 60  # Меньше высота

                energy_gradient = QLinearGradient(0, wave_y - wave_height, 0, wave_y + wave_height)
                pulse = (math.sin(self.energy_pulse) + 1) / 2  # 0-1
                alpha_base = int(25 + 20 * pulse)  # Меньше интенсивность

                # Мягкий синий вместо кислотного зелёного
                energy_gradient.setColorAt(0.0, QColor(76, 142, 231, 0))
                energy_gradient.setColorAt(0.3, QColor(76, 142, 231, alpha_base // 2))
                energy_gradient.setColorAt(0.5, QColor(107, 163, 240, alpha_base))
                energy_gradient.setColorAt(0.7, QColor(76, 142, 231, alpha_base // 2))
                energy_gradient.setColorAt(1.0, QColor(76, 142, 231, 0))

                painter.fillRect(0, int(wave_y - wave_height), width, int(wave_height * 2), energy_gradient)

                # Shimmer внутри зоны разрушения - мягче
                shimmer_width = 0.3
                start_x = (self.shimmer_pos - shimmer_width) * width * 1.5
                end_x = (self.shimmer_pos + shimmer_width) * width * 1.5

                shimmer_gradient = QLinearGradient(start_x, 0, end_x, 0)
                shimmer_gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
                shimmer_gradient.setColorAt(0.4, QColor(255, 255, 255, 0))
                shimmer_gradient.setColorAt(0.5, QColor(76, 142, 231, 25))  # Мягкий синий
                shimmer_gradient.setColorAt(0.6, QColor(255, 255, 255, 0))
                shimmer_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

                # Рисуем shimmer только в разрушенной области
                destroyed_height = int(height * self.displayed_progress / 100.0)
                painter.setClipRect(0, height - destroyed_height, width, destroyed_height)
                painter.fillRect(0, 0, width, height, shimmer_gradient)
                painter.setClipping(False)

            # === СЛОЙ 4: Свечение снизу - мягкий синий Fluent ===
            glow_height = 80
            glow_gradient = QLinearGradient(0, height, 0, height - glow_height)
            glow_intensity = min(1.0, self.displayed_progress / 50.0)
            glow_alpha = int(40 * glow_intensity)  # Меньше интенсивность

            # Мягкий синий
            glow_gradient.setColorAt(0.0, QColor(76, 142, 231, glow_alpha))
            glow_gradient.setColorAt(0.5, QColor(107, 163, 240, glow_alpha // 2))
            glow_gradient.setColorAt(1.0, QColor(76, 142, 231, 0))

            painter.fillRect(0, height - glow_height, width, glow_height, glow_gradient)
            
            # === СЛОЙ 5: Надпись "БЛОКИРОВКА" на стене (только если анимация включена) ===
            if self.animation_enabled and self.displayed_progress < 80:
                # Находим центр оставшейся стены
                remaining_top = height * (1 - self.displayed_progress / 100.0) * 0.5
                
                font = painter.font()
                font.setPointSize(28)
                font.setBold(True)
                font.setFamily("Arial Black")
                painter.setFont(font)
                
                text_opacity = int(180 * (1 - self.displayed_progress / 80.0))
                if text_opacity > 0:
                    # Тень
                    painter.setPen(QColor(50, 20, 20, text_opacity))
                    painter.drawText(
                        int(width/2 - 60 + 2), int(remaining_top + 2),
                        "БЛОКИРОВКА"
                    )
                    # Основной текст
                    painter.setPen(QColor(200, 60, 60, text_opacity))
                    painter.drawText(
                        int(width/2 - 60), int(remaining_top),
                        "БЛОКИРОВКА"
                    )
            
            painter.end()
            
        except Exception as e:
            # Логируем ошибку рисования но не крашим
            try:
                from log import log
                log(f"WallDestructionOverlay paintEvent error: {e}", "DEBUG")
            except Exception:
                pass
        finally:
            self._is_painting = False
            self._paint_lock.release()
        
    def stop_animation(self):
        """Останавливает анимацию"""
        self._is_destroyed = True
        self.animation_timer.stop()
        
    def closeEvent(self, event):
        """Останавливаем анимацию при закрытии"""
        self.stop_animation()
        super().closeEvent(event)


class AnimatedIconWidget(QWidget):
    """Виджет с анимированной иконкой - минималистичная версия для Fluent Design"""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.rotation_angle = 0.0
        self.scale_factor = 0.85
        self.target_scale = 1.0

        # Защита от конкурентного рисования
        self._paint_lock = threading.Lock()
        self._is_destroyed = False

        # Размер виджета с небольшим запасом
        size = int(pixmap.width() * 1.4)
        self.setFixedSize(size, size)

        # Таймер анимации (реже для производительности)
        self.rotation_timer = QTimer(self)
        self.rotation_timer.timeout.connect(self._update_rotation)
        self.rotation_timer.start(25)  # ~40 FPS вместо 60

        # Параметры - более плавные
        self.rotation_speed = 0.3  # Медленнее вращение
        self.pulse_phase = 0.0
        self.shake_offset_x = 0.0
        self.shake_offset_y = 0.0
        self.progress = 0

        # Мягкий ореол
        self.glow_phase = 0.0

        # Одно кольцо вместо трёх (минимализм)
        self.energy_rings = [{'phase': 0.0, 'speed': 0.03}]
        
    def _update_rotation(self):
        """Обновление анимации - плавная версия"""
        self.rotation_angle = (self.rotation_angle + self.rotation_speed) % 360
        self.pulse_phase += 0.04  # Медленнее пульсация
        self.glow_phase += 0.06

        # Обновляем кольца энергии
        for ring in self.energy_rings:
            ring['phase'] += ring['speed']

        # Убрана тряска - более спокойная анимация
        self.shake_offset_x = 0
        self.shake_offset_y = 0

        self.update()
        
    def set_progress(self, progress: int):
        """Обновляет состояние в зависимости от прогресса - плавная версия"""
        progress = max(0, min(100, progress))
        self.progress = progress

        # Плавный рост масштаба
        self.scale_factor = 0.85 + (progress / 100.0) * 0.15

        # Вращение почти постоянное (минимальные изменения)
        self.rotation_speed = 0.3 + (progress / 100.0) * 0.2
        
    def paintEvent(self, event):
        """Отрисовка иконки - минималистичная версия Fluent Design"""
        if self._is_destroyed:
            return

        if not self._paint_lock.acquire(blocking=False):
            return

        try:
            painter = QPainter(self)
            if not painter.isActive():
                return

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            center_x = self.width() / 2
            center_y = self.height() / 2

            # Мягкое кольцо (одно, тонкое)
            if self.progress > 5:
                for ring in self.energy_rings:
                    ring_progress = (math.sin(ring['phase']) + 1) / 2
                    base_size = self.original_pixmap.width() * self.scale_factor
                    ring_size = int(base_size * (1.0 + ring_progress * 0.4))
                    ring_alpha = int(30 * (1 - ring_progress) * min(1.0, self.progress / 30))

                    if ring_alpha > 0:
                        # Мягкий синий вместо кислотного зелёного
                        ring_pen = QPen(QColor(76, 142, 231, ring_alpha), 1)
                        painter.setPen(ring_pen)
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawEllipse(
                            int(center_x - ring_size/2),
                            int(center_y - ring_size/2),
                            ring_size, ring_size
                        )

            # Мягкий ореол (subtle glow)
            if self.progress > 10:
                glow_size = int(self.original_pixmap.width() * self.scale_factor * 1.3)
                glow_alpha = int(20 + 15 * math.sin(self.glow_phase))

                glow_gradient = QLinearGradient(
                    center_x - glow_size/2, center_y - glow_size/2,
                    center_x + glow_size/2, center_y + glow_size/2
                )
                # Мягкий синий
                glow_gradient.setColorAt(0.0, QColor(76, 142, 231, 0))
                glow_gradient.setColorAt(0.5, QColor(76, 142, 231, glow_alpha))
                glow_gradient.setColorAt(1.0, QColor(76, 142, 231, 0))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(glow_gradient)
                painter.drawEllipse(
                    int(center_x - glow_size/2),
                    int(center_y - glow_size/2),
                    glow_size, glow_size
                )

            # Минимальная пульсация
            pulse = math.sin(self.pulse_phase) * 0.01
            current_scale = self.scale_factor + pulse

            # Трансформация иконки
            transform = QTransform()
            transform.translate(center_x, center_y)
            transform.rotate(self.rotation_angle)
            transform.scale(current_scale, current_scale)
            transform.translate(-self.original_pixmap.width() / 2, -self.original_pixmap.height() / 2)

            painter.setTransform(transform)
            painter.drawPixmap(0, 0, self.original_pixmap)
            painter.end()

        except Exception:
            pass
        finally:
            self._paint_lock.release()
        
    def stop_animation(self):
        """Останавливает анимацию"""
        self._is_destroyed = True
        self.rotation_timer.stop()


class SplashScreen(QWidget):
    """
    Splash Screen в стиле Windows 11 Fluent Design.
    Мягкие цвета, плавные анимации, минималистичный дизайн.
    """

    load_complete = pyqtSignal()
    _progress_signal = pyqtSignal(int, str, str)

    def __init__(self):
        super().__init__(None)

        # Флаги окна: без рамки, всегда сверху, прозрачный фон для скруглённых углов
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Размер и позиция - компактное окно в стиле Windows 11
        self.setFixedSize(480, 520)
        self._center_on_screen()

        self.animated_icon = None
        self.wall_overlay = None
        self._loading_complete = False

        # Параметры для отрисовки - Windows 11 Fluent стиль
        self._border_radius = 12  # Меньше радиус как в Windows 11
        self._glow_animation_phase = 0.0
        self._particle_effects = []  # Минимум частиц

        self.init_ui()
        self._progress_signal.connect(self._do_set_progress)

        # Анимация свечения рамки (медленнее для мягкости)
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self._update_glow)
        self._glow_timer.start(50)  # Реже для производительности

        # Эффект появления
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self._fade_in()
    
    def _fade_in(self):
        """Анимация плавного появления"""
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_animation.start()
    
    def _update_glow(self):
        """Обновление анимации свечения рамки - минималистичная версия"""
        self._glow_animation_phase += 0.03  # Медленнее для мягкости

        # Частицы отключены для чистого Windows 11 стиля
        # Только мягкое свечение рамки

        self.update()  # Перерисовка
    
    def _center_on_screen(self):
        """Центрирует окно на экране"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)
    
    def paintEvent(self, event):
        """Кастомная отрисовка в стиле Windows 11 Fluent Design"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        radius = self._border_radius

        # ═══════════════════════════════════════════════════════════
        # СЛОЙ 1: Мягкое внешнее свечение (subtle glow)
        # ═══════════════════════════════════════════════════════════
        glow_intensity = (math.sin(self._glow_animation_phase) + 1) / 2  # 0-1
        glow_alpha = int(20 + 15 * glow_intensity)  # Меньше интенсивность

        # Только один мягкий слой свечения
        glow_color = QColor(76, 142, 231, glow_alpha)  # Мягкий синий
        glow_rect = rect.adjusted(4, 4, -4, -4)

        path = QPainterPath()
        path.addRoundedRect(QRectF(glow_rect), radius + 4, radius + 4)
        painter.fillPath(path, glow_color)

        # ═══════════════════════════════════════════════════════════
        # СЛОЙ 2: Основной фон с градиентом (Windows 11 style)
        # ═══════════════════════════════════════════════════════════
        bg_rect = rect.adjusted(1, 1, -1, -1)

        # Градиент фона - тёмный, как в основном окне
        bg_gradient = QLinearGradient(0, 0, 0, self.height())
        bg_gradient.setColorAt(0.0, QColor(30, 32, 36))      # Верх
        bg_gradient.setColorAt(0.5, QColor(26, 28, 32))      # Середина
        bg_gradient.setColorAt(1.0, QColor(22, 24, 28))      # Низ

        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(bg_rect), radius, radius)
        painter.fillPath(bg_path, bg_gradient)

        # ═══════════════════════════════════════════════════════════
        # СЛОЙ 3: Тонкая рамка (Windows 11 style - 1px)
        # ═══════════════════════════════════════════════════════════
        border_rect = rect.adjusted(1, 1, -1, -1)

        # Статичная мягкая рамка (без анимации для чистоты)
        border_color = QColor(60, 63, 68, 180)  # Мягкий серый

        border_pen = QPen(border_color, 1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(border_rect), radius, radius)

        # ═══════════════════════════════════════════════════════════
        # СЛОЙ 4: Тонкий блик сверху (subtle glass effect)
        # ═══════════════════════════════════════════════════════════
        highlight_rect = QRectF(bg_rect.x() + 15, bg_rect.y() + 2,
                                bg_rect.width() - 30, 25)
        highlight_gradient = QLinearGradient(0, highlight_rect.top(), 0, highlight_rect.bottom())
        highlight_gradient.setColorAt(0.0, QColor(255, 255, 255, 8))
        highlight_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(highlight_rect, radius - 1, radius - 1)
        painter.fillPath(highlight_path, highlight_gradient)

        painter.end()
    
    def init_ui(self):
        """Инициализация интерфейса в стиле Windows 11 Fluent"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Центральный контейнер
        central_container = QWidget(self)
        central_container.setStyleSheet("background: transparent;")
        central_layout = QVBoxLayout(central_container)
        central_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        central_layout.setSpacing(12)

        # Иконка
        icon_path = ICON_TEST_PATH if CHANNEL.lower() == "test" else ICON_PATH

        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            pixmap = icon.pixmap(96, 96)  # Компактнее
        else:
            icon = qta.icon('fa5s.shield-alt', color=FLUENT_ACCENT)
            pixmap = icon.pixmap(96, 96)

        self.animated_icon = AnimatedIconWidget(pixmap, parent=central_container)
        central_layout.addWidget(self.animated_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        central_layout.addSpacing(8)

        # Заголовок - чистый белый без градиента
        title = QLabel("Zapret2")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                color: {FLUENT_TEXT};
                font-size: 32px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                background: transparent;
                letter-spacing: 1px;
            }}
        """)
        central_layout.addWidget(title)

        # Подзаголовок
        subtitle = QLabel("Обход блокировок")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: {FLUENT_TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 400;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
                letter-spacing: 1px;
            }}
        """)
        central_layout.addWidget(subtitle)

        central_layout.addSpacing(4)

        # Версия - мягкий синий
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(f"""
            QLabel {{
                color: {FLUENT_ACCENT};
                font-size: 13px;
                font-weight: 500;
                font-family: 'Segoe UI', 'Consolas', monospace;
                background: transparent;
            }}
        """)
        central_layout.addWidget(version_label)

        # Канал (если не release)
        if CHANNEL.lower() != "release":
            channel_label = QLabel(f"{CHANNEL.upper()}")
            channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            channel_label.setStyleSheet(f"""
                QLabel {{
                    color: #1a1a1a;
                    background: {FLUENT_ACCENT};
                    font-size: 10px;
                    font-weight: 600;
                    padding: 4px 12px;
                    border-radius: 10px;
                }}
            """)
            central_layout.addWidget(channel_label, alignment=Qt.AlignmentFlag.AlignCenter)

        central_layout.addSpacing(16)

        # Контейнер прогресса
        progress_container = QWidget(central_container)
        progress_container.setMaximumWidth(360)
        progress_container.setStyleSheet("background: transparent;")
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)

        # Статус
        self.status_label = QLabel("Загрузка...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {FLUENT_TEXT_SECONDARY};
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
            }}
        """)
        progress_layout.addWidget(self.status_label)

        # Прогресс-бар в стиле Windows 11
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)  # Тонкий как в Windows 11
        self.progress_bar.setMinimumWidth(320)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {FLUENT_ACCENT};
                border-radius: 2px;
            }}
        """)
        progress_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        # Процент
        self.percent_label = QLabel("0%")
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.percent_label.setStyleSheet(f"""
            QLabel {{
                color: {FLUENT_ACCENT};
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
            }}
        """)
        progress_layout.addWidget(self.percent_label)

        # Детали
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.4);
                font-size: 11px;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
            }
        """)
        progress_layout.addWidget(self.detail_label)

        central_layout.addWidget(progress_container, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(central_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # Анимация стены (опционально) - отключена по умолчанию для производительности
        animation_enabled = get_wall_animation_enabled()
        if animation_enabled:
            self.wall_overlay = WallDestructionOverlay(self)
        else:
            self.wall_overlay = None
    
    def resizeEvent(self, event):
        """Растягиваем overlay"""
        super().resizeEvent(event)
        if self.wall_overlay:
            self.wall_overlay.setGeometry(0, 0, self.width(), self.height())
            self.wall_overlay.raise_()
    
    def fade_out(self):
        """Анимация исчезновения"""
        if self._loading_complete:
            return
        
        self._loading_complete = True
        
        # Останавливаем анимации
        if hasattr(self, '_glow_timer'):
            self._glow_timer.stop()
        if self.animated_icon:
            self.animated_icon.stop_animation()
        if self.wall_overlay:
            self.wall_overlay.stop_animation()
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(450)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_animation.finished.connect(self._on_fade_complete)
        self.fade_animation.start()
    
    def _on_fade_complete(self):
        """Вызывается после завершения анимации исчезновения"""
        self.load_complete.emit()
        self.close()
    
    def set_progress(self, value: int, status: str = "", detail: str = ""):
        """Обновляет прогресс (потокобезопасно)"""
        import threading
        if QApplication.instance() and threading.current_thread() != threading.main_thread():
            self._progress_signal.emit(value, status, detail)
            return
        self._do_set_progress(value, status, detail)
    
    def _do_set_progress(self, value: int, status: str = "", detail: str = ""):
        """Внутренний метод обновления прогресса"""
        try:
            self.progress_bar.setValue(min(value, 100))
            self.percent_label.setText(f"{min(value, 100)}%")
            
            if self.animated_icon:
                self.animated_icon.set_progress(min(value, 100))
            
            if self.wall_overlay:
                self.wall_overlay.set_progress(min(value, 100))
            
            if status:
                self.status_label.setText(status)
            if detail:
                self.detail_label.setText(detail)
            
            if value >= 100 and not self._loading_complete:
                log("SplashScreen: прогресс 100%, закрываемся", "DEBUG")
                QTimer.singleShot(300, self.fade_out)
        except RuntimeError:
            pass
    
    def finish(self):
        """Принудительное завершение splash"""
        self.set_progress(100, "Готово!", "")
    
    def show_error(self, error: str):
        """Показывает ошибку и закрывает splash через 3 секунды"""
        if self.animated_icon:
            self.animated_icon.stop_animation()
        if self.wall_overlay:
            self.wall_overlay.stop_animation()

        # Цвет ошибки - мягкий красный
        error_color = "#e06c75"

        self.status_label.setText(f"Ошибка: {error}")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {error_color};
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
            }}
        """)
        self.percent_label.setText("—")
        self.percent_label.setStyleSheet(f"""
            QLabel {{
                color: {error_color};
                font-size: 11px;
                font-weight: 500;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
            }}
        """)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {error_color};
                border-radius: 2px;
            }}
        """)
        QTimer.singleShot(3000, self.fade_out)
