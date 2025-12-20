from PyQt6.QtWidgets import QToolButton
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QPoint

from .widgets import CompactStrategyItem


# Стили для избранных (константы для кэширования)
_STYLE_SELECTED = """
    FavoriteCompactStrategyItem {
        background: rgba(96, 205, 255, 0.15);
        border: 1px solid rgba(96, 205, 255, 0.5);
        border-radius: 4px;
    }
"""
_STYLE_FAVORITE = """
    FavoriteCompactStrategyItem {
        background: rgba(255, 215, 0, 0.08);
        border: 1px solid rgba(255, 215, 0, 0.25);
        border-radius: 4px;
    }
    FavoriteCompactStrategyItem:hover {
        background: rgba(255, 215, 0, 0.12);
        border-color: rgba(255, 215, 0, 0.4);
    }
"""
_STYLE_NORMAL = """
    FavoriteCompactStrategyItem {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 4px;
    }
    FavoriteCompactStrategyItem:hover {
        background: rgba(255, 255, 255, 0.06);
        border-color: rgba(255, 255, 255, 0.15);
    }
"""

# Стили для рейтинга стратегий (рабочая/нерабочая)
_STYLE_RATING_WORKING = """
    FavoriteCompactStrategyItem {
        background: rgba(74, 222, 128, 0.15);
        border: 1px solid rgba(74, 222, 128, 0.3);
        border-radius: 4px;
    }
    FavoriteCompactStrategyItem:hover {
        background: rgba(74, 222, 128, 0.2);
        border-color: rgba(74, 222, 128, 0.5);
    }
"""
_STYLE_RATING_BROKEN = """
    FavoriteCompactStrategyItem {
        background: rgba(248, 113, 113, 0.15);
        border: 1px solid rgba(248, 113, 113, 0.3);
        border-radius: 4px;
    }
    FavoriteCompactStrategyItem:hover {
        background: rgba(248, 113, 113, 0.2);
        border-color: rgba(248, 113, 113, 0.5);
    }
"""

# Кэшированные стили для кнопки избранного (оптимизация)
_FAV_BTN_STYLE_ACTIVE = """
    QToolButton {
        border: none;
        background: transparent;
        color: #ffc107;
        font-size: 20px;
        padding: 0;
        margin: 0;
    }
    QToolButton:hover {
        color: #ffca28;
    }
"""
_FAV_BTN_STYLE_INACTIVE = """
    QToolButton {
        border: none;
        background: transparent;
        color: rgba(255, 255, 255, 0.15);
        font-size: 20px;
        padding: 0;
        margin: 0;
    }
    QToolButton:hover {
        color: #ffc107;
    }
"""


