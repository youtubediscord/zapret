# ui/widgets/notification_banner.py
"""
Виджет-уведомление (toast/banner) в стиле Windows 11 Fluent Design.

Используется для показа предупреждений и ошибок в верхней части страницы.
Поддерживает анимацию появления/исчезновения и автоматическое скрытие.
"""

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect
import qtawesome as qta

from ui.theme import get_theme_tokens
from ui.theme_refresh import ThemeRefreshController


class NotificationBanner(QWidget):
    """
    Виджет уведомления в стиле Windows 11 Fluent Design.

    Типы уведомлений:
    - error: Красный фон, иконка ошибки
    - warning: Оранжевый фон, иконка предупреждения
    - info: Голубой фон, иконка информации
    - success: Зеленый фон, иконка галочки
    """

    # Цветовые схемы для разных типов
    STYLES = {
        'error': {
            'bg': 'rgba(255, 107, 107, 0.15)',
            'border': 'rgba(255, 107, 107, 0.4)',
            'icon_color': '#ff6b6b',
            'icon': 'mdi.alert-circle',
        },
        'warning': {
            'bg': 'rgba(255, 152, 0, 0.15)',
            'border': 'rgba(255, 152, 0, 0.4)',
            'icon_color': '#ff9800',
            'icon': 'mdi.alert',
        },
        'info': {
            'bg': 'rgba(96, 205, 255, 0.15)',
            'border': 'rgba(96, 205, 255, 0.4)',
            'icon_color': '#5caee8',
            'icon': 'mdi.information',
        },
        'success': {
            'bg': 'rgba(76, 175, 80, 0.15)',
            'border': 'rgba(76, 175, 80, 0.4)',
            'icon_color': '#4CAF50',
            'icon': 'mdi.check-circle',
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_animation()
        self._theme_refresh = ThemeRefreshController(self, self._refresh_theme)
        self._refresh_theme()
        self.hide()  # Скрыт по умолчанию

    def _setup_ui(self):
        """Настройка UI элементов"""
        self.setFixedHeight(48)

        # Основной layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 12, 8)
        layout.setSpacing(12)

        # Иконка
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.icon_label)

        # Текст сообщения
        self.message_label = QLabel()
        self.message_label.setProperty("tone", "primary")
        self.message_label.setStyleSheet(
            "font-size: 13px; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif; background: transparent; border: none;"
        )
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

        # Кнопка закрытия
        self.close_btn = QPushButton()
        self.close_btn.setIconSize(QSize(16, 16))
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide_animated)
        layout.addWidget(self.close_btn)

        # Opacity effect для анимации
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity_effect)

    def _refresh_theme(self) -> None:
        try:
            tokens = get_theme_tokens()
            icon_color = "#111111" if tokens.is_light else "#f5f5f5"
            hover_bg = tokens.surface_bg_hover
            pressed_bg = tokens.surface_bg_pressed
        except Exception:
            icon_color = "#f5f5f5"
            hover_bg = "rgba(245, 245, 245, 0.14)"
            pressed_bg = "rgba(245, 245, 245, 0.20)"

        self.close_btn.setIcon(qta.icon("mdi.close", color=icon_color))
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton:pressed {{
                background-color: {pressed_bg};
            }}
        """)

    def _setup_animation(self):
        """Настройка анимаций"""
        # Таймер автоскрытия
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.hide_animated)

        # Анимация появления (fade in)
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(200)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Анимация исчезновения (fade out)
        self.fade_out_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(200)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_out_animation.finished.connect(self._on_fade_out_finished)

    def _apply_style(self, notification_type: str):
        """Применяет стиль в зависимости от типа уведомления"""
        style = dict(self.STYLES.get(notification_type, self.STYLES['info']))
        try:
            tokens = get_theme_tokens()
            # For "info", track the active accent instead of the legacy fixed blue.
            if notification_type == "info":
                style["bg"] = f"rgba({tokens.accent_rgb_str}, 0.15)"
                style["border"] = f"rgba({tokens.accent_rgb_str}, 0.40)"
                style["icon_color"] = tokens.accent_hex
        except Exception:
            pass

        # Стиль контейнера
        self.setStyleSheet(f"""
            NotificationBanner {{
                background-color: {style['bg']};
                border: 1px solid {style['border']};
                border-radius: 8px;
            }}
        """)

        # Иконка
        icon = qta.icon(style['icon'], color=style['icon_color'])
        self.icon_label.setPixmap(icon.pixmap(24, 24))

    def show_message(self, message: str, notification_type: str = 'info', auto_hide_ms: int = 6000):
        """
        Показывает уведомление с анимацией.

        Args:
            message: Текст сообщения
            notification_type: Тип уведомления ('error', 'warning', 'info', 'success')
            auto_hide_ms: Время до автоматического скрытия (мс). 0 = не скрывать автоматически
        """
        # Останавливаем текущие анимации
        self.fade_in_animation.stop()
        self.fade_out_animation.stop()
        self.auto_hide_timer.stop()

        # Применяем стиль
        self._apply_style(notification_type)

        # Устанавливаем текст
        self.message_label.setText(message)

        # Показываем с анимацией
        self.opacity_effect.setOpacity(0.0)
        self.show()
        self.fade_in_animation.start()

        # Запускаем таймер автоскрытия
        if auto_hide_ms > 0:
            self.auto_hide_timer.start(auto_hide_ms)

    def show_error(self, message: str, auto_hide_ms: int = 6000):
        """Показывает ошибку (красный)"""
        self.show_message(message, 'error', auto_hide_ms)

    def show_warning(self, message: str, auto_hide_ms: int = 6000):
        """Показывает предупреждение (оранжевый)"""
        self.show_message(message, 'warning', auto_hide_ms)

    def show_info(self, message: str, auto_hide_ms: int = 6000):
        """Показывает информацию (голубой)"""
        self.show_message(message, 'info', auto_hide_ms)

    def show_success(self, message: str, auto_hide_ms: int = 6000):
        """Показывает успех (зеленый)"""
        self.show_message(message, 'success', auto_hide_ms)

    def hide_animated(self):
        """Скрывает уведомление с анимацией"""
        self.auto_hide_timer.stop()
        self.fade_in_animation.stop()
        self.fade_out_animation.start()

    def _on_fade_out_finished(self):
        """Callback после завершения анимации исчезновения"""
        self.hide()
        self.opacity_effect.setOpacity(1.0)  # Reset для следующего показа
