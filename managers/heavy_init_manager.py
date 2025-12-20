from PyQt6.QtCore import QTimer
from log import log
import os
import ctypes
from ctypes import wintypes


class HeavyInitManager:
    """Быстрый менеджер инициализации через WinAPI (без QThread)"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self._init_started = False
        
        # WinAPI функции для максимальной скорости
        self._kernel32 = ctypes.windll.kernel32
        self._wininet = None
        try:
            self._wininet = ctypes.windll.wininet
        except:
            pass

    def start_heavy_init(self):
        """⚡ Быстрая синхронная инициализация через WinAPI"""
        
        # ЗАЩИТА от двойного вызова
        if self._init_started:
            log("HeavyInit уже запущен, пропускаем", "DEBUG")
            return
        
        self._init_started = True
        log("⚡ Быстрая инициализация через WinAPI", "DEBUG")
        
        try:
            # 1. Проверка winws.exe через WinAPI (~0.1ms)
            if not self._check_winws_fast():
                log("winws.exe не найден", "❌ ERROR")
                self.app.set_status("❌ winws.exe не найден")
                return
            
            log("✅ winws.exe найден", "DEBUG")
            
            # 2. Быстрая проверка интернета через WinAPI (~10-50ms)
            has_internet = self._check_internet_fast()
            if not has_internet:
                log("Нет интернета - работаем в автономном режиме", "⚠ WARNING")
            
            # 3. Подсчёт стратегий через WinAPI (~1-5ms)
            strategy_count = self._count_strategies_fast()
            log(f"Найдено {strategy_count} стратегий", "DEBUG")
            
            # 4. Обновление UI через менеджеры
            self._finalize_init()
            
        except Exception as e:
            log(f"Ошибка в HeavyInit: {e}", "❌ ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "❌ ERROR")
        finally:
            self._init_started = False

    def _check_winws_fast(self) -> bool:
        """⚡ Проверка winws.exe через WinAPI GetFileAttributesW (~0.1ms)"""
        try:
            from config import get_winws_exe_for_method
            from strategy_menu import get_strategy_launch_method

            launch_method = get_strategy_launch_method()
            target_file = get_winws_exe_for_method(launch_method)
            
            # GetFileAttributesW возвращает -1 если файла нет
            INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
            attrs = self._kernel32.GetFileAttributesW(target_file)
            
            return attrs != INVALID_FILE_ATTRIBUTES
            
        except Exception as e:
            log(f"Ошибка при проверке winws.exe: {e}", "DEBUG")
            # Fallback на os.path.exists
            try:
                from config import WINWS_EXE
                return os.path.exists(WINWS_EXE)
            except:
                return False
    
    def _check_internet_fast(self) -> bool:
        """⚡ Проверка интернета через WinAPI InternetCheckConnection (~10-50ms)"""
        try:
            if not self._wininet:
                return False
            
            # InternetCheckConnectionW - быстрая проверка без HTTP запроса
            result = self._wininet.InternetCheckConnectionW(
                "https://www.google.com",
                1,  # FLAG_ICC_FORCE_CONNECTION
                0
            )
            
            return bool(result)
            
        except Exception as e:
            log(f"Ошибка проверки интернета через WinAPI: {e}", "DEBUG")
            return False
    
    def _count_strategies_fast(self) -> int:
        """⚡ Подсчёт .bat файлов через os.scandir (~1-5ms)"""
        try:
            from config import BAT_FOLDER

            if not os.path.exists(BAT_FOLDER):
                return 0

            # os.scandir быстрее чем os.listdir и безопаснее чем ctypes
            count = 0
            with os.scandir(BAT_FOLDER) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.lower().endswith('.bat'):
                        count += 1
            return count

        except Exception as e:
            log(f"Ошибка подсчёта стратегий: {e}", "DEBUG")
            return 0
    
    def _finalize_init(self):
        """Финализация инициализации - обновление UI и автозапуск"""
        try:
            # Обновляем splash
            if hasattr(self.app, 'splash') and self.app.splash:
                self.app.splash.set_progress(75, "Подготовка к запуску...", "Почти готово")
            
            # Обновление списка стратегий
            if hasattr(self.app, 'strategy_manager') and self.app.strategy_manager:
                if self.app.strategy_manager.already_loaded:
                    if hasattr(self.app, 'ui_manager'):
                        self.app.ui_manager.update_strategies_list()
            
            # Автозапуск DPI если настроен
            if hasattr(self.app, 'dpi_manager'):
                self.app.dpi_manager.delayed_dpi_start()
            
            # Combobox-фикс через UI Manager
            for delay in (0, 100, 200):
                QTimer.singleShot(delay, lambda: (
                    self.app.ui_manager.force_enable_combos() 
                    if hasattr(self.app, 'ui_manager') else None
                ))
            
            self.app.set_status("✅ Инициализация завершена")
            log("⚡ Быстрая инициализация завершена", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка финализации: {e}", "❌ ERROR")

    def check_local_files(self) -> bool:
        """Быстрая проверка наличия критически важных файлов (для совместимости)"""
        return self._check_winws_fast()
    
    def cleanup(self):
        """Очистка ресурсов (теперь не требуется - нет потоков)"""
        # Больше нет QThread, все работает синхронно
        self._init_started = False
        log("HeavyInitManager очищен", "DEBUG")