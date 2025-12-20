# strategy_menu/workers.py

from PyQt6.QtCore import QObject, pyqtSignal
from log import log


class StrategyListLoader(QObject):
    """Воркер для асинхронной загрузки списка стратегий."""
    
    finished = pyqtSignal(dict, str)  # strategies_dict, error_message
    progress = pyqtSignal(str)        # status_message
    
    def __init__(self, strategy_manager, force_update=False):
        super().__init__()
        self.strategy_manager = strategy_manager
        self.force_update = force_update
    
    def run(self):
        try:
            if self.force_update:
                self.progress.emit("Принудительное обновление с сервера...")
                strategies = self.strategy_manager.get_strategies_list(force_update=True)
            else:
                self.progress.emit("Загрузка локального кэша...")
                strategies = self.strategy_manager.get_strategies_list(force_update=False)
                
            self.progress.emit("Обработка списка стратегий...")
            
            if strategies:
                self.finished.emit(strategies, "")
            else:
                self.finished.emit({}, "Список стратегий пуст")
                
        except Exception as e:
            error_msg = f"Ошибка загрузки: {str(e)}"
            log(error_msg, "❌ ERROR")
            self.finished.emit({}, error_msg)


class InternetStrategyLoader(QObject):
    """Воркер для загрузки стратегий из интернета."""
    
    finished = pyqtSignal(dict, str)
    progress = pyqtSignal(str)
    
    def __init__(self, strategy_manager):
        super().__init__()
        self.strategy_manager = strategy_manager
    
    def run(self):
        try:
            self.progress.emit("Подключение к серверу...")
            strategies = self.strategy_manager.download_strategies_index_from_internet()
            
            if strategies:
                self.finished.emit(strategies, "")
            else:
                self.finished.emit({}, "Не удалось загрузить стратегии")
                
        except Exception as e:
            error_msg = f"Ошибка загрузки: {str(e)}"
            log(error_msg, "❌ ERROR")
            self.finished.emit({}, error_msg)


class StrategyFilesDownloader(QObject):
    """Воркер для скачивания .bat файлов стратегий."""
    
    finished = pyqtSignal(int, int, str)  # downloaded_count, total_count, error_message
    progress = pyqtSignal(int, str)       # progress_percent, current_strategy
    
    def __init__(self, strategy_manager):
        super().__init__()
        self.strategy_manager = strategy_manager
    
    def run(self):
        try:
            strategies = self.strategy_manager.get_local_strategies_only()
            if not strategies:
                self.finished.emit(0, 0, "Список стратегий пуст")
                return
            
            downloaded_count = 0
            total_count = 0
            
            # Подсчитываем файлы для скачивания
            for strategy_id, strategy_info in strategies.items():
                if strategy_info.get('file_path'):
                    version_status = self.strategy_manager.check_strategy_version_status(strategy_id)
                    if version_status in ['not_downloaded', 'outdated']:
                        total_count += 1
            
            if total_count == 0:
                self.finished.emit(0, 0, "Все файлы актуальны")
                return
            
            current_file = 0
            
            for strategy_id, strategy_info in strategies.items():
                file_path = strategy_info.get('file_path')
                if file_path:
                    version_status = self.strategy_manager.check_strategy_version_status(strategy_id)
                    if version_status in ['not_downloaded', 'outdated']:
                        current_file += 1
                        strategy_name = strategy_info.get('name') or strategy_id
                        
                        # Обновляем прогресс
                        progress_percent = int((current_file / total_count) * 100)
                        self.progress.emit(progress_percent, strategy_name)
                        
                        try:
                            local_path = self.strategy_manager.download_single_strategy_bat(strategy_id)
                            if local_path:
                                downloaded_count += 1
                                log(f"Скачан файл стратегии: {file_path}", "INFO")
                            else:
                                log(f"Не удалось скачать файл: {file_path}", "⚠ WARNING")
                        except Exception as e:
                            log(f"Ошибка при скачивании {file_path}: {e}", "⚠ WARNING")
            
            self.finished.emit(downloaded_count, total_count, "")

        except Exception as e:
            error_msg = f"Ошибка скачивания: {str(e)}"
            log(error_msg, "❌ ERROR")
            self.finished.emit(0, 0, error_msg)


class CategoryTabLoader(QObject):
    """
    Асинхронный загрузчик контента вкладки категории.
    Загружает стратегии, избранные и текущий выбор в фоновом потоке.
    """

    # category_key, strategies_dict, favorites_list, current_selection
    finished = pyqtSignal(str, dict, list, str)
    # category_key, error_message
    error = pyqtSignal(str, str)

    def __init__(self, category_key: str):
        super().__init__()
        self.category_key = category_key

    def run(self):
        """Загружает данные категории в фоновом потоке"""
        try:
            from strategy_menu.strategies_registry import registry
            from strategy_menu import get_direct_strategy_selections, get_favorite_strategies

            # Загружаем стратегии для категории
            strategies_dict = registry.get_category_strategies(self.category_key)

            # Загружаем избранные
            favorites_list = get_favorite_strategies(self.category_key) or []

            # Загружаем текущий выбор
            selections = get_direct_strategy_selections()
            current_selection = selections.get(self.category_key, "none")

            log(f"Категория {self.category_key}: загружено {len(strategies_dict)} стратегий", "DEBUG")

            self.finished.emit(
                self.category_key,
                strategies_dict,
                favorites_list,
                current_selection
            )

        except Exception as e:
            error_msg = f"Ошибка загрузки категории {self.category_key}: {e}"
            log(error_msg, "ERROR")
            self.error.emit(self.category_key, str(e))