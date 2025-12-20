from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QVBoxLayout, QLabel,
                            QRadioButton, QWidget, QListWidgetItem, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush

from .constants import LABEL_TEXTS, LABEL_COLORS

# Константы стилей - оптимизированы для минимизации setStyleSheet вызовов
_STYLE_SELECTED = """
    CompactStrategyItem {
        background: rgba(96, 205, 255, 0.15);
        border: 1px solid rgba(96, 205, 255, 0.5);
        border-radius: 4px;
    }
"""
_STYLE_NORMAL = """
    CompactStrategyItem {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 4px;
    }
    CompactStrategyItem:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(255, 255, 255, 0.12);
    }
"""

# Стили для рейтинга стратегий (рабочая/нерабочая)
_STYLE_RATING_WORKING = """
    CompactStrategyItem {
        background: rgba(74, 222, 128, 0.15);
        border: 1px solid rgba(74, 222, 128, 0.3);
        border-radius: 4px;
    }
    CompactStrategyItem:hover {
        background: rgba(74, 222, 128, 0.2);
        border-color: rgba(74, 222, 128, 0.5);
    }
"""
_STYLE_RATING_BROKEN = """
    CompactStrategyItem {
        background: rgba(248, 113, 113, 0.15);
        border: 1px solid rgba(248, 113, 113, 0.3);
        border-radius: 4px;
    }
    CompactStrategyItem:hover {
        background: rgba(248, 113, 113, 0.2);
        border-color: rgba(248, 113, 113, 0.5);
    }
"""

# Константы стилей для текста (используются как есть, без пересоздания строк)
_STYLE_NAME = "color: rgba(255, 255, 255, 0.9); font-size: 11px; font-weight: 500;"
_STYLE_DESC = "color: rgba(255, 255, 255, 0.4); font-size: 10px;"

# Кэш стилей для меток (оптимизация - избегаем создания строк)
_LABEL_STYLE_CACHE = {}


def _get_label_style(color: str) -> str:
    """Получает кэшированный стиль для метки"""
    if color not in _LABEL_STYLE_CACHE:
        _LABEL_STYLE_CACHE[color] = f"background:{color};color:#fff;font-size:9px;font-weight:600;padding:3px 8px;border-radius:4px;"
    return _LABEL_STYLE_CACHE[color]


