# strategy_menu/hover_tooltip.py
"""
Красивый hover tooltip в стиле Windows 11
С анимацией, полупрозрачным фоном
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QGraphicsDropShadowEffect, QApplication)
from PyQt6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve, 
                          QPoint, QRectF, pyqtProperty)
from PyQt6.QtGui import (QColor, QPainter, QPainterPath, QBrush, 
                         QPen, QLinearGradient, QCursor)

from ui.theme import get_theme_tokens
from ui.theme_refresh import ThemeRefreshController


class FloatingSpinner(QWidget):
    """Плавающий спиннер справа от tooltip"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Tooltip/spinner must never block clicks/hover on the underlying UI.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(32, 32)
        
        self._angle = 0
        self._color = QColor("#60cdff")
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        
    def _rotate(self):
        self._angle = (self._angle + 10) % 360
        self.update()
        
    def paintEvent(self, event):
        tokens = get_theme_tokens()
        self._color = QColor(tokens.accent_hex)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Фон
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 8, 8)
        if tokens.is_light:
            painter.fillPath(path, QBrush(QColor(255, 255, 255, 240)))
            painter.setPen(QPen(QColor(0, 0, 0, 26), 1))
        else:
            painter.fillPath(path, QBrush(QColor(40, 40, 40, 230)))
            painter.setPen(QPen(QColor(255, 255, 255, 15), 1))
        painter.drawPath(path)
        
        # Спиннер
        cx, cy = self.width() / 2, self.height() / 2
        radius = 8
        
        pen = QPen(self._color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.drawArc(rect, self._angle * 16, 270 * 16)
        
    def start(self):
        self._timer.start(16)
        
    def stop(self):
        self._timer.stop()


class StrategyHoverTooltip(QWidget):
    """Красивый hover tooltip в стиле Windows 11"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # Tooltip must not block clicks/hover on the app UI.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self._opacity = 0.0
        self._spinner = None
        
        self._fade_animation = QPropertyAnimation(self, b"opacity_value")
        self._fade_animation.setDuration(150)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self._init_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme_styles)
        
    def _init_ui(self):
        """Инициализация интерфейса"""
        self.setFixedWidth(260)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.container = QWidget()
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(14, 12, 14, 12)
        container_layout.setSpacing(8)
        
        # Заголовок
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        container_layout.addWidget(self.title_label)
        
        # Описание
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        container_layout.addWidget(self.description_label)
        
        # Разделитель
        self.separator = QWidget()
        self.separator.setFixedHeight(1)
        container_layout.addWidget(self.separator)
        
        # Информация
        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(4)
        container_layout.addLayout(self.info_layout)
        
        # Подсказка
        self.hint_label = QLabel("ПКМ — подробнее")
        container_layout.addWidget(self.hint_label)
        
        main_layout.addWidget(self.container)
        
        # Тень
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        tokens = get_theme_tokens()

        self.title_label.setStyleSheet(
            f"color: {tokens.fg}; font-size: 12px; font-weight: 600;"
        )
        self.description_label.setStyleSheet(
            f"color: {tokens.fg_muted}; font-size: 11px;"
        )
        self.hint_label.setStyleSheet(
            f"color: {tokens.fg_faint}; font-size: 10px; margin-top: 4px;"
        )

        separator_color = "rgba(0, 0, 0, 0.10)" if tokens.is_light else "rgba(255, 255, 255, 0.08)"
        self.separator.setStyleSheet(f"background: {separator_color};")

        effect = self.container.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            effect.setColor(QColor(0, 0, 0, 54 if tokens.is_light else 78))
        
    def _create_info_row(self, label_text, value_text, color="#60cdff"):
        """Создает строку информации"""
        tokens = get_theme_tokens()
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        
        name = QLabel(label_text)
        name.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 10px;")
        row_layout.addWidget(name)
        
        row_layout.addStretch()
        
        value = QLabel(value_text)
        value.setStyleSheet(f"color: {color}; font-size: 10px;")
        row_layout.addWidget(value)
        
        return row
    
    def set_data(self, strategy_info, strategy_id):
        """Устанавливает данные"""
        self._apply_theme_styles()
        name = strategy_info.get('name') or strategy_id
        self.title_label.setText(name)
        
        description = strategy_info.get('description') or ''
        if len(description) > 100:
            description = description[:97] + "..."
        
        if description:
            self.description_label.setText(description)
            self.description_label.show()
        else:
            self.description_label.hide()
        
        # Очищаем
        while self.info_layout.count():
            item = self.info_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Добавляем инфо
        author = strategy_info.get('author') or None
        if author and author.lower() != 'unknown':
            self.info_layout.addWidget(self._create_info_row("Автор", author, "#a78bfa"))
        
        version = strategy_info.get('version') or '1.0'
        self.info_layout.addWidget(self._create_info_row("Версия", version, "#4ade80"))
        
        date = strategy_info.get('date') or None
        if date:
            self.info_layout.addWidget(self._create_info_row("Дата", date, "#fbbf24"))
        
        provider = strategy_info.get('provider') or 'universal'
        providers = {'universal': 'All', 'rostelecom': 'РТК', 'mts': 'МТС', 
                    'megafon': 'МФ', 'beeline': 'Билайн'}
        self.info_layout.addWidget(self._create_info_row("Провайдер", providers.get(provider, provider), "#60cdff"))
        
        self.adjustSize()
    
    def show_at(self, pos: QPoint, with_spinner=True):
        """Показывает tooltip"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            if pos.x() + self.width() > screen_rect.right():
                pos.setX(screen_rect.right() - self.width() - 10)
            if pos.y() + self.height() + 50 > screen_rect.bottom():
                pos.setY(pos.y() - self.height() - 20)
        
        self.move(pos)
        
        # Показываем спиннер справа
        if with_spinner:
            if not self._spinner:
                self._spinner = FloatingSpinner()
            spinner_pos = QPoint(pos.x() + self.width() + 6, pos.y())
            self._spinner.move(spinner_pos)
            self._spinner.start()
            self._spinner.show()
            
            # Скрываем спиннер через 200мс
            QTimer.singleShot(200, self._hide_spinner)
        
        self._opacity = 0.0
        self.show()
        
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()
    
    def _hide_spinner(self):
        """Скрывает спиннер"""
        if self._spinner:
            self._spinner.stop()
            self._spinner.hide()
    
    def hide_animated(self):
        """Скрывает с анимацией"""
        self._hide_spinner()
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.finished.connect(self._on_hide_finished)
        self._fade_animation.start()
    
    def _on_hide_finished(self):
        try:
            self._fade_animation.finished.disconnect(self._on_hide_finished)
        except:
            pass
        self.hide()
    
    @pyqtProperty(float)
    def opacity_value(self):
        return self._opacity
    
    @opacity_value.setter
    def opacity_value(self, value):
        self._opacity = value
        self.setWindowOpacity(value)
    
    def paintEvent(self, event):
        """Рисуем Fluent фон"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        radius = 10
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        
        tokens = get_theme_tokens()
        gradient = QLinearGradient(0, 0, 0, rect.height())
        if tokens.is_light:
            gradient.setColorAt(0, QColor(255, 255, 255, 248))
            gradient.setColorAt(1, QColor(244, 247, 252, 242))
            border_color = QColor(0, 0, 0, 24)
        else:
            gradient.setColorAt(0, QColor(48, 48, 48, 250))
            gradient.setColorAt(1, QColor(32, 32, 32, 250))
            border_color = QColor(255, 255, 255, 12)
        painter.fillPath(path, QBrush(gradient))

        painter.setPen(QPen(border_color, 1))
        painter.drawPath(path)

class TooltipManager:
    """Менеджер hover tooltip"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tooltip = None
            cls._instance._hide_timer = QTimer()
            cls._instance._hide_timer.setSingleShot(True)
            cls._instance._hide_timer.timeout.connect(cls._instance._hide_tooltip)
            cls._instance._show_timer = QTimer()
            cls._instance._show_timer.setSingleShot(True)
            cls._instance._pending_data = None
        return cls._instance
    
    def show_tooltip(
        self,
        pos: QPoint,
        strategy_info: dict,
        strategy_id: str,
        delay: int = 400,
        source_widget: QWidget | None = None,
    ):
        """Показывает tooltip с задержкой"""
        # Если открыто интерактивное окно предпросмотра по ПКМ, hover-tooltip не нужен.
        try:
            app = QApplication.instance()
            if app and bool(app.property("zapretgui_args_preview_open")):
                self.hide_immediately()
                return
        except Exception:
            pass

        self._hide_timer.stop()
        self._pending_data = (pos, strategy_info, strategy_id, source_widget)
        
        try:
            self._show_timer.timeout.disconnect()
        except:
            pass
        self._show_timer.timeout.connect(self._do_show)
        self._show_timer.start(delay)
    
    def _do_show(self):
        """Выполняет показ"""
        if not self._pending_data:
            return
        
        pos, strategy_info, strategy_id, source_widget = self._pending_data

        # Guard against delayed show after the source widget/page is hidden.
        try:
            if source_widget is not None:
                if (not source_widget.isVisible()) or (not source_widget.window().isVisible()):
                    self._pending_data = None
                    return
        except Exception:
            pass

        # Show only when the cursor is actually inside the source widget (or its children).
        try:
            if source_widget is not None:
                w = QApplication.widgetAt(QCursor.pos())
                if (w is None) or (w is not source_widget and (not source_widget.isAncestorOf(w))):
                    self._pending_data = None
                    return
        except Exception:
            pass
        
        if not self._tooltip:
            self._tooltip = StrategyHoverTooltip()
        
        self._tooltip.set_data(strategy_info, strategy_id)
        self._tooltip.show_at(pos)
        self._pending_data = None
    
    def hide_tooltip(self, delay: int = 150):
        """Скрывает с задержкой"""
        self._show_timer.stop()
        self._pending_data = None
        
        if self._tooltip and self._tooltip.isVisible():
            self._hide_timer.start(delay)
    
    def _hide_tooltip(self):
        if self._tooltip:
            self._tooltip.hide_animated()
    
    def hide_immediately(self):
        """Немедленно скрывает"""
        self._show_timer.stop()
        self._hide_timer.stop()
        self._pending_data = None
        
        if self._tooltip:
            self._tooltip._hide_spinner()
            self._tooltip.hide()


tooltip_manager = TooltipManager()
