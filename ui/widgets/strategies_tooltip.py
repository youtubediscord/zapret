# ui/widgets/strategies_tooltip.py
"""
Красивый hover tooltip для списка активных стратегий.
Следует за мышкой, с Font Awesome иконками и анимацией.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QGraphicsDropShadowEffect, QApplication)
from PyQt6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve, 
                          QPoint, QRectF, pyqtProperty, QEvent)
from PyQt6.QtGui import (QColor, QPainter, QPainterPath, QBrush, 
                         QPen, QLinearGradient, QCursor, QPixmap)
import qtawesome as qta

from log import log


class StrategiesListTooltip(QWidget):
    """Красивый tooltip со списком активных стратегий"""
    
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
        self._strategies = []
        self._follow_mouse = False
        self._mouse_offset = QPoint(15, 15)
        
        # Анимация появления
        self._fade_animation = QPropertyAnimation(self, b"opacity_value")
        self._fade_animation.setDuration(150)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Таймер для следования за мышкой
        self._mouse_timer = QTimer(self)
        self._mouse_timer.timeout.connect(self._follow_cursor)
        
        self._init_ui()
        
    def _init_ui(self):
        """Инициализация интерфейса"""
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.container = QWidget()
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(6)
        
        # Заголовок
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)
        
        header_icon = QLabel()
        header_icon.setPixmap(qta.icon('fa5s.list-ul', color='#60cdff').pixmap(14, 14))
        header_layout.addWidget(header_icon)
        
        self.title_label = QLabel("Все активные стратегии")
        self.title_label.setStyleSheet("""
            QLabel {
                color: #60cdff;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        container_layout.addLayout(header_layout)
        
        # Разделитель
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: rgba(255, 255, 255, 0.1);")
        container_layout.addWidget(separator)
        
        # Контейнер для списка стратегий
        self.strategies_layout = QVBoxLayout()
        self.strategies_layout.setSpacing(4)
        self.strategies_layout.setContentsMargins(0, 4, 0, 0)
        container_layout.addLayout(self.strategies_layout)
        
        main_layout.addWidget(self.container)
        
        # Тень
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)
    
    def _create_strategy_row(self, index: int, icon_name: str, icon_color: str, 
                             category_name: str, strategy_name: str) -> QWidget:
        """Создает строку стратегии с иконкой"""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)
        
        # Номер
        num_label = QLabel(f"{index}.")
        num_label.setFixedWidth(18)
        num_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 10px;")
        row_layout.addWidget(num_label)
        
        # Иконка категории (Font Awesome)
        icon_label = QLabel()
        try:
            pixmap = qta.icon(icon_name, color=icon_color).pixmap(14, 14)
            icon_label.setPixmap(pixmap)
        except:
            # Fallback на простую иконку
            pixmap = qta.icon('fa5s.globe', color='#60cdff').pixmap(14, 14)
            icon_label.setPixmap(pixmap)
        icon_label.setFixedSize(16, 16)
        row_layout.addWidget(icon_label)
        
        # Название категории
        cat_label = QLabel(category_name)
        cat_label.setStyleSheet(f"color: {icon_color}; font-size: 10px; font-weight: 500;")
        cat_label.setFixedWidth(70)
        row_layout.addWidget(cat_label)
        
        # Название стратегии
        strat_label = QLabel(strategy_name)
        strat_label.setStyleSheet("color: rgba(255, 255, 255, 0.85); font-size: 10px;")
        strat_label.setWordWrap(False)
        row_layout.addWidget(strat_label, 1)
        
        return row
    
    def set_strategies(self, strategies: list):
        """
        Устанавливает список стратегий для отображения.

        Args:
            strategies: список кортежей (icon_name, icon_color, category_name, strategy_name)
        """
        self._strategies = strategies

        # Очищаем старые строки - важно отсоединить от родителя сразу
        while self.strategies_layout.count():
            item = self.strategies_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)  # Немедленно отсоединяем от layout
                widget.deleteLater()

        # Добавляем новые
        for i, (icon_name, icon_color, cat_name, strat_name) in enumerate(strategies, 1):
            row = self._create_strategy_row(i, icon_name, icon_color, cat_name, strat_name)
            self.strategies_layout.addWidget(row)

        # Обновляем заголовок
        self.title_label.setText(f"Все активные стратегии ({len(strategies)})")

        # Пересчитываем размер
        self.strategies_layout.invalidate()
        self.adjustSize()
    
    def show_at_cursor(self, follow: bool = True):
        """Показывает tooltip у курсора"""
        self._follow_mouse = follow
        
        # Начальная позиция
        cursor_pos = QCursor.pos()
        self._position_near_cursor(cursor_pos)
        
        # Запускаем следование за мышкой
        if follow:
            self._mouse_timer.start(16)  # ~60 FPS
        
        # Анимация появления
        self._opacity = 0.0
        self.show()
        
        self._fade_animation.stop()
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()
    
    def _follow_cursor(self):
        """Плавно следует за курсором"""
        if not self.isVisible():
            self._mouse_timer.stop()
            return
        
        cursor_pos = QCursor.pos()
        self._position_near_cursor(cursor_pos)
    
    def _position_near_cursor(self, cursor_pos: QPoint):
        """Позиционирует tooltip около курсора с учетом границ экрана"""
        target_pos = cursor_pos + self._mouse_offset
        
        # Проверяем границы экрана
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            
            # Справа
            if target_pos.x() + self.width() > screen_rect.right():
                target_pos.setX(cursor_pos.x() - self.width() - 10)
            
            # Снизу
            if target_pos.y() + self.height() > screen_rect.bottom():
                target_pos.setY(cursor_pos.y() - self.height() - 10)
            
            # Слева
            if target_pos.x() < screen_rect.left():
                target_pos.setX(screen_rect.left() + 5)
            
            # Сверху
            if target_pos.y() < screen_rect.top():
                target_pos.setY(screen_rect.top() + 5)
        
        self.move(target_pos)
    
    def hide_animated(self):
        """Скрывает с анимацией"""
        self._mouse_timer.stop()
        self._follow_mouse = False
        
        self._fade_animation.stop()
        self._fade_animation.setStartValue(self._opacity)
        self._fade_animation.setEndValue(0.0)
        
        try:
            self._fade_animation.finished.disconnect()
        except:
            pass
        self._fade_animation.finished.connect(self._on_hide_finished)
        self._fade_animation.start()
    
    def _on_hide_finished(self):
        try:
            self._fade_animation.finished.disconnect(self._on_hide_finished)
        except:
            pass
        self.hide()
    
    def hide_immediately(self):
        """Немедленно скрывает"""
        self._mouse_timer.stop()
        self._follow_mouse = False
        self._fade_animation.stop()
        self.hide()
    
    @pyqtProperty(float)
    def opacity_value(self):
        return self._opacity
    
    @opacity_value.setter
    def opacity_value(self, value):
        self._opacity = value
        self.setWindowOpacity(value)
    
    def paintEvent(self, event):
        """Рисуем Fluent фон с градиентом"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        radius = 10
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        
        # Градиентный фон
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(45, 45, 48, 252))
        gradient.setColorAt(1, QColor(30, 30, 32, 252))
        painter.fillPath(path, QBrush(gradient))
        
        # Тонкая рамка
        painter.setPen(QPen(QColor(255, 255, 255, 15), 1))
        painter.drawPath(path)


class StrategiesTooltipManager:
    """Менеджер для tooltip списка стратегий"""
    
    _instance = None
    _tooltip = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tooltip = None
            cls._instance._hide_timer = QTimer()
            cls._instance._hide_timer.setSingleShot(True)
            cls._instance._hide_timer.timeout.connect(cls._instance._do_hide)
        return cls._instance
    
    def show(self, strategies: list, follow: bool = True):
        """
        Показывает tooltip со списком стратегий.
        
        Args:
            strategies: список кортежей (icon_name, icon_color, category_name, strategy_name)
            follow: следовать за мышкой
        """
        self._hide_timer.stop()
        
        if not self._tooltip:
            self._tooltip = StrategiesListTooltip()
        
        self._tooltip.set_strategies(strategies)
        self._tooltip.show_at_cursor(follow)
    
    def hide(self, delay: int = 100):
        """Скрывает с задержкой"""
        if self._tooltip and self._tooltip.isVisible():
            self._hide_timer.start(delay)
    
    def _do_hide(self):
        if self._tooltip:
            self._tooltip.hide_animated()
    
    def hide_immediately(self):
        """Немедленно скрывает"""
        self._hide_timer.stop()
        if self._tooltip:
            self._tooltip.hide_immediately()


# Глобальный экземпляр менеджера
strategies_tooltip_manager = StrategiesTooltipManager()

