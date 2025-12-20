# ui/fluent_icons.py
"""
Объёмные иконки в стиле Fluent Design / Windows 11
с градиентами и тенями
"""
from PyQt6.QtCore import Qt, QSize, QRect, QPointF
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QLinearGradient, 
    QPen, QBrush, QPainterPath, QRadialGradient
)
import qtawesome as qta


class FluentIcon:
    """Создаёт объёмные иконки с градиентами в стиле Windows 11"""
    
    # Палитра цветов для иконок (градиенты)
    ICON_COLORS = {
        # Синие оттенки
        'blue': ('#60cdff', '#0078d4'),
        'light_blue': ('#99d9ea', '#60cdff'),
        
        # Зелёные оттенки
        'green': ('#6ccb5f', '#107c10'),
        'teal': ('#00b7c3', '#038387'),
        
        # Жёлтые/оранжевые
        'yellow': ('#fff100', '#ff8c00'),
        'orange': ('#ff8c00', '#d83b01'),
        'amber': ('#ffb900', '#ff8c00'),
        
        # Красные/розовые
        'red': ('#ff6b6b', '#d13438'),
        'pink': ('#ea4aaa', '#c239b3'),
        'magenta': ('#e3008c', '#b4009e'),
        
        # Фиолетовые
        'purple': ('#b4a0ff', '#8764b8'),
        'violet': ('#886ce4', '#5c2d91'),
        
        # Нейтральные
        'gray': ('#8a8a8a', '#4a4a4a'),
        'dark': ('#5c5c5c', '#2d2d2d'),
        
        # Специальные
        'gold': ('#ffc107', '#d4a106'),
        'silver': ('#c0c0c0', '#808080'),
    }
    
    # Маппинг иконок на цвета
    ICON_COLOR_MAP = {
        # Управление
        'fa5s.play': 'green',
        'fa5s.play-circle': 'green',
        'fa5s.stop': 'gray',
        'fa5s.pause': 'gray',
        
        # Навигация
        'fa5s.home': 'blue',
        'fa5s.cog': 'gray',
        'fa5s.cogs': 'gray',
        
        # Статус
        'fa5s.check': 'green',
        'fa5s.check-circle': 'green',
        'fa5s.times': 'red',
        'fa5s.times-circle': 'red',
        'fa5s.exclamation-triangle': 'amber',
        'fa5s.info-circle': 'blue',
        
        # Сеть
        'fa5s.wifi': 'teal',
        'fa5s.network-wired': 'teal',
        'fa5s.globe': 'blue',
        'fa5s.shield-alt': 'blue',
        
        # Файлы
        'fa5s.folder': 'amber',
        'fa5s.folder-open': 'amber',
        'fa5s.file': 'gray',
        'fa5s.file-pdf': 'red',
        
        # Специальные
        'fa5s.star': 'gold',
        'fa5s.rocket': 'orange',
        'fa5s.palette': 'purple',
        'fa5s.question-circle': 'purple',
        'fa5s.sync-alt': 'blue',
        'fa5s.arrow-right': 'blue',
        
        # Замок
        'fa5s.lock': 'red',
        'fa5s.unlock': 'green',
    }
    
    @classmethod
    def get_gradient_colors(cls, icon_name: str) -> tuple:
        """Возвращает цвета градиента для иконки"""
        color_key = cls.ICON_COLOR_MAP.get(icon_name, 'blue')
        return cls.ICON_COLORS.get(color_key, cls.ICON_COLORS['blue'])
    
    @classmethod
    def create_icon(cls, icon_name: str, size: int = 24) -> QIcon:
        """
        Создаёт объёмную иконку с градиентом
        
        Args:
            icon_name: Имя иконки FontAwesome
            size: Размер иконки
        """
        # Получаем цвета градиента
        top_color, bottom_color = cls.get_gradient_colors(icon_name)
        
        # Создаём pixmap
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Создаём градиент сверху вниз
        gradient = QLinearGradient(0, 0, 0, size)
        gradient.setColorAt(0.0, QColor(top_color))
        gradient.setColorAt(1.0, QColor(bottom_color))
        
        # Получаем базовую иконку
        base_icon = qta.icon(icon_name, color='white')
        base_pixmap = base_icon.pixmap(QSize(size, size))
        
        # Рисуем иконку с градиентом используя маску
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawPixmap(0, 0, base_pixmap)
        
        # Применяем градиент как цвет
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), gradient)
        
        # Добавляем лёгкое свечение сверху для объёма
        highlight_gradient = QLinearGradient(0, 0, 0, size // 3)
        highlight_gradient.setColorAt(0.0, QColor(255, 255, 255, 60))
        highlight_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        painter.fillRect(0, 0, size, size // 3, highlight_gradient)
        
        painter.end()
        
        return QIcon(pixmap)
    
    @classmethod
    def create_pixmap(cls, icon_name: str, size: int = 24) -> QPixmap:
        """Создаёт объёмную иконку как QPixmap"""
        return cls.create_icon(icon_name, size).pixmap(QSize(size, size))
    
    @classmethod
    def create_nav_icon(cls, icon_name: str, size: int = 18, selected: bool = False) -> QIcon:
        """
        Создаёт иконку для навигации
        
        Args:
            icon_name: Имя иконки
            size: Размер
            selected: Выбран ли элемент
        """
        if selected:
            # Для выбранного - используем акцентный цвет
            return cls.create_icon(icon_name, size)
        else:
            # Для невыбранного - полупрозрачный белый
            return qta.icon(icon_name, color='rgba(255, 255, 255, 0.8)')
    
    @classmethod
    def create_status_icon(cls, status: str, size: int = 16) -> QPixmap:
        """
        Создаёт иконку статуса
        
        Args:
            status: 'running', 'stopped', 'warning', 'neutral'
            size: Размер
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Цвета для разных статусов
        colors = {
            'running': ('#6ccb5f', '#4caf50'),
            'stopped': ('#ff6b6b', '#f44336'),
            'warning': ('#ffc107', '#ff9800'),
            'neutral': ('#8a8a8a', '#606060'),
        }
        
        top_color, bottom_color = colors.get(status, colors['neutral'])
        
        # Градиент
        gradient = QRadialGradient(size / 2, size / 3, size / 1.5)
        gradient.setColorAt(0.0, QColor(top_color))
        gradient.setColorAt(1.0, QColor(bottom_color))
        
        # Рисуем круг
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        margin = size // 8
        painter.drawEllipse(margin, margin, size - margin * 2, size - margin * 2)
        
        # Блик
        highlight = QRadialGradient(size / 3, size / 3, size / 3)
        highlight.setColorAt(0.0, QColor(255, 255, 255, 100))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight))
        painter.drawEllipse(margin, margin, size - margin * 2, size - margin * 2)
        
        painter.end()
        
        return pixmap


# Удобные функции для использования
def fluent_icon(icon_name: str, size: int = 24) -> QIcon:
    """Создаёт Fluent иконку"""
    return FluentIcon.create_icon(icon_name, size)


def fluent_pixmap(icon_name: str, size: int = 24) -> QPixmap:
    """Создаёт Fluent иконку как pixmap"""
    return FluentIcon.create_pixmap(icon_name, size)


def status_pixmap(status: str, size: int = 16) -> QPixmap:
    """Создаёт иконку статуса"""
    return FluentIcon.create_status_icon(status, size)


# Безопасные префиксы иконок
VALID_ICON_PREFIXES = ('fa5s.', 'fa5b.', 'fa.', 'mdi.', 'ei.', 'ri.')


def safe_qta_icon(icon_name: str, color: str = '#ffffff', fallback: str = 'fa5s.circle') -> QIcon:
    """
    Безопасно создаёт иконку qtawesome с проверкой префикса.
    
    Args:
        icon_name: Имя иконки (например 'fa5s.star')
        color: Цвет иконки
        fallback: Fallback иконка если основная невалидна
        
    Returns:
        QIcon объект
    """
    if not icon_name or not isinstance(icon_name, str):
        icon_name = fallback
    
    # Проверяем префикс
    if not icon_name.startswith(VALID_ICON_PREFIXES):
        from log import log
        log(f"Неизвестный префикс иконки: {icon_name}, используется fallback", "⚠ WARNING")
        icon_name = fallback
    
    try:
        return qta.icon(icon_name, color=color)
    except Exception as e:
        from log import log
        log(f"Ошибка создания иконки {icon_name}: {e}", "⚠ WARNING")
        try:
            return qta.icon(fallback, color=color)
        except:
            return QIcon()