class FavoriteCompactStrategyItem(CompactStrategyItem):
    """Компактный элемент стратегии со звёздочкой избранного и hover tooltip"""

    favoriteToggled = pyqtSignal(str, bool)

    def __init__(self, strategy_id, strategy_data, category_key=None, parent=None):
        self.category_key = category_key
        self._current_fav_style = None  # Кэш стиля кнопки избранного

        from strategy_menu import is_favorite_strategy
        self.is_favorite = is_favorite_strategy(strategy_id, category_key)

        super().__init__(strategy_id, strategy_data, parent)
        self._add_favorite_button()

        # Включаем отслеживание мыши для hover tooltip
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def _get_rating_style(self):
        """Возвращает стиль на основе рейтинга стратегии"""
        from strategy_menu import get_strategy_rating
        # Используем category_key для правильной привязки рейтинга
        rating = get_strategy_rating(self.strategy_id, self.category_key)
        if rating == 'working':
            return _STYLE_RATING_WORKING
        elif rating == 'broken':
            return _STYLE_RATING_BROKEN
        return None

    def _apply_style(self, selected):
        """Стиль с учётом избранного и рейтинга (с кэшированием)"""
        if selected:
            new_style = _STYLE_SELECTED
        else:
            # Сначала проверяем рейтинг (приоритет выше чем избранное)
            rating_style = self._get_rating_style()
            if rating_style:
                new_style = rating_style
            elif self.is_favorite:
                new_style = _STYLE_FAVORITE
            else:
                new_style = _STYLE_NORMAL

        # Применяем только если стиль изменился
        if self._current_style != new_style:
            self._current_style = new_style
            self.setStyleSheet(new_style)

    def _add_favorite_button(self):
        """Добавляет звёздочку избранного слева (вынесена за пределы основного контента)"""
        self.favorite_btn = QToolButton()
        self.favorite_btn.setFixedSize(28, 28)
        self.favorite_btn.setCheckable(True)
        self.favorite_btn.setChecked(self.is_favorite)
        self.favorite_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_favorite_style()
        self.favorite_btn.clicked.connect(self._toggle_favorite)

        if hasattr(self, 'main_layout') and self.main_layout:
            # Вставляем звезду первой с отрицательным отступом чтобы была левее
            self.main_layout.insertWidget(0, self.favorite_btn)
            self.main_layout.setContentsMargins(2, 4, 10, 4)  # Меньше слева

    def _update_favorite_style(self):
        """Стиль звёздочки - крупная и заметная (с кэшированием)"""
        if self.is_favorite:
            self.favorite_btn.setText("★")
            self.favorite_btn.setToolTip("Убрать из избранных")
            new_style = _FAV_BTN_STYLE_ACTIVE
        else:
            self.favorite_btn.setText("☆")
            self.favorite_btn.setToolTip("Добавить в избранные")
            new_style = _FAV_BTN_STYLE_INACTIVE

        # Применяем только если стиль изменился
        if self._current_fav_style != new_style:
            self._current_fav_style = new_style
            self.favorite_btn.setStyleSheet(new_style)
    
    def _toggle_favorite(self):
        """Переключает избранное"""
        from strategy_menu import toggle_favorite_strategy
        
        self.is_favorite = toggle_favorite_strategy(self.strategy_id, self.category_key)
        self.favorite_btn.setChecked(self.is_favorite)
        self._update_favorite_style()
        self._apply_style(self.is_selected)
        self.favoriteToggled.emit(self.strategy_id, self.is_favorite)
    
    def _show_context_menu(self, pos):
        """Показывает окно информации о стратегии по ПКМ"""
        from .args_preview_dialog import preview_manager
        # Передаём category_key для правильной работы рейтингов
        preview_manager.show_preview(self, self.strategy_id, self.strategy_data, category_key=self.category_key)

    def _on_toggled(self, checked):
        """Переопределяем переключение"""
        self.is_selected = checked
        self._apply_style(checked)
        if checked:
            self.clicked.emit(self.strategy_id)

    def enterEvent(self, event):
        """При наведении мыши показываем hover tooltip"""
        try:
            from .hover_tooltip import tooltip_manager
            
            pos = self.mapToGlobal(QPoint(self.width() + 10, 0))
            tooltip_manager.show_tooltip(pos, self.strategy_data, self.strategy_id, delay=600)
        except Exception:
            pass
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """При уходе мыши скрываем tooltip"""
        try:
            from .hover_tooltip import tooltip_manager
            tooltip_manager.hide_tooltip(delay=100)
        except Exception:
            pass
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """Клик с учётом кнопки избранного"""
        # Скрываем tooltip при клике
        try:
            from .hover_tooltip import tooltip_manager
            tooltip_manager.hide_immediately()
        except Exception:
            pass
        
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, 'favorite_btn'):
                btn_rect = self.favorite_btn.geometry()
                if not btn_rect.contains(event.pos()):
                    self.radio.setChecked(True)
            else:
                self.radio.setChecked(True)
        super().mousePressEvent(event)


def get_strategy_widget(strategy_id, strategy_data, category_key, parent=None):
    """Фабричная функция для создания виджета стратегии"""
    return FavoriteCompactStrategyItem(strategy_id, strategy_data, category_key, parent)
