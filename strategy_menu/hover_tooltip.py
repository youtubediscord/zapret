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
                         QPen, QLinearGradient)


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
        self.setFixedSize(32, 32)
        
        self._angle = 0
        self._color = QColor("#60cdff")
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        
    def _rotate(self):
        self._angle = (self._angle + 10) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Фон
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 8, 8)
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
        
        self._opacity = 0.0
        self._spinner = None
        
        self._fade_animation = QPropertyAnimation(self, b"opacity_value")
        self._fade_animation.setDuration(150)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self._init_ui()
        
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
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        container_layout.addWidget(self.title_label)
        
        # Описание
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 11px;
            }
        """)
        container_layout.addWidget(self.description_label)
        
        # Разделитель
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        container_layout.addWidget(separator)
        
        # Информация
        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(4)
        container_layout.addLayout(self.info_layout)
        
        # Подсказка
        hint = QLabel("ПКМ — подробнее")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.3); font-size: 10px; margin-top: 4px;")
        container_layout.addWidget(hint)
        
        main_layout.addWidget(self.container)
        
        # Тень
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)
        
    def _create_info_row(self, label_text, value_text, color="#60cdff"):
        """Создает строку информации"""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        
        name = QLabel(label_text)
        name.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 10px;")
        row_layout.addWidget(name)
        
        row_layout.addStretch()
        
        value = QLabel(value_text)
        value.setStyleSheet(f"color: {color}; font-size: 10px;")
        row_layout.addWidget(value)
        
        return row
    
    def set_data(self, strategy_info, strategy_id):
        """Устанавливает данные"""
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
        
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(48, 48, 48, 250))
        gradient.setColorAt(1, QColor(32, 32, 32, 250))
        painter.fillPath(path, QBrush(gradient))
        
        painter.setPen(QPen(QColor(255, 255, 255, 12), 1))
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
    
    def show_tooltip(self, pos: QPoint, strategy_info: dict, strategy_id: str, delay: int = 400):
        """Показывает tooltip с задержкой"""
        self._hide_timer.stop()
        self._pending_data = (pos, strategy_info, strategy_id)
        
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
        
        pos, strategy_info, strategy_id = self._pending_data
        
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
