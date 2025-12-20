# strategy_menu/strategy_table_widget_favorites.py

from .strategy_table_widget import StrategyTableWidget


class FavoriteStrategyTableWidget(StrategyTableWidget):
    """Виджет таблицы стратегий (для обратной совместимости)"""
    
    def __init__(self, strategy_manager=None, parent=None):
        super().__init__(strategy_manager, parent)


class StrategyTableWithFavoritesFilter(StrategyTableWidget):
    """Расширение с поддержкой фильтра (для обратной совместимости)"""
    
    def __init__(self, strategy_manager=None, parent=None):
        super().__init__(strategy_manager, parent)
        self._all_strategies = {}
    
    def populate_strategies(self, strategies, category_key="bat"):
        """Сохраняет все стратегии"""
        self._all_strategies = strategies.copy()
        super().populate_strategies(strategies, category_key)
