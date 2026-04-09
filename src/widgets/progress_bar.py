# widgets/progress_bar.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QFont

from ui.theme import get_theme_tokens
from ui.theme_refresh import ThemeRefreshController

class AnimatedProgressBar(QWidget):
    """Красивый анимированный прогресс-бар с текстом статуса"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()
        self._is_visible = False
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme_styles)
        
    def setupUI(self):
        # Основной layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Метка статуса
        self.status_label = QLabel("Инициализация...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        self.status_label.setFont(font)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Добавляем виджеты
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

        self._apply_theme_styles()

        # Эффект прозрачности для анимации
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)
        
        # Анимация появления/скрытия
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Анимация прогресса
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setDuration(200)
        self.progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Таймер для пульсации при долгой загрузке
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self._pulse_effect)
        self.pulse_direction = 1
        
        # Скрываем по умолчанию
        self.hide()

    def _apply_theme_styles(self):
        tokens = get_theme_tokens()
        if tokens.is_light:
            panel_bg = "rgba(255, 255, 255, 0.84)"
            panel_border = "rgba(0, 0, 0, 0.08)"
            bar_bg = "rgba(0, 0, 0, 0.10)"
        else:
            panel_bg = "rgba(0, 0, 0, 0.20)"
            panel_border = "rgba(255, 255, 255, 0.05)"
            bar_bg = "rgba(255, 255, 255, 0.08)"

        chunk_bg = f"rgba({tokens.accent_rgb_str}, 0.60)"

        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                text-align: center;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 500;
                font-size: 10px;
                color: {tokens.fg_muted};
                background-color: {bar_bg};
                min-height: 6px;
                max-height: 6px;
            }}

            QProgressBar::chunk {{
                background: {chunk_bg};
                border-radius: 3px;
            }}
            """
        )

        self.status_label.setStyleSheet(
            f"""
            QLabel {{
                color: {tokens.fg_muted};
                background-color: transparent;
                padding: 6px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                font-weight: 400;
            }}
            """
        )

        self.setStyleSheet(
            f"""
            AnimatedProgressBar {{
                background-color: {panel_bg};
                border-radius: 16px;
                border: 1px solid {panel_border};
            }}
            """
        )
    
    def show_animated(self):
        """Показать с анимацией"""
        if not self._is_visible:
            self._is_visible = True
            self.show()
            self.fade_animation.setStartValue(0)
            self.fade_animation.setEndValue(1)
            self.fade_animation.start()
            
            # Запускаем пульсацию через 3 секунды
            QTimer.singleShot(3000, self.start_pulse)
    
    def hide_animated(self):
        """Скрыть с анимацией"""
        if self._is_visible:
            self._is_visible = False
            self.stop_pulse()
            self.fade_animation.setStartValue(1)
            self.fade_animation.setEndValue(0)
            self.fade_animation.finished.connect(self.hide)
            self.fade_animation.start()
    
    def set_progress(self, value: int, text: str = None):
        """Установить прогресс с анимацией"""
        # Анимированное изменение значения
        self.progress_animation.setStartValue(self.progress_bar.value())
        self.progress_animation.setEndValue(value)
        self.progress_animation.start()
        
        # Обновляем текст
        if text:
            self.status_label.setText(text)
            
        # Останавливаем пульсацию при 100%
        if value >= 100:
            self.stop_pulse()
            self.status_label.setText("✅ Инициализация завершена!")
            # Автоскрытие через 2 секунды
            QTimer.singleShot(2000, self.hide_animated)
    
    def start_pulse(self):
        """Начать эффект пульсации"""
        if self.progress_bar.value() < 90:  # Только если не почти завершено
            self.pulse_timer.start(50)
    
    def stop_pulse(self):
        """Остановить пульсацию"""
        self.pulse_timer.stop()
        self.progress_bar.setStyleSheet(self.progress_bar.styleSheet())  # Сброс стиля
    
    def _pulse_effect(self):
        """Эффект пульсации для индикации активности"""
        opacity = self.opacity_effect.opacity()
        opacity += 0.02 * self.pulse_direction
        
        if opacity >= 1:
            self.pulse_direction = -1
            opacity = 1
        elif opacity <= 0.7:
            self.pulse_direction = 1
            opacity = 0.7
            
        self.opacity_effect.setOpacity(opacity)
