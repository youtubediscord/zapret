# main.py
import sys, os

# ──────────────────────────────────────────────────────────────
# Делаем рабочей директорией папку, где лежит exe/скрипт
# Нужно выполнить до любых других импортов!
# ──────────────────────────────────────────────────────────────
def _set_workdir_to_app():
    """Устанавливает рабочую директорию"""
    try:
        # Nuitka
        if "__compiled__" in globals():
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        # PyInstaller
        elif getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        # Обычный Python
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        os.chdir(app_dir)
        
        # Отладочная информация
        debug_info = f"""
=== ZAPRET STARTUP DEBUG ===
Compiled mode: {'__compiled__' in globals()}
Frozen mode: {getattr(sys, 'frozen', False)}
sys.executable: {sys.executable}
sys.argv[0]: {sys.argv[0]}
Working directory: {app_dir}
Directory exists: {os.path.exists(app_dir)}
Directory contents: {os.listdir(app_dir) if os.path.exists(app_dir) else 'N/A'}
========================
"""
        
        with open("zapret_startup.log", "w", encoding="utf-8") as f:
            f.write(debug_info)
            
    except Exception as e:
        with open("zapret_startup_error.log", "w", encoding="utf-8") as f:
            f.write(f"Error setting workdir: {e}\n")
            import traceback
            f.write(traceback.format_exc())

_set_workdir_to_app()

# ──────────────────────────────────────────────────────────────
# ✅ УБРАНО: Очистка _MEI* папок больше не нужна
# Приложение собирается в режиме --onedir (папка с файлами)
# вместо --onefile, поэтому временные папки не создаются
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
# Устанавливаем глобальный обработчик крашей (ДО всех импортов!)
# ──────────────────────────────────────────────────────────────
from log.crash_handler import install_crash_handler
install_crash_handler()

# ──────────────────────────────────────────────────────────────
# Предзагрузка медленных модулей в фоне (ускоряет старт на ~300ms)
# ──────────────────────────────────────────────────────────────
def _preload_slow_modules():
    """Загружает медленные модули в фоновом потоке.
    
    Когда основной код дойдёт до импорта этих модулей,
    они уже будут в sys.modules - импорт будет мгновенным.
    """
    import threading
    
    def _preload():
        try:
            # Порядок важен! PyQt должен быть загружен до qt_material
            import PyQt6.QtWidgets  # ~17ms
            import PyQt6.QtCore
            import PyQt6.QtGui
            import jinja2            # ~1ms, но нужен qt_material
            import requests          # ~99ms
            import qtawesome         # ~115ms (нужен после PyQt)
            import qt_material       # ~90ms (нужен после PyQt)
            import psutil            # ~10ms
            import json              # для config и API
            import winreg            # для реестра Windows
        except Exception:
            pass  # Ошибки при предзагрузке не критичны
    
    t = threading.Thread(target=_preload, daemon=True)
    t.start()

_preload_slow_modules()

# ──────────────────────────────────────────────────────────────
# дальше можно импортировать всё остальное
# ──────────────────────────────────────────────────────────────
import subprocess, time

from PyQt6.QtCore    import QTimer
from PyQt6.QtWidgets import QMessageBox, QWidget, QApplication

from ui.main_window import MainWindowUI
from ui.splash_screen import SplashScreen
from ui.custom_titlebar import CustomTitleBar, FramelessWindowMixin
from ui.garland_widget import GarlandWidget
from ui.snowflakes_widget import SnowflakesWidget

from startup.admin_check import is_admin

from config import ICON_PATH, ICON_TEST_PATH, WIDTH, HEIGHT
from config import get_last_strategy, set_last_strategy
from config import APP_VERSION
from utils import run_hidden

from ui.theme_subscription_manager import ThemeSubscriptionManager

# DNS настройки теперь интегрированы в network_page
from log import log

from config import CHANNEL

def _set_attr_if_exists(name: str, on: bool = True) -> None:
    """Безопасно включает атрибут, если он есть в текущей версии Qt."""
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtCore import Qt
    
    # 1) PyQt6 ‑ ищем в Qt.ApplicationAttribute
    attr = getattr(Qt.ApplicationAttribute, name, None)
    # 2) PyQt5 ‑ там всё лежит прямо в Qt
    if attr is None:
        attr = getattr(Qt, name, None)

    if attr is not None:
        QCoreApplication.setAttribute(attr, on)

def _handle_update_mode():
    """updater.py запускает: main.py --update <old_exe> <new_exe>"""
    import os, sys, time, shutil, subprocess
    
    if len(sys.argv) < 4:
        log("--update: недостаточно аргументов", "❌ ERROR")
        return

    old_exe, new_exe = sys.argv[2], sys.argv[3]

    # ждём, пока старый exe освободится
    for _ in range(10):  # 10 × 0.5 c = 5 сек
        if not os.path.exists(old_exe) or os.access(old_exe, os.W_OK):
            break
        time.sleep(0.5)

    try:
        shutil.copy2(new_exe, old_exe)
        run_hidden([old_exe])          # запускаем новую версию
        log("Файл обновления применён", "INFO")
    except Exception as e:
        log(f"Ошибка в режиме --update: {e}", "❌ ERROR")
    finally:
        try:
            os.remove(new_exe)
        except FileNotFoundError:
            pass

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from managers.ui_manager import UIManager
    from managers.dpi_manager import DPIManager
    from managers.heavy_init_manager import HeavyInitManager
    from managers.process_monitor_manager import ProcessMonitorManager
    from managers.subscription_manager import SubscriptionManager
    from managers.initialization_manager import InitializationManager