class CompactStrategyItem(QFrame):
    """Компактный виджет стратегии - без кружка, только подсветка"""

    clicked = pyqtSignal(str)

    # Статические стили для дочерних элементов (не требуют setStyleSheet)
    _name_style_applied = False
    _desc_style_applied = False

    def __init__(self, strategy_id, strategy_data, parent=None):
        super().__init__(parent)
        self.strategy_id = strategy_id
        self.strategy_data = strategy_data
        self.is_selected = False
        self._current_style = None  # Кэш текущего стиля

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._apply_style(False)
        self._init_ui()
        self._setup_tooltip()

    def _get_rating_style(self):
        """Возвращает стиль на основе рейтинга стратегии"""
        from strategy_menu import get_strategy_rating
        # Для CompactStrategyItem category_key не доступен, используем legacy формат
        rating = get_strategy_rating(self.strategy_id, category_key=None)
        if rating == 'working':
            return _STYLE_RATING_WORKING
        elif rating == 'broken':
            return _STYLE_RATING_BROKEN
        return None

    def _apply_style(self, selected):
        """Применяет стиль (с кэшированием для избежания лишних вызовов)"""
        if selected:
            new_style = _STYLE_SELECTED
        else:
            # Проверяем рейтинг стратегии
            rating_style = self._get_rating_style()
            new_style = rating_style if rating_style else _STYLE_NORMAL
        if self._current_style != new_style:
            self._current_style = new_style
            self.setStyleSheet(new_style)

    def _setup_tooltip(self):
        """Tooltip"""
        name = self.strategy_data.get('name', self.strategy_id)
        tip = f"<b>{name}</b><br><i style='color:#888'>ПКМ - показать аргументы</i>"
        self.setToolTip(tip)

    def _init_ui(self):
        """UI - компактный без кружка"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 4, 10, 4)
        main_layout.setSpacing(6)
        self.main_layout = main_layout

        # Скрытая радиокнопка для QButtonGroup
        self.radio = QRadioButton()
        self.radio.hide()
        self.radio.toggled.connect(self._on_toggled)

        # Контейнер для текста (вертикальный)
        text_container = QVBoxLayout()
        text_container.setContentsMargins(0, 0, 0, 0)
        text_container.setSpacing(0)

        # Верхняя строка: название + метка
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        name = self.strategy_data.get('name', self.strategy_id)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(_STYLE_NAME)
        top_row.addWidget(self.name_label)

        # Метка (если есть)
        label = self.strategy_data.get('label')
        if label and label in LABEL_TEXTS:
            tag = QLabel(LABEL_TEXTS[label])
            color = LABEL_COLORS[label]
            tag.setStyleSheet(_get_label_style(color))
            top_row.addWidget(tag)

        top_row.addStretch()
        text_container.addLayout(top_row)

        # Нижняя строка: описание
        desc = self.strategy_data.get('description', '')
        if desc:
            self.desc_label = QLabel(desc)
            self.desc_label.setWordWrap(True)
            self.desc_label.setStyleSheet(_STYLE_DESC)
            text_container.addWidget(self.desc_label)

        main_layout.addLayout(text_container, 1)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.radio.setChecked(True)
        super().mousePressEvent(event)
    
    def _show_context_menu(self, pos):
        """Показывает окно информации о стратегии по ПКМ"""
        from .args_preview_dialog import preview_manager
        # Для CompactStrategyItem нет category_key, передаем None
        preview_manager.show_preview(self, self.strategy_id, self.strategy_data, category_key=None)
    
    def _on_toggled(self, checked):
        self.is_selected = checked
        self._apply_style(checked)
        if checked:
            self.clicked.emit(self.strategy_id)
    
    def set_checked(self, checked):
        self.radio.setChecked(checked)
    
    def refresh_rating(self):
        """Обновляет стиль на основе рейтинга"""
        self._current_style = None  # Сбрасываем кэш
        self._apply_style(self.is_selected)

    def _update_rating_style(self):
        """Обновляет стиль рейтинга"""
        self.refresh_rating()


class ProviderHeaderItem(QListWidgetItem):
    """Специальный элемент для заголовка группы провайдера"""
    def __init__(self, provider_name):
        super().__init__(f"{provider_name}")
        font = self.font()
        font.setBold(True)
        self.setFont(font)
        self.setBackground(QBrush(QColor(240, 240, 240)))
        self.setFlags(Qt.ItemFlag.NoItemFlags)


class StrategyItem(QWidget):
    """Виджет для отображения элемента стратегии с цветной меткой"""
    def __init__(self, display_name, label=None, strategy_number=None, 
                 version_status=None, parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # Основной текст
        text = ""
        if strategy_number is not None:
            text = f"{strategy_number}. "
        text += display_name
        
        self.main_label = QLabel(text)
        self.main_label.setWordWrap(False)
        self.main_label.setMinimumHeight(20)
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.main_label.setStyleSheet("font-size: 10pt; margin: 0; padding: 0;")
        layout.addWidget(self.main_label)
        
        # Статус версии
        if version_status and version_status != 'current':
            version_text = ""
            version_color = ""
            
            if version_status == 'outdated':
                version_text = "ОБНОВИТЬ"
                version_color = "#FF6600"
            elif version_status == 'not_downloaded':
                version_text = "НЕ СКАЧАНА"
                version_color = "#CC0000"
            elif version_status == 'unknown':
                version_text = "?"
                version_color = "#888888"
                
            if version_text:
                self.version_label = QLabel(version_text)
                self.version_label.setStyleSheet(
                    f"color: {version_color}; font-weight: bold; font-size: 8pt; "
                    f"margin: 0; padding: 2px 4px; "
                    f"border: 1px solid {version_color}; border-radius: 3px;"
                )
                self.version_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
                self.version_label.setMinimumHeight(16)
                layout.addWidget(self.version_label)
        
        # Метка
        if label and label in LABEL_TEXTS:
            self.tag_label = QLabel(LABEL_TEXTS[label])
            self.tag_label.setStyleSheet(
                f"color: {LABEL_COLORS[label]}; font-weight: bold; font-size: 9pt; "
                f"margin: 0; padding: 0;"
            )
            self.tag_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            self.tag_label.setMinimumHeight(20)
            layout.addWidget(self.tag_label)
            
        layout.addStretch()
        self.setMinimumHeight(30)