class LupiDPIApp(QWidget, MainWindowUI, ThemeSubscriptionManager, FramelessWindowMixin):
    """Главное окно приложения с поддержкой тем и подписок"""

    from ui.theme import ThemeHandler
    # ✅ ДОБАВЛЯЕМ TYPE HINTS для менеджеров
    ui_manager: 'UIManager'
    dpi_manager: 'DPIManager' 
    heavy_init_manager: 'HeavyInitManager'
    process_monitor_manager: 'ProcessMonitorManager'
    subscription_manager: 'SubscriptionManager'
    initialization_manager: 'InitializationManager'
    theme_handler: 'ThemeHandler'

    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна"""
        self._is_exiting = True
        
        # ✅ СОХРАНЯЕМ ПОЗИЦИЮ И РАЗМЕР ОКНА
        try:
            from config import set_window_position, set_window_size
            
            # Сохраняем позицию
            pos = self.pos()
            set_window_position(pos.x(), pos.y())
            
            # Сохраняем размер
            size = self.size()
            set_window_size(size.width(), size.height())
            
            log(f"Сохранена позиция окна: ({pos.x()}, {pos.y()}), размер: ({size.width()}x{size.height()})", "DEBUG")
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна: {e}", "❌ ERROR")
        
        # ✅ Очищаем менеджеры через их методы
        if hasattr(self, 'heavy_init_manager'):
            self.heavy_init_manager.cleanup()
        
        if hasattr(self, 'process_monitor_manager'):
            self.process_monitor_manager.stop_monitoring()
        
        # ✅ Очищаем DNS UI Manager
        if hasattr(self, 'dns_ui_manager'):
            self.dns_ui_manager.cleanup()
        
        # ✅ Очищаем Theme Manager
        if hasattr(self, 'theme_handler') and hasattr(self.theme_handler, 'theme_manager'):
            try:
                self.theme_handler.theme_manager.cleanup()
            except Exception as e:
                log(f"Ошибка при очистке theme_manager: {e}", "DEBUG")
        
        # ✅ Очищаем страницы с потоками
        try:
            if hasattr(self, 'logs_page') and hasattr(self.logs_page, 'cleanup'):
                self.logs_page.cleanup()
            if hasattr(self, 'servers_page') and hasattr(self.servers_page, 'cleanup'):
                self.servers_page.cleanup()
            if hasattr(self, 'connection_page') and hasattr(self.connection_page, 'cleanup'):
                self.connection_page.cleanup()
            if hasattr(self, 'dns_check_page') and hasattr(self.dns_check_page, 'cleanup'):
                self.dns_check_page.cleanup()
            if hasattr(self, 'hosts_page') and hasattr(self.hosts_page, 'cleanup'):
                self.hosts_page.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке страниц: {e}", "DEBUG")
        
        # ✅ Очищаем потоки через контроллер
        if hasattr(self, 'dpi_controller'):
            self.dpi_controller.cleanup_threads()
        
        # Останавливаем все асинхронные операции без уведомлений
        try:
            if hasattr(self, '_dpi_start_thread') and self._dpi_start_thread:
                try:
                    if self._dpi_start_thread.isRunning():
                        self._dpi_start_thread.quit()
                        self._dpi_start_thread.wait(1000)
                except RuntimeError:
                    pass
            
            if hasattr(self, '_dpi_stop_thread') and self._dpi_stop_thread:
                try:
                    if self._dpi_stop_thread.isRunning():
                        self._dpi_stop_thread.quit()
                        self._dpi_stop_thread.wait(1000)
                except RuntimeError:
                    pass
        except Exception as e:
            log(f"Ошибка при очистке потоков: {e}", "❌ ERROR")
        
        super().closeEvent(event)

    def restore_window_geometry(self):
        """Восстанавливает сохраненную позицию и размер окна"""
        try:
            from config import get_window_position, get_window_size, WIDTH, HEIGHT

            # Минимальные размеры окна (фиксированные)
            MIN_WIDTH = 400
            MIN_HEIGHT = 400

            # Восстанавливаем размер
            saved_size = get_window_size()
            if saved_size:
                width, height = saved_size
                # Проверяем что размер не меньше минимального
                if width >= MIN_WIDTH and height >= MIN_HEIGHT:
                    self.resize(width, height)
                    log(f"Восстановлен размер окна: {width}x{height}", "DEBUG")
                else:
                    log(f"Сохраненный размер слишком мал ({width}x{height}), используем по умолчанию", "DEBUG")
                    self.resize(WIDTH, HEIGHT)
            else:
                self.resize(WIDTH, HEIGHT)
            
            # Восстанавливаем позицию
            saved_pos = get_window_position()
            if saved_pos:
                x, y = saved_pos
                
                # Проверяем что окно будет видимо на каком-то из экранов
                screen_geometry = QApplication.primaryScreen().availableGeometry()
                screens = QApplication.screens()
                
                # Проверяем все экраны
                is_visible = False
                for screen in screens:
                    screen_rect = screen.availableGeometry()
                    # Окно считается видимым если хотя бы 100x100 пикселей на экране
                    if (x + 100 > screen_rect.left() and 
                        x < screen_rect.right() and
                        y + 100 > screen_rect.top() and 
                        y < screen_rect.bottom()):
                        is_visible = True
                        break
                
                if is_visible:
                    self.move(x, y)
                    log(f"Восстановлена позиция окна: ({x}, {y})", "DEBUG")
                else:
                    # Если окно за пределами всех экранов - центрируем на основном
                    self.move(
                        screen_geometry.center().x() - self.width() // 2,
                        screen_geometry.center().y() - self.height() // 2
                    )
                    log(f"Сохраненная позиция за пределами экранов, окно отцентрировано", "WARNING")
            else:
                # Если позиция не сохранена - центрируем
                screen_geometry = QApplication.primaryScreen().availableGeometry()
                self.move(
                    screen_geometry.center().x() - self.width() // 2,
                    screen_geometry.center().y() - self.height() // 2
                )
                log("Позиция не сохранена, окно отцентрировано", "DEBUG")
                
        except Exception as e:
            log(f"Ошибка восстановления геометрии окна: {e}", "❌ ERROR")
            # В случае ошибки используем размер по умолчанию
            from config import WIDTH, HEIGHT
            self.resize(WIDTH, HEIGHT)

    def set_status(self, text: str) -> None:
        """Sets the status text."""
        # Обновляем статус на главной странице
        if hasattr(self, 'home_page'):
            # Определяем тип статуса по тексту
            status_type = "neutral"
            if "работает" in text.lower() or "запущен" in text.lower() or "успешно" in text.lower():
                status_type = "running"
            elif "останов" in text.lower() or "ошибка" in text.lower() or "выключен" in text.lower():
                status_type = "stopped"
            elif "внимание" in text.lower() or "предупреждение" in text.lower():
                status_type = "warning"
            self.home_page.set_status(text, status_type)

    def update_ui(self, running: bool) -> None:
        """Обновляет состояние кнопок в зависимости от статуса запуска"""
        if hasattr(self, 'ui_manager'):
            self.ui_manager.update_ui_state(running)

    def update_strategies_list(self, force_update: bool = False) -> None:
        """Обновляет список доступных стратегий"""
        if hasattr(self, 'ui_manager'):
            self.ui_manager.update_strategies_list(force_update)

    def delayed_dpi_start(self) -> None:
        """Выполняет отложенный запуск DPI с проверкой наличия автозапуска"""
        if hasattr(self, 'dpi_manager'):
            self.dpi_manager.delayed_dpi_start()

    def update_autostart_ui(self, service_running: bool) -> None:
        """Обновляет интерфейс при включении/выключении автозапуска"""
        if hasattr(self, 'ui_manager'):
            self.ui_manager.update_autostart_ui(service_running)

    def force_enable_combos(self) -> bool:
        """Принудительно включает комбо-боксы тем"""
        if hasattr(self, 'ui_manager'):
            return self.ui_manager.force_enable_combos()
        return False
    
    def on_strategy_selected_from_dialog(self, strategy_id: str, strategy_name: str) -> None:
        """Обрабатывает выбор стратегии из диалога."""
        try:
            log(f"Выбрана стратегия: {strategy_name} (ID: {strategy_id})", level="INFO")
            
            # Сохраняем ID и имя выбранной стратегии в атрибутах класса
            self.current_strategy_id = strategy_id
            self.current_strategy_name = strategy_name
            
            # ✅ УБИРАЕМ АВТОМАТИЧЕСКОЕ СКРЫТИЕ - теперь это контролируется настройкой
            # Диалог сам решит закрываться или нет в методе accept()
            
            # ✅ ДЛЯ DIRECT РЕЖИМА ИСПОЛЬЗУЕМ ПРОСТОЕ НАЗВАНИЕ
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            
            if strategy_id == "DIRECT_MODE" or launch_method == "direct":
                display_name = "Прямой запуск"
                self.current_strategy_name = display_name
                strategy_name = display_name
                # Для Direct режима selections сохраняются отдельно, не нужно сохранять через set_last_strategy
                log(f"Установлено простое название для Direct режима: {display_name}", "DEBUG")
            else:
                # Для BAT режима сохраняем последнюю стратегию (отдельный ключ реестра)
                from config.reg import set_last_bat_strategy
                set_last_bat_strategy(strategy_name)
            
            # Обновляем метку с текущей стратегией
            self.current_strategy_label.setText(strategy_name)
            
            # Обновляем новые страницы интерфейса
            if hasattr(self, 'update_current_strategy_display'):
                self.update_current_strategy_display(strategy_name)

            # Записываем время изменения стратегии
            self.last_strategy_change_time = time.time()
            
            # ✅ ИСПРАВЛЕННАЯ ЛОГИКА для обработки Direct режима
            if launch_method == "direct":
                if strategy_id == "DIRECT_MODE" or strategy_id == "combined":
                    # Получаем стратегию из сохранённых настроек
                    from strategy_menu.strategy_lists_separated import combine_strategies
                    from strategy_menu import get_direct_strategy_selections, get_default_selections
                        
                    try:
                        category_selections = get_direct_strategy_selections()
                    except:
                        category_selections = get_default_selections()
                    
                    combined_strategy = combine_strategies(**category_selections)
                    combined_args = combined_strategy['args']
                    
                    combined_data = {
                        'id': strategy_id,
                        'name': strategy_name,
                        'is_combined': True,
                        'args': combined_args,
                        'selections': category_selections
                    }
                    
                    log(f"Комбинированная стратегия: {len(combined_args)} символов", "DEBUG")
                    
                    self._last_combined_args = combined_args
                    self._last_category_selections = category_selections
                    
                    self.dpi_controller.start_dpi_async(selected_mode=combined_data)
                    
                else:
                    self.dpi_controller.start_dpi_async(selected_mode=(strategy_id, strategy_name))
            else:
                try:
                    strategies = self.strategy_manager.get_strategies_list()
                    strategy_info = strategies.get(strategy_id, {})
                    
                    if not strategy_info:
                        strategy_info = {
                            'name': strategy_name,
                            'file_path': f"{strategy_id}.bat"
                        }
                        log(f"Не удалось найти информацию о стратегии {strategy_id}, используем базовую", "⚠ WARNING")
                    
                    self.dpi_controller.start_dpi_async(selected_mode=strategy_info)
                    
                except Exception as strategy_error:
                    log(f"Ошибка при получении информации о стратегии: {strategy_error}", "❌ ERROR")
                    self.dpi_controller.start_dpi_async(selected_mode=strategy_name)
            
            # ✅ Перезапуск Discord теперь выполняется в dpi_controller._on_dpi_start_finished()
            # после успешного запуска DPI (убрано дублирование)
                
        except Exception as e:
            log(f"Ошибка при установке выбранной стратегии: {str(e)}", level="❌ ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            self.set_status(f"Ошибка при установке стратегии: {str(e)}")

    def __init__(self, start_in_tray=False):
        # ✅ Вызываем super().__init__() ОДИН раз - он инициализирует все базовые классы
        super().__init__()
        
        # ✅ ИНИЦИАЛИЗИРУЕМ МЕТОД ЗАПУСКА ПРИ ПЕРВОМ ЗАПУСКЕ
        from strategy_menu import get_strategy_launch_method
        current_method = get_strategy_launch_method()
        log(f"Метод запуска стратегий: {current_method}", "INFO")
        
        self.start_in_tray = start_in_tray
        
        # Флаги для защиты от двойных вызовов
        self._splash_closed = False
        self._dpi_autostart_initiated = False
        self._heavy_init_started = False
        self._heavy_init_thread = None

        # ✅ FRAMELESS WINDOW - убираем стандартную рамку
        from PyQt6.QtCore import Qt
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinMaxButtonsHint
        )
        # Включаем прозрачный фон для скругленных углов
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Устанавливаем основные параметры окна
        self.setWindowTitle(f"Zapret2 v{APP_VERSION} - загрузка...")

        # ✅ ДОБАВЛЕНО: Восстанавливаем сохраненную геометрию окна
        self.restore_window_geometry()
        
        # ✅ УСТАНАВЛИВАЕМ ПРАВИЛЬНЫЙ РАЗМЕР ОКНА (компактный)
        self.setMinimumSize(WIDTH, 400)  # Минимальная высота 400, ширина из конфига
        self.resize(WIDTH, HEIGHT)       # Стартовый размер
                
        # Устанавливаем иконку
        icon_path = ICON_TEST_PATH if CHANNEL == "test" else ICON_PATH
        self._app_icon = None
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self._app_icon = QIcon(icon_path)
            self.setWindowIcon(self._app_icon)
            QApplication.instance().setWindowIcon(self._app_icon)
        
        from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout, QFrame
        
        # ✅ ГЛАВНЫЙ КОНТЕЙНЕР со скругленными углами и полупрозрачным фоном (Windows 11 style)
        self.container = QFrame(self)
        self.container.setObjectName("mainContainer")
        # ⚠️ НЕ применяем inline стили - они будут из темы QApplication

        # Инициализируем функционал безрамочного resize
        self.init_frameless()
        
        # Layout для контейнера
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # ✅ КАСТОМНЫЙ TITLEBAR
        self.title_bar = CustomTitleBar(
            self, 
            title=f"Zapret2 v{APP_VERSION} - загрузка..."
        )
        if self._app_icon:
            self.title_bar.set_icon(self._app_icon)
        container_layout.addWidget(self.title_bar)
        
        # ✅ НОВОГОДНЯЯ ГИРЛЯНДА (Premium) - поверх всего контента
        self.garland = GarlandWidget(self.container)
        self.garland.setGeometry(0, 32, self.width(), 20)  # Под title bar
        self.garland.raise_()  # Поверх всех виджетов
        
        # ✅ СНЕЖИНКИ (Premium) - поверх всего окна (геометрия будет установлена в showEvent/resizeEvent)
        self.snowflakes = SnowflakesWidget(self)

        # Обновляем зоны resize после создания titlebar,
        # иначе верхний правый угол будет рассчитан без учёта кнопок
        self._update_resize_handles()
        
        # Создаем QStackedWidget для переключения между экранами
        self.stacked_widget = QStackedWidget()
        # ⚠️ НЕ применяем inline стили - они будут из темы QApplication
        container_layout.addWidget(self.stacked_widget)
        
        # Главный layout окна
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)
        
        # Создаем основной виджет (с родителем чтобы не было отдельного окна!)
        self.main_widget = QWidget(self.stacked_widget)  # ✅ Родитель = stacked_widget
        # ⚠️ НЕ применяем inline стили - они будут из темы QApplication
        # ✅ Только минимальная ширина, высота динамическая
        self.main_widget.setMinimumWidth(WIDTH)

        # ✅ НЕ СОЗДАЕМ theme_handler ЗДЕСЬ - создадим его после theme_manager

        # Добавляем main_widget в stack
        self.main_index = self.stacked_widget.addWidget(self.main_widget)
        self.stacked_widget.setCurrentIndex(self.main_index)
        
        # ✅ ВОЗВРАЩАЕМ SPLASH но главное окно НЕ показываем пока CSS не готов
        self._css_applied_at_startup = False
        self._startup_theme = None
        
        if not self.start_in_tray:
            # Создаём splash
            self.splash = SplashScreen()
            self.splash.load_complete.connect(self._on_splash_complete)
            self.splash.show()
            
            QApplication.processEvents()
            
            self.splash.set_progress(5, "Запуск Zapret...", "Подготовка")
            QApplication.processEvents()
            
            # Главное окно НЕ показываем - оно создано но скрыто
            # Splash анимируется, а главное окно ждёт применения CSS
            log("Splash показан, главное окно скрыто", "DEBUG")
        else:
            # Если в трее - без splash
            self.splash = None
            self._css_applied_at_startup = False
        
        # Splash больше не используется - окно показывается сразу
        
        # Инициализируем атрибуты
        self.process_monitor = None
        self.first_start = True
        self.current_strategy_id = None
        self.current_strategy_name = None
        
        # Теперь строим UI в main_widget (не в self)
        self._build_main_ui()
        
        # Обновляем прогресс splash
        if self.splash:
            self.splash.set_progress(35, "Создание интерфейса...", "")
        
        # Создаем менеджеры
        from managers.initialization_manager import InitializationManager
        from managers.subscription_manager import SubscriptionManager
        from managers.heavy_init_manager import HeavyInitManager
        from managers.process_monitor_manager import ProcessMonitorManager
        from managers.ui_manager import UIManager
        from managers.dpi_manager import DPIManager

        self.initialization_manager = InitializationManager(self)
        self.subscription_manager = SubscriptionManager(self)
        self.heavy_init_manager = HeavyInitManager(self)
        self.process_monitor_manager = ProcessMonitorManager(self)
        self.ui_manager = UIManager(self)
        self.dpi_manager = DPIManager(self)
        
        # Обновляем прогресс splash
        if self.splash:
            self.splash.set_progress(50, "Проверка подписки...", "")

        # Инициализируем donate checker
        self._init_real_donate_checker()  # Упрощенная версия
        self.update_title_with_subscription_status(False, None, 0, source="init")
        
        # Запускаем асинхронную инициализацию через менеджер
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self.initialization_manager.run_async_init)
        QTimer.singleShot(1000, self.subscription_manager.initialize_async)
        # Гирлянда инициализируется автоматически в subscription_manager после проверки подписки

    def init_theme_handler(self):
        """Инициализирует theme_handler после создания theme_manager"""
        if not hasattr(self, 'theme_handler'):
            from ui.theme import ThemeHandler
            self.theme_handler = ThemeHandler(self, target_widget=self.main_widget)
            
            # Если theme_manager уже создан, устанавливаем его
            if hasattr(self, 'theme_manager'):
                self.theme_handler.set_theme_manager(self.theme_manager)
                
            log("ThemeHandler инициализирован", "DEBUG")

    # ═══════════════════════════════════════════════════════════════════════
    # FRAMELESS WINDOW: Обработчики событий мыши для изменения размера
    # ═══════════════════════════════════════════════════════════════════════
    
    def setWindowTitle(self, title: str):
        """Переопределяем setWindowTitle для обновления кастомного titlebar"""
        super().setWindowTitle(title)
        if hasattr(self, 'title_bar'):
            self.title_bar.set_title(title)
    
    def mousePressEvent(self, event):
        """Обработка нажатия мыши"""
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        """Обработка движения мыши"""
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        """Обработка отпускания мыши"""
        super().mouseReleaseEvent(event)

    def _build_main_ui(self) -> None:
        """Строит основной UI в main_widget"""
        # Временно меняем self на main_widget для build_ui
        old_layout = self.main_widget.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            # ✅ Удаляем layout напрямую (НЕ через QWidget() - это создаёт призрачное окно!)
            old_layout.deleteLater()
        
        # ⚠️ НЕ применяем inline стили к main_widget - они будут из темы QApplication
        
        # Вызываем build_ui но с модификацией - все виджеты создаются как дети main_widget
        # Для этого временно подменяем методы
        original_method = self.build_ui
        
        # Создаем модифицированный build_ui
        def modified_build_ui(width, height):
            # Сохраняем оригинальные методы
            original_setStyleSheet = self.setStyleSheet
            original_setMinimumSize = self.setMinimumSize
            original_layout = self.layout
            
            # Временно перенаправляем на main_widget
            self.setStyleSheet = self.main_widget.setStyleSheet
            self.setMinimumSize = self.main_widget.setMinimumSize
            self.layout = self.main_widget.layout
            
            # Вызываем оригинальный build_ui
            original_method(width, height)
            
            # Восстанавливаем методы
            self.setStyleSheet = original_setStyleSheet
            self.setMinimumSize = original_setMinimumSize
            self.layout = original_layout
        
        # Вызываем модифицированный метод
        modified_build_ui(WIDTH, HEIGHT)

    def _on_splash_complete(self) -> None:
        """Обработчик завершения splash - показываем главное окно"""
        if self._splash_closed:
            log("Splash уже закрыт, пропускаем", "DEBUG")
            return
        
        self._splash_closed = True
        log("Splash завершён, показываем главное окно", "DEBUG")
        
        # Показываем главное окно
        if not self.start_in_tray and not self.isVisible():
            self.show()
            log("Основное окно показано", "DEBUG")
        
        # Принудительно обновляем стили
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10, self._force_style_refresh)
        
        # Проверяем РКН Тян темы
        if hasattr(self, 'theme_manager'):
            current_theme = self.theme_manager.current_theme
            if current_theme == "РКН Тян":
                QTimer.singleShot(200, lambda: self.theme_manager.apply_rkn_background())
            elif current_theme == "РКН Тян 2":
                QTimer.singleShot(200, lambda: self.theme_manager.apply_rkn2_background())
        
        self.splash = None
    
    def _apply_deferred_css_if_needed(self) -> None:
        """Применяет отложенный полный CSS (вызывается через 300ms после показа окна)"""
        log(f"🎨 _apply_deferred_css_if_needed вызван, has_deferred={hasattr(self, '_deferred_css')}", "DEBUG")
        
        if not hasattr(self, '_deferred_css'):
            return
            
        log("🎨 Применяем полный CSS (300ms после показа окна)", "DEBUG")
        try:
            import time as _time
            _t = _time.perf_counter()
            
            QApplication.instance().setStyleSheet(self._deferred_css)
            self.setStyleSheet(self._deferred_css)
            
            from PyQt6.QtGui import QPalette
            self.setPalette(QPalette())
            
            elapsed_ms = (_time.perf_counter()-_t)*1000
            log(f"  setStyleSheet took {elapsed_ms:.0f}ms (полный CSS)", "DEBUG")
            
            # Обновляем theme_manager
            if hasattr(self, 'theme_manager'):
                self.theme_manager._current_css_hash = hash(self.styleSheet())
                self.theme_manager._theme_applied = True
                self.theme_manager.current_theme = getattr(self, '_deferred_theme_name', self.theme_manager.current_theme)
                
                if getattr(self, '_deferred_persist', False):
                    from ui.theme import set_selected_theme
                    set_selected_theme(self.theme_manager.current_theme)
            
            # Принудительно обновляем стили виджетов
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(10, self._force_style_refresh)
            
            # Проверяем РКН Тян темы
            if hasattr(self, 'theme_manager'):
                current_theme = self.theme_manager.current_theme
                if current_theme == "РКН Тян":
                    QTimer.singleShot(200, lambda: self.theme_manager.apply_rkn_background())
                elif current_theme == "РКН Тян 2":
                    QTimer.singleShot(200, lambda: self.theme_manager.apply_rkn2_background())
            
            # Очищаем отложенные данные
            delattr(self, '_deferred_css')
            if hasattr(self, '_deferred_theme_name'):
                delattr(self, '_deferred_theme_name')
            if hasattr(self, '_deferred_persist'):
                delattr(self, '_deferred_persist')
                
        except Exception as e:
            log(f"Ошибка применения отложенного CSS: {e}", "ERROR")
    
    def _force_style_refresh(self) -> None:
        """Принудительно обновляет стили всех виджетов после показа окна
        
        Необходимо потому что CSS применяется к QApplication ДО создания/показа виджетов.
        unpolish/polish заставляет Qt пересчитать стили для каждого виджета.
        """
        try:
            # unpolish/polish принудительно пересчитывает стили виджета
            for widget in self.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            
            log("🎨 Принудительное обновление стилей выполнено после показа окна", "DEBUG")
        except Exception as e:
            log(f"Ошибка обновления стилей: {e}", "DEBUG")
    
    def _adjust_window_size(self) -> None:
        """Корректирует размер окна под значения из config.py"""
        try:
            from config import WIDTH, HEIGHT
            
            # Используем размеры из конфига
            self.resize(WIDTH, HEIGHT)
            log(f"Размер окна установлен из конфига: {WIDTH}x{HEIGHT}", "DEBUG")
        except Exception as e:
            log(f"Ошибка корректировки размера: {e}", "DEBUG")

    def _init_real_donate_checker(self) -> None:
        """Создает базовый DonateChecker (полная инициализация в SubscriptionManager)"""
        try:
            from donater import DonateChecker
            self.donate_checker = DonateChecker()
            log("Базовый DonateChecker создан", "DEBUG")
        except Exception as e:
            log(f"Ошибка создания DonateChecker: {e}", "❌ ERROR")

    def show_subscription_dialog(self) -> None:
        """Переключается на страницу Premium"""
        try:
            # Переключаемся на страницу Premium через sidebar
            if hasattr(self, 'side_nav'):
                # Индекс страницы Premium в sidebar
                # Главная(0), Управление(1), Стратегии(2), Hostlist(3), IPset(4), Настройки DPI(5),
                # Автозапуск(6), Сеть(7), Оформление(8), Premium(9), Логи(10), О программе(11)
                premium_index = 10
                self.side_nav.set_section(premium_index)
            
        except Exception as e:
            log(f"Ошибка при переходе на страницу Premium: {e}", level="❌ ERROR")
            self.set_status(f"Ошибка: {e}")
            
    def open_folder(self) -> None:
        """Opens the DPI folder."""
        try:
            run_hidden('explorer.exe .', shell=True)
        except Exception as e:
            self.set_status(f"Ошибка при открытии папки: {str(e)}")

    def open_connection_test(self) -> None:
        """✅ Переключает на вкладку диагностики соединений."""
        try:
            if hasattr(self, "connection_page") and hasattr(self, "pages_stack"):
                page_index = self.pages_stack.indexOf(self.connection_page)
                if page_index >= 0:
                    if hasattr(self, "side_nav"):
                        self.side_nav.set_page(page_index)
                    try:
                        self.connection_page.start_btn.setFocus()
                    except Exception:
                        pass
                log("Открыта вкладка диагностики соединения", "INFO")
        except Exception as e:
            log(f"Ошибка при открытии вкладки тестирования: {e}", "❌ ERROR")
            self.set_status(f"Ошибка: {e}")

    def set_garland_enabled(self, enabled: bool) -> None:
        """Включает или выключает новогоднюю гирлянду (Premium функция)"""
        try:
            if hasattr(self, 'garland'):
                self._update_garland_geometry()
                self.garland.set_enabled(enabled)
                self.garland.raise_()  # Поднимаем поверх всего
                log(f"Гирлянда {'включена' if enabled else 'выключена'}", "DEBUG")
        except Exception as e:
            log(f"Ошибка при изменении состояния гирлянды: {e}", "❌ ERROR")
    
    def _update_garland_geometry(self) -> None:
        """Обновляет позицию и размер гирлянды"""
        if hasattr(self, 'garland') and hasattr(self, 'container'):
            # Позиционируем под title bar на всю ширину контейнера
            self.garland.setGeometry(0, 32, self.container.width(), 20)
            self.garland.raise_()
    
    def set_snowflakes_enabled(self, enabled: bool) -> None:
        """Включает или выключает снежинки (Premium функция)"""
        try:
            if hasattr(self, 'snowflakes'):
                self._update_snowflakes_geometry()
                self.snowflakes.set_enabled(enabled)
                self.snowflakes.raise_()  # Поднимаем поверх всего
                log(f"Снежинки {'включены' if enabled else 'выключены'}", "DEBUG")
        except Exception as e:
            log(f"Ошибка при изменении состояния снежинок: {e}", "❌ ERROR")
    
    def _update_snowflakes_geometry(self) -> None:
        """Обновляет позицию и размер снежинок"""
        if hasattr(self, 'snowflakes'):
            # Покрываем всё окно полностью
            self.snowflakes.setGeometry(0, 0, self.width(), self.height())
            self.snowflakes.raise_()

    def set_blur_effect_enabled(self, enabled: bool) -> None:
        """Включает или выключает эффект размытия окна (Acrylic/Mica)"""
        try:
            from ui.theme import BlurEffect

            # Получаем HWND окна
            hwnd = int(self.winId())

            if enabled:
                success = BlurEffect.enable(hwnd, blur_type="acrylic")
                if success:
                    log("✅ Эффект размытия включён", "INFO")
                else:
                    log("⚠️ Не удалось включить эффект размытия", "WARNING")
            else:
                BlurEffect.disable(hwnd)
                log("✅ Эффект размытия выключен", "INFO")

            # Переприменяем тему чтобы обновить все стили с учётом нового состояния blur
            if hasattr(self, 'theme_manager') and self.theme_manager:
                current_theme = self.theme_manager.current_theme
                if current_theme:
                    self.theme_manager.apply_theme_async(current_theme, persist=False)

        except Exception as e:
            log(f"❌ Ошибка при изменении эффекта размытия: {e}", "ERROR")

    def set_window_opacity(self, value: int) -> None:
        """Устанавливает прозрачность окна (0-100%)"""
        try:
            # Преобразуем процент в значение 0.0-1.0
            opacity = max(0.1, min(1.0, value / 100.0))  # Минимум 0.1 чтобы окно не исчезло
            self.setWindowOpacity(opacity)
            log(f"Прозрачность окна установлена: {value}%", "DEBUG")
        except Exception as e:
            log(f"❌ Ошибка при установке прозрачности окна: {e}", "ERROR")

    def _update_container_opacity(self, blur_enabled: bool) -> None:
        """Обновляет прозрачность контейнера в зависимости от состояния blur"""
        try:
            if not hasattr(self, 'container'):
                return

            # Определяем непрозрачность: меньше для blur, полностью непрозрачно без него
            opacity = 180 if blur_enabled else 255

            # Получаем текущие цвета темы
            from ui.theme import ThemeManager
            theme_manager = ThemeManager.instance()
            if theme_manager and hasattr(theme_manager, '_current_theme'):
                theme_name = theme_manager._current_theme
                theme_config = theme_manager._themes.get(theme_name, {})
                theme_bg = theme_config.get('theme_bg', '30, 30, 30')
                border_color = "rgba(80, 80, 80, 200)" if 'Светлая' not in theme_name else "rgba(200, 200, 200, 220)"
            else:
                theme_bg = '30, 30, 30'
                border_color = "rgba(80, 80, 80, 200)"

            self.container.setStyleSheet(f"""
                QFrame#mainContainer {{
                    background-color: rgba({theme_bg}, {opacity});
                    border-radius: 10px;
                    border: 1px solid {border_color};
                }}
            """)
            log(f"Контейнер обновлён: opacity={opacity}", "DEBUG")
        except Exception as e:
            log(f"Ошибка обновления контейнера: {e}", "WARNING")

    def resizeEvent(self, event):
        """Обновляем декорации при изменении размера окна"""
        super().resizeEvent(event)
        self._update_garland_geometry()
        self._update_snowflakes_geometry()
    
    def showEvent(self, event):
        """Устанавливаем геометрию декораций при первом показе окна"""
        super().showEvent(event)
        self._update_garland_geometry()
        self._update_snowflakes_geometry()

        # Отключаем системное скругление углов на Windows 11
        # чтобы избежать белых треугольников по краям при использовании CSS border-radius
        try:
            from ui.theme import BlurEffect
            hwnd = int(self.winId())
            BlurEffect.disable_window_rounding(hwnd)
        except Exception:
            pass

    def _init_garland_from_registry(self) -> None:
        """Загружает состояние гирлянды и снежинок из реестра при старте"""
        try:
            from config.reg import get_garland_enabled, get_snowflakes_enabled
            
            garland_saved = get_garland_enabled()
            snowflakes_saved = get_snowflakes_enabled()
            log(f"🎄 Инициализация: гирлянда={garland_saved}, снежинки={snowflakes_saved}", "DEBUG")
            
            # Проверяем премиум статус
            is_premium = False
            if hasattr(self, 'donate_checker') and self.donate_checker:
                try:
                    is_premium, _, _ = self.donate_checker.check_subscription_status(use_cache=True)
                    log(f"🎄 Премиум статус: {is_premium}", "DEBUG")
                except Exception as e:
                    log(f"🎄 Ошибка проверки премиума: {e}", "DEBUG")
            
            # Гирлянда
            should_enable_garland = is_premium and garland_saved
            if should_enable_garland:
                self.set_garland_enabled(True)
            if hasattr(self, 'appearance_page'):
                self.appearance_page.set_garland_state(should_enable_garland)
            
            # Снежинки
            should_enable_snowflakes = is_premium and snowflakes_saved
            if should_enable_snowflakes:
                self.set_snowflakes_enabled(True)
            if hasattr(self, 'appearance_page'):
                self.appearance_page.set_snowflakes_state(should_enable_snowflakes)

            # Эффект размытия (не зависит от премиума)
            from config.reg import get_blur_effect_enabled
            blur_saved = get_blur_effect_enabled()
            log(f"🔮 Инициализация: blur={blur_saved}", "DEBUG")
            if blur_saved:
                self.set_blur_effect_enabled(True)
            if hasattr(self, 'appearance_page'):
                self.appearance_page.set_blur_effect_state(blur_saved)

            # Прозрачность окна (не зависит от премиума)
            from config.reg import get_window_opacity
            opacity_saved = get_window_opacity()
            log(f"🔮 Инициализация: opacity={opacity_saved}%", "DEBUG")
            self.set_window_opacity(opacity_saved)
            if hasattr(self, 'appearance_page'):
                self.appearance_page.set_opacity_value(opacity_saved)

        except Exception as e:
            log(f"❌ Ошибка загрузки состояния декораций: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")


def set_batfile_association() -> bool:
    """
    Устанавливает ассоциацию типа файла для .bat файлов
    """
    try:
        # Используем максимально скрытый режим
        command = r'ftype batfile="%SystemRoot%\System32\cmd.exe" /c "%1" %*'

        result = subprocess.run(command, shell=True, check=True, 
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            log("Ассоциация успешно установлена", level="INFO")
            return True
        else:
            log(f"Ошибка при выполнении команды: {result.stderr}", level="❌ ERROR")
            return False
            
    except Exception as e:
        log(f"Произошла ошибка: {e}", level="❌ ERROR")
        return False

def main():
    import sys, ctypes, os, atexit
    log("=== ЗАПУСК ПРИЛОЖЕНИЯ ===", "🔹 main")
    log(APP_VERSION, "🔹 main")

    # ---------------- Быстрая обработка специальных аргументов ----------------
    if "--version" in sys.argv:
        ctypes.windll.user32.MessageBoxW(None, APP_VERSION, "Zapret – версия", 0x40)
        sys.exit(0)

    if "--update" in sys.argv and len(sys.argv) > 3:
        _handle_update_mode()
        sys.exit(0)
    
    start_in_tray = "--tray" in sys.argv
    
    # ---------------- Проверка прав администратора ----------------
    if not is_admin():
        params = " ".join(sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit(0)
    
    # ✅ Автоматическая установка сертификата (асинхронно, не блокирует запуск)
    def _install_certificate_async():
        try:
            from startup.certificate_installer import check_and_install_on_startup
            check_and_install_on_startup()
        except Exception:
            pass  # Не критично
    
    import threading
    threading.Thread(target=_install_certificate_async, daemon=True).start()

    # ---------------- Проверка single instance ----------------
    from startup.single_instance import create_mutex, release_mutex
    from startup.kaspersky import _check_kaspersky_antivirus, show_kaspersky_warning
    from startup.ipc_manager import IPCManager
    
    mutex_handle, already_running = create_mutex("ZapretSingleInstance")
    if already_running:
        ipc = IPCManager()
        if ipc.send_show_command():
            log("Отправлена команда показать окно запущенному экземпляру", "INFO")
        else:
            ctypes.windll.user32.MessageBoxW(None, 
                "Экземпляр Zapret уже запущен, но не удалось показать окно!", "Zapret", 0x40)
        sys.exit(0)
    
    atexit.register(lambda: release_mutex(mutex_handle))

    # ✅ Проверки перед созданием QApplication (не блокируют запуск)
    from startup.check_start import check_goodbyedpi, check_mitmproxy
    from startup.check_start import _native_message
    
    critical_warnings = []
    
    # Проверка GoodbyeDPI: пытаемся удалить службы, но не блокируем запуск
    has_gdpi, gdpi_msg = check_goodbyedpi()
    if has_gdpi:
        log("WARNING: GoodbyeDPI обнаружен - продолжим работу после предупреждения", "⚠ WARNING")
        if gdpi_msg:
            critical_warnings.append(gdpi_msg)
    
    # Проверка mitmproxy: только предупреждаем
    has_mitmproxy, mitmproxy_msg = check_mitmproxy()
    if has_mitmproxy:
        log("WARNING: mitmproxy обнаружен - продолжим работу после предупреждения", "⚠ WARNING")
        if mitmproxy_msg:
            critical_warnings.append(mitmproxy_msg)
    
    if critical_warnings:
        _native_message(
            "Предупреждение",
            "\n\n".join(critical_warnings),
            0x30  # MB_ICONWARNING
        )

    # ---------------- Создаём QApplication ----------------
    try:
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        _set_attr_if_exists("AA_EnableHighDpiScaling")
        _set_attr_if_exists("AA_UseHighDpiPixmaps")

        app = QApplication(sys.argv)

        # ──────────────────────────────────────────────────────────────
        # Debug: log every top-level window that becomes visible
        # Helps to track mysterious blank window reported on Windows
        # ──────────────────────────────────────────────────────────────
        from PyQt6.QtCore import QObject, QEvent, QTimer

        class _ShowDebugFilter(QObject):
            def eventFilter(self, obj, event):
                try:
                    is_window = hasattr(obj, "isWindow") and obj.isWindow()
                except Exception:
                    is_window = False

                if event.type() == QEvent.Type.Show and is_window:
                    print(f"[DEBUG SHOW] {obj.__class__.__name__} title={obj.windowTitle()!r}")
                return False

        _show_debug_filter = _ShowDebugFilter()
        app.installEventFilter(_show_debug_filter)
        app.setQuitOnLastWindowClosed(False)
        
        # Устанавливаем Qt crash handler
        from log.crash_handler import install_qt_crash_handler
        install_qt_crash_handler(app)
        
        # Тема применяется позже в ThemeManager.__init__ - убран дублирующий вызов
        
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(None,
            f"Ошибка инициализации Qt: {e}", "Zapret", 0x10)

    # ---------- проверяем Касперского + показываем диалог -----------------
    try:
        kaspersky_detected = _check_kaspersky_antivirus(None)
    except Exception:
        kaspersky_detected = False

    if kaspersky_detected:
        log("Обнаружен антивирус Kaspersky", "⚠️ KASPERSKY")
        try:
            from startup.kaspersky import show_kaspersky_warning
            show_kaspersky_warning()
        except Exception as e:
            log(f"Не удалось показать предупреждение Kaspersky: {e}",
                "⚠️ KASPERSKY")

    # СОЗДАЁМ ОКНО
    window = LupiDPIApp(start_in_tray=start_in_tray)

    # ──────────────────────────────────────────────────────────────
    # Debug helper: dump all top-level windows shortly after start
    # Helps track mysterious blank window reported by users
    # ──────────────────────────────────────────────────────────────
    def _dump_top_level_windows():
        try:
            items = []
            for w in QApplication.topLevelWidgets():
                items.append(f"{w.__class__.__name__} :: title={w.windowTitle()!r} :: visible={w.isVisible()}")
            log("DEBUG TOP-LEVEL WINDOWS:\n" + "\n".join(items), "DEBUG")
        except Exception as debug_err:
            log(f"Failed to dump top-level windows: {debug_err}", "⚠ DEBUG")

    QTimer.singleShot(1500, _dump_top_level_windows)
    
    # ✅ ЗАПУСКАЕМ IPC СЕРВЕР
    ipc_manager = IPCManager()
    ipc_manager.start_server(window)
    atexit.register(ipc_manager.stop)

    if start_in_tray:
        log("Запуск приложения скрыто в трее", "TRAY")
        if hasattr(window, 'tray_manager'):
            window.tray_manager.show_notification(
                "Zapret работает в трее", 
                "Приложение запущено в фоновом режиме"
            )
                
    # ✅ НЕКРИТИЧЕСКИЕ ПРОВЕРКИ ПОСЛЕ ПОКАЗА ОКНА
    def async_startup_checks():
        """Выполняет некритические стартовые проверки асинхронно"""
        try:
            from startup.bfe_util import preload_service_status, ensure_bfe_running, cleanup as bfe_cleanup
            from startup.check_start import display_startup_warnings
            from startup.remove_terminal import remove_windows_terminal_if_win11
            from startup.admin_check_debug import debug_admin_status
            
            preload_service_status("BFE")
            
            if not ensure_bfe_running(show_ui=True):
                log("BFE не запущен, продолжаем работу после предупреждения", "⚠ WARNING")
            
            # ✅ ТОЛЬКО НЕКРИТИЧЕСКИЕ ПРОВЕРКИ (пути, команды, архив)
            warnings_ok = display_startup_warnings()
            if not warnings_ok and not start_in_tray:
                log("Некритические проверки не пройдены, продолжаем работу после предупреждения", "⚠ WARNING")
            
            remove_windows_terminal_if_win11()
            debug_admin_status()
            set_batfile_association()
            
            atexit.register(bfe_cleanup)
            
            log("✅ Все проверки пройдены", "🔹 main")
            
        except Exception as e:
            log(f"Ошибка при асинхронных проверках: {e}", "❌ ERROR")
            if hasattr(window, 'set_status'):
                window.set_status(f"Ошибка проверок: {e}")

    # Запускаем проверки через 100ms после показа окна
    QTimer.singleShot(100, async_startup_checks)
    
    # Exception handler
    def global_exception_handler(exctype, value, traceback):
        import traceback as tb
        error_msg = ''.join(tb.format_exception(exctype, value, traceback))
        log(f"UNCAUGHT EXCEPTION: {error_msg}", level="❌ CRITICAL")

    sys.excepthook = global_exception_handler
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
