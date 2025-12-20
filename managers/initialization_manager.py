# managers/initialization_manager.py

from PyQt6.QtCore import QTimer, QThread, QObject, pyqtSignal
from log import log


class InitializationManager:
    """
    Менеджер управления асинхронной инициализацией приложения.
    Делает плановую загрузку компонентов и выполняет «мягкую» верификацию
    (несколько попыток с дедлайном), чтобы избежать ложных предупреждений.
    """

    def __init__(self, app_instance):
        self.app = app_instance
        self.init_tasks_completed = set()

        # Служебные флаги/счетчики для мягкой верификации
        self._verify_done = False
        self._verify_attempts = 0
        self._verify_max_attempts = 8       # Максимум 8 попыток
        self._verify_interval_ms = 1000     # Интервал 1 сек
        self._verify_timer_started = False
        self._post_init_scheduled = False

        # Для фоновой проверки ipsets, чтобы можно было корректно завершить поток
        self._ipsets_thread = None

    # ───────────────────────── запуск и планирование ─────────────────────────

    def run_async_init(self):
        """Полностью асинхронная инициализация с оптимизированным порядком загрузки.
        
        Порядок загрузки оптимизирован по зависимостям:
        
        ФАЗА 1 (0-50ms): Критичные компоненты UI
        - DPI Starter → нужен для состояния кнопок
        - DPI Controller → управление DPI
        - Меню и сигналы → UI готов к взаимодействию
        
        ФАЗА 2 (60-100ms): Менеджеры (параллельно где возможно)
        - Core: DPI Manager, Process Monitor
        - Network: Discord, Hosts, DNS
        - Content: Strategy Manager
        - Theme: ThemeManager (асинхронная генерация CSS)
        
        ФАЗА 3 (100-200ms): Фоновые сервисы
        - Tray, Logger, Update Manager
        
        ФАЗА 4 (200+ms): Отложенные проверки
        - Hostlists, IPsets (не критичны для UI)
        - Подписка
        """
        log("🟡 InitializationManager: начало оптимизированной инициализации", "DEBUG")
        
        self.app.set_status("Инициализация компонентов...")

        # ═══════════════════════════════════════════════════════════════
        # ФАЗА 1: Критичные компоненты UI (быстрые, нужны для отображения)
        # ═══════════════════════════════════════════════════════════════
        init_tasks = [
            (0,   self._init_dpi_starter),        # Быстро, нужен для кнопок
            (10,  self._init_dpi_controller),     # Зависит от dpi_starter
            (20,  self._init_menu),               # UI элементы
            (30,  self._connect_signals),         # Связываем UI
        ]
        
        # ═══════════════════════════════════════════════════════════════
        # ФАЗА 2: Менеджеры (основная логика приложения)
        # ═══════════════════════════════════════════════════════════════
        init_tasks.extend([
            (50,  self._init_core_managers),      # DPI, Process Monitor
            (60,  self._init_network_managers),   # Discord, Hosts, DNS
            (70,  self._init_strategy_manager),   # Стратегии (локально)
            (80,  self._init_theme_manager),      # Тема (асинхронно)
            (90,  self._init_service_managers),   # Service, Update
        ])
        
        # ═══════════════════════════════════════════════════════════════
        # ФАЗА 3: Фоновые сервисы (не критичны для UI)
        # ═══════════════════════════════════════════════════════════════
        init_tasks.extend([
            (100, self._init_tray),               # Системный трей
            (120, self._init_strategy_cache),     # Прогрев кэша стратегий
            (150, self._init_logger),             # Логирование
            (200, self._finalize_managers_init),  # Финализация
        ])
        
        # ═══════════════════════════════════════════════════════════════
        # ФАЗА 4: Отложенные проверки (могут быть медленными)
        # ═══════════════════════════════════════════════════════════════
        init_tasks.extend([
            (300,  self._init_hostlists_check),   # Проверка hostlists
            (400,  self._init_ipsets_check),      # Проверка ipsets
            (2000, self._init_subscription_check),# Проверка подписки (сеть)
        ])

        for delay, task in init_tasks:
            log(f"🟡 Планируем {task.__name__} через {delay}ms", "DEBUG")
            QTimer.singleShot(delay, task)

        # Мягкая верификация с повторами
        if not self._verify_timer_started:
            self._verify_timer_started = True
            QTimer.singleShot(1500, self._verify_initialization)

    # ───────────────────────── инициализация подсистем ───────────────────────

    def _init_strategy_manager(self):
        """Быстрая синхронная инициализация Strategy Manager (локально)"""
        try:
            # ВАЖНО: импортируем из 'strategy_menu.bat_zapret1_manager', чтобы избежать побочных эффектов
            from strategy_menu.bat_zapret1_manager import BatZapret1Manager
            from config import STRATEGIES_FOLDER, INDEXJSON_FOLDER
            import os

            os.makedirs(STRATEGIES_FOLDER, exist_ok=True)

            self.app.strategy_manager = BatZapret1Manager(
                local_dir=STRATEGIES_FOLDER,
                json_dir=INDEXJSON_FOLDER,
                status_callback=self.app.set_status,
                preload=False
            )
            # Работаем только с локальными стратегиями на старте
            self.app.strategy_manager.local_only_mode = True

            log("Strategy Manager инициализирован (без загрузки из интернета)", "INFO")
            self.init_tasks_completed.add('strategy_manager')

        except Exception as e:
            log(f"Ошибка инициализации Strategy Manager: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка: {e}")

    def _init_strategy_cache(self):
        """Прогрев кэша стратегий для быстрого открытия вкладок"""
        try:
            from strategy_menu import get_direct_strategy_selections
            from strategy_menu.strategies_registry import registry

            # Прогреваем кэш отсортированных ключей
            registry.get_all_category_keys_sorted()

            # Прогреваем кэш выборов стратегий
            get_direct_strategy_selections()

            log("Кэш стратегий прогрет", "DEBUG")

        except Exception as e:
            log(f"Ошибка прогрева кэша стратегий: {e}", "WARNING")

    def _init_dpi_starter(self):
        """Инициализация DPI стартера"""
        try:
            from dpi.bat_start import BatDPIStart
            from config import get_winws_exe_for_method, is_zapret2_mode
            from strategy_menu import get_strategy_launch_method

            # Выбираем исполняемый файл в зависимости от режима запуска
            launch_method = get_strategy_launch_method()
            winws_exe = get_winws_exe_for_method(launch_method)
            if is_zapret2_mode(launch_method):
                log(f"Используется winws2.exe для режима {launch_method} (Zapret 2)", "INFO")
            else:
                log("Используется winws.exe для BAT режима (Zapret 1)", "INFO")

            self.app.dpi_starter = BatDPIStart(
                winws_exe=winws_exe,
                status_callback=self.app.set_status,
                ui_callback=self._safe_ui_update,  # безопасный вызов в UI
                app_instance=self.app
            )
            log("DPI Starter инициализирован", "INFO")
            self.init_tasks_completed.add('dpi_starter')
        except Exception as e:
            log(f"Ошибка инициализации DPI Starter: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка DPI: {e}")

    def _safe_ui_update(self, running: bool):
        """Безопасное обновление UI через UI Manager"""
        if hasattr(self.app, 'ui_manager'):
            try:
                self.app.ui_manager.update_ui_state(running)
            except Exception as e:
                log(f"Ошибка при обновлении UI: {e}", "❌ ERROR")
        else:
            # Fallback, если UI Manager еще не готов
            if hasattr(self.app, 'update_ui'):
                try:
                    self.app.update_ui(running)
                except Exception as e:
                    log(f"Ошибка при обновлении UI (fallback): {e}", "❌ ERROR")

    def _init_hostlists_check(self):
        """Синхронная проверка и создание хостлистов"""
        try:
            log("🔧 Начинаем проверку хостлистов", "DEBUG")
            from utils.hostlists_manager import startup_hostlists_check
            result = startup_hostlists_check()
            if result:
                log("✅ Хостлисты проверены и готовы", "SUCCESS")
            else:
                log("⚠️ Проблемы с хостлистами, создаем минимальные", "WARNING")
            self.init_tasks_completed.add('hostlists')
        except Exception as e:
            log(f"❌ Ошибка проверки хостлистов: {e}", "ERROR")

    def _init_ipsets_check(self):
        """Синхронная проверка IPsets"""
        try:
            log("🔧 Начинаем проверку IPsets", "DEBUG")
            from utils.ipsets_manager import startup_ipsets_check
            result = startup_ipsets_check()
            if result:
                log("✅ IPsets проверены и готовы", "SUCCESS")
            else:
                log("⚠️ Проблемы с IPsets, создаем минимальные", "WARNING")
            self.init_tasks_completed.add('ipsets')
        except Exception as e:
            log(f"❌ Ошибка проверки IPsets: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")

    def _init_dpi_controller(self):
        """Инициализация DPI контроллера"""
        try:
            from dpi.dpi_controller import DPIController
            self.app.dpi_controller = DPIController(self.app)
            log("DPI Controller инициализирован", "INFO")
            self.init_tasks_completed.add('dpi_controller')
        except Exception as e:
            log(f"Ошибка инициализации DPI Controller: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка контроллера: {e}")

    def _init_menu(self):
        """Инициализация меню"""
        try:
            from altmenu.app_menubar import AppMenuBar
            from PyQt6.QtWidgets import QWidget, QHBoxLayout
            
            self.app.menu_bar = AppMenuBar(self.app)
            
            # ✅ Добавляем меню под titlebar в отдельном контейнере
            if hasattr(self.app, 'container') and self.app.container.layout():
                # Создаем контейнер для меню (с явным родителем!)
                menubar_widget = QWidget(self.app.container)  # ✅ Родитель = container
                menubar_widget.setObjectName("menubarWidget")
                menubar_widget.setFixedHeight(28)
                menubar_widget.setStyleSheet("""
                    QWidget#menubarWidget {
                        background-color: rgba(20, 20, 20, 240);
                        border-bottom: 1px solid rgba(80, 80, 80, 200);
                    }
                """)
                
                menubar_layout = QHBoxLayout(menubar_widget)
                menubar_layout.setContentsMargins(8, 0, 8, 0)
                menubar_layout.setSpacing(0)
                
                # Стилизуем menubar
                self.app.menu_bar.setStyleSheet("""
                    QMenuBar {
                        background-color: transparent;
                        color: #ffffff;
                        border: none;
                        padding: 0px;
                        spacing: 0px;
                        font-size: 11px;
                        font-family: 'Segoe UI', Arial, sans-serif;
                    }
                    QMenuBar::item {
                        background-color: transparent;
                        color: #ffffff;
                        padding: 4px 10px;
                        border-radius: 4px;
                        margin: 2px 1px;
                    }
                    QMenuBar::item:selected {
                        background-color: #333333;
                    }
                    QMenuBar::item:pressed {
                        background-color: #404040;
                    }
                    QMenu {
                        background-color: #252525;
                        border: 1px solid #3d3d3d;
                        border-radius: 6px;
                        padding: 4px;
                    }
                    QMenu::item {
                        padding: 6px 24px 6px 12px;
                        border-radius: 4px;
                        color: #ffffff;
                    }
                    QMenu::item:selected {
                        background-color: #333333;
                    }
                    QMenu::separator {
                        height: 1px;
                        background-color: #3d3d3d;
                        margin: 4px 8px;
                    }
                """)
                
                menubar_layout.addWidget(self.app.menu_bar)
                menubar_layout.addStretch()
                
                # Вставляем после titlebar (индекс 1)
                container_layout = self.app.container.layout()
                container_layout.insertWidget(1, menubar_widget)
                
                # Сохраняем ссылку для обновления стилей при смене темы
                self.app.menubar_widget = menubar_widget
                
                log("Меню добавлено под titlebar", "INFO")
            else:
                # Fallback для старого поведения
                if self.app.layout():
                    self.app.layout().setMenuBar(self.app.menu_bar)
                log("Меню инициализировано (fallback)", "INFO")
                
            self.init_tasks_completed.add('menu')
        except Exception as e:
            log(f"Ошибка инициализации меню: {e}", "❌ ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")

    def _connect_signals(self):
        """Подключение всех сигналов"""
        try:
            self.app.start_clicked.connect(self._on_start_clicked)
            self.app.stop_clicked.connect(lambda: self.app.dpi_controller.stop_dpi_async())
            self.app.theme_changed.connect(self.app.change_theme)
            self.app.open_folder_btn.clicked.connect(self.app.open_folder)
            self.app.test_connection_btn.clicked.connect(self.app.open_connection_test)
            self.app.server_status_btn.clicked.connect(self.app.show_servers_page)
            
            # Сигнал гирлянды (новогоднее оформление)
            if hasattr(self.app, 'appearance_page') and hasattr(self.app.appearance_page, 'garland_changed'):
                self.app.appearance_page.garland_changed.connect(self.app.set_garland_enabled)
            
            # Сигнал снежинок
            if hasattr(self.app, 'appearance_page') and hasattr(self.app.appearance_page, 'snowflakes_changed'):
                self.app.appearance_page.snowflakes_changed.connect(self.app.set_snowflakes_enabled)

            # Сигнал эффекта размытия
            if hasattr(self.app, 'appearance_page') and hasattr(self.app.appearance_page, 'blur_effect_changed'):
                self.app.appearance_page.blur_effect_changed.connect(self.app.set_blur_effect_enabled)

            # Сигнал прозрачности окна
            if hasattr(self.app, 'appearance_page') and hasattr(self.app.appearance_page, 'opacity_changed'):
                self.app.appearance_page.opacity_changed.connect(self.app.set_window_opacity)

            self.init_tasks_completed.add('signals')
        except Exception as e:
            log(f"Ошибка при подключении сигналов: {e}", "❌ ERROR")

    def _on_start_clicked(self):
        """Обработчик нажатия кнопки запуска с проверкой выбранной стратегии"""
        from strategy_menu import get_strategy_launch_method, get_direct_strategy_selections

        launch_method = get_strategy_launch_method()

        # Для режимов direct/direct_orchestra проверяем выбранные категории
        if launch_method in ("direct", "direct_orchestra"):
            selections = get_direct_strategy_selections()
            # Проверяем есть ли хотя бы одна категория не равная 'none'
            has_any = any(v and v != 'none' for v in selections.values())
            if not has_any:
                # Нет выбранных стратегий - перенаправляем на страницу стратегий
                self._navigate_to_strategies()
                self.app.set_status("⚠️ Выберите стратегию для запуска")
                return

        # Для BAT режима проверяем последнюю выбранную стратегию
        elif launch_method == "bat":
            from config.reg import get_last_bat_strategy
            last_strategy = get_last_bat_strategy()
            if not last_strategy or last_strategy == "Автостарт DPI отключен":
                self._navigate_to_strategies()
                self.app.set_status("⚠️ Выберите стратегию для запуска")
                return

        # orchestra режим не требует выбора стратегии - работает автоматически

        # Запускаем DPI
        self.app.dpi_controller.start_dpi_async()

    def _navigate_to_strategies(self):
        """Перенаправляет на страницу выбора стратегий"""
        try:
            if hasattr(self.app, '_navigate_to_strategies'):
                self.app._navigate_to_strategies()
            elif hasattr(self.app, 'side_nav') and hasattr(self.app, 'pages_stack') and hasattr(self.app, 'strategies_page'):
                index = self.app.pages_stack.indexOf(self.app.strategies_page)
                if index >= 0:
                    self.app.side_nav.set_page(index)
        except Exception as e:
            log(f"Ошибка навигации на страницу стратегий: {e}", "DEBUG")

    # ═══════════════════════════════════════════════════════════════════
    # ФАЗА 2: Инициализация менеджеров (разбито на логические группы)
    # ═══════════════════════════════════════════════════════════════════
    
    def _init_core_managers(self):
        """Инициализация ядра: DPI Manager, Process Monitor, файлы"""
        try:
            import time as _t
            t0 = _t.perf_counter()
            
            # Создаем необходимые файлы
            from utils.file_manager import ensure_required_files
            ensure_required_files()
            
            # DPI Manager
            from managers.dpi_manager import DPIManager
            self.app.dpi_manager = DPIManager(self.app)
            
            # Process Monitor
            if hasattr(self.app, 'process_monitor_manager'):
                self.app.process_monitor_manager.initialize_process_monitor()
            self.app.last_strategy_change_time = __import__('time').time()
            
            log(f"✅ Core managers: {(_t.perf_counter() - t0)*1000:.0f}ms", "DEBUG")
            self.init_tasks_completed.add('core_managers')
        except Exception as e:
            log(f"❌ Ошибка core managers: {e}", "ERROR")
    
    def _init_network_managers(self):
        """Инициализация сетевых менеджеров: Discord, Hosts, DNS"""
        try:
            import time as _t
            t0 = _t.perf_counter()
            
            # Discord Manager
            from discord.discord import DiscordManager
            self.app.discord_manager = DiscordManager(status_callback=self.app.set_status)
            
            # Hosts Manager
            from hosts.hosts import HostsManager
            self.app.hosts_manager = HostsManager(status_callback=self.app.set_status)
            
            # DNS UI Manager
            from dns import DNSUIManager, DNSStartupManager
            self.app.dns_ui_manager = DNSUIManager(
                parent=self.app,
                status_callback=self.app.set_status
            )
            
            # Применяем DNS при запуске (асинхронно)
            DNSStartupManager.apply_dns_on_startup_async(status_callback=self.app.set_status)
            
            log(f"✅ Network managers: {(_t.perf_counter() - t0)*1000:.0f}ms", "DEBUG")
            self.init_tasks_completed.add('network_managers')
        except Exception as e:
            log(f"❌ Ошибка network managers: {e}", "ERROR")
    
    def _init_theme_manager(self):
        """Инициализация ThemeManager с асинхронной генерацией темы"""
        try:
            import time as _t
            t0 = _t.perf_counter()
            
            from ui.theme import ThemeManager, ThemeHandler
            from config import THEME_FOLDER
            from PyQt6.QtWidgets import QApplication
            
            # Создаём ThemeManager БЕЗ применения темы
            self.app.theme_manager = ThemeManager(
                app=QApplication.instance(),
                widget=self.app,
                theme_folder=THEME_FOLDER,
                donate_checker=getattr(self.app, 'donate_checker', None),
                apply_on_init=False
            )
            
            # Handler и привязка
            self.app.theme_handler = ThemeHandler(self.app, target_widget=self.app.main_widget)
            self.app.theme_handler.set_theme_manager(self.app.theme_manager)
            self.app.theme_handler.update_available_themes()
            
            # ✅ Получаем текущую тему из theme_manager
            current_theme = self.app.theme_manager.current_theme
            
            # ✅ ВСЕГДА устанавливаем текущую тему и премиум статус в appearance_page
            if hasattr(self.app, 'appearance_page'):
                self.app.appearance_page.set_current_theme(current_theme)
                
                # Устанавливаем премиум статус
                is_premium = False
                if hasattr(self.app, 'donate_checker') and self.app.donate_checker:
                    try:
                        is_premium, _, _ = self.app.donate_checker.check_subscription_status(use_cache=True)
                    except Exception:
                        pass
                self.app.appearance_page.set_premium_status(is_premium)
                log(f"🎨 Установлена текущая тема в галерее: '{current_theme}' (premium={is_premium})", "DEBUG")
            
            # ✅ Проверяем, был ли CSS уже применён синхронно при старте
            if getattr(self.app, '_css_applied_at_startup', False):
                startup_theme = getattr(self.app, '_startup_theme', None)
                
                if startup_theme == current_theme:
                    log(f"⏭️ CSS уже применён при старте для '{current_theme}', пропускаем асинхронное применение", "DEBUG")
                    self.app._theme_pending = False
                    
                    # Помечаем тему как применённую в ThemeManager
                    self.app.theme_manager._theme_applied = True
                    # ✅ Хеш берём от главного окна (CSS применяется к нему)
                    self.app.theme_manager._current_css_hash = hash(self.app.styleSheet())
                    
                    # ✅ Закрываем splash т.к. тема применена
                    if hasattr(self.app, 'splash') and self.app.splash:
                        self.app.splash.set_progress(100, "Готово", "")
                else:
                    # Темы разные - применяем асинхронно
                    log(f"🔄 Тема изменилась: startup='{startup_theme}' -> current='{current_theme}'", "DEBUG")
                    self.app._theme_pending = True
                    self.app.theme_manager.apply_theme_async(
                        persist=True,
                        progress_callback=self._on_theme_progress,
                        done_callback=self._on_theme_ready
                    )
            else:
                # CSS не был применён при старте - применяем асинхронно
                self.app._theme_pending = True
                
                if hasattr(self.app, 'splash') and self.app.splash:
                    self.app.splash.set_progress(40, "Генерация темы...", "")
                
                self.app.theme_manager.apply_theme_async(
                    persist=True,
                    progress_callback=self._on_theme_progress,
                    done_callback=self._on_theme_ready
                )
            
            log(f"✅ Theme manager: {(_t.perf_counter() - t0)*1000:.0f}ms (CSS в фоне)", "DEBUG")
            self.init_tasks_completed.add('theme_manager')
        except Exception as e:
            log(f"❌ Ошибка theme manager: {e}", "ERROR")
    
    def _init_service_managers(self):
        """Инициализация сервисных менеджеров: автозапуск, обновления"""
        try:
            import time as _t
            t0 = _t.perf_counter()
            
            # Service Manager (автозапуск)
            from autostart.checker import CheckerManager
            from config import WINWS_EXE
            
            self.app.service_manager = CheckerManager(
                winws_exe=WINWS_EXE,
                status_callback=self.app.set_status,
                ui_callback=self._safe_ui_update
            )
            
            log(f"✅ Service managers: {(_t.perf_counter() - t0)*1000:.0f}ms", "DEBUG")
            self.init_tasks_completed.add('service_managers')
        except Exception as e:
            log(f"❌ Ошибка service managers: {e}", "ERROR")
    
    def _finalize_managers_init(self):
        """Финализация инициализации менеджеров и обновление UI"""
        try:
            # Обновляем UI состояние
            from autostart.registry_check import is_autostart_enabled
            autostart_exists = is_autostart_enabled()
            
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_autostart_ui(autostart_exists)
                self.app.ui_manager.update_ui_state(running=False)
            
            self.init_tasks_completed.add('managers')
            self._on_managers_init_done()
            log("✅ Managers init finalized", "DEBUG")
        except Exception as e:
            log(f"❌ Ошибка финализации: {e}", "ERROR")

    def _on_theme_progress(self, status: str):
        """Обработчик прогресса генерации темы"""
        try:
            # Обновляем splash если есть
            if hasattr(self.app, 'splash') and self.app.splash:
                self.app.splash.set_progress(45, f"🎨 {status}", "")
        except Exception:
            pass
    
    def _on_theme_ready(self, success: bool, message: str):
        """Обработчик завершения генерации/применения темы"""
        try:
            self.app._theme_pending = False
            
            if success:
                log(f"✅ Тема применена асинхронно: {message}", "DEBUG")
                # Устанавливаем текущую тему в галерее
                if hasattr(self.app, 'appearance_page') and hasattr(self.app, 'theme_manager'):
                    self.app.appearance_page.set_current_theme(self.app.theme_manager.current_theme)
                
                # ✅ Закрываем splash т.к. тема применена
                if hasattr(self.app, 'splash') and self.app.splash:
                    self.app.splash.set_progress(100, "Готово", "")
            else:
                log(f"⚠ Тема не применена: {message}", "WARNING")
        except Exception as e:
            log(f"Ошибка в _on_theme_ready: {e}", "ERROR")

    def _init_tray(self):
        """Инициализация системного трея"""
        try:
            from tray import SystemTrayManager
            from config import ICON_PATH, ICON_TEST_PATH, APP_VERSION, CHANNEL
            from PyQt6.QtGui import QIcon
            from PyQt6.QtWidgets import QApplication
            import os

            icon_path = ICON_TEST_PATH if CHANNEL.lower() == "test" else ICON_PATH
            if not os.path.exists(icon_path):
                icon_path = ICON_PATH

            app_icon = QIcon(icon_path)
            self.app.setWindowIcon(app_icon)
            QApplication.instance().setWindowIcon(app_icon)

            self.app.tray_manager = SystemTrayManager(
                parent=self.app,
                icon_path=os.path.abspath(icon_path),
                app_version=APP_VERSION
            )

            log("Системный трей инициализирован", "INFO")
            self.init_tasks_completed.add('tray')
        except Exception as e:
            log(f"Ошибка инициализации трея: {e}", "❌ ERROR")

    def _init_logger(self):
        """Инициализация отправки логов"""
        try:
            from log import global_logger
            from tgram import FullLogDaemon

            log_path = getattr(global_logger, 'log_file', None)
            if log_path:
                self.app.log_sender = FullLogDaemon(
                    log_path=log_path,
                    interval=1800,  # 30 минут
                    parent=self.app
                )
                log("Логгер инициализирован", "INFO")
            else:
                log("Не удалось инициализировать отправку логов", "⚠ WARNING")
        except Exception as e:
            log(f"Ошибка инициализации логгера: {e}", "ERROR")
    
    def _init_subscription_check(self):
        """Фоновая проверка подписки при запуске"""
        try:
            log("Запуск фоновой проверки подписки...", "DEBUG")
            
            if hasattr(self.app, 'subscription_manager') and self.app.subscription_manager:
                # Запускаем проверку в фоне (silent=True чтобы не показывать уведомления)
                self.app.subscription_manager.check_and_update_subscription(silent=True)
                log("Фоновая проверка подписки завершена", "INFO")
            else:
                log("subscription_manager не инициализирован, повторная попытка через 1с", "WARNING")
                # Повторная попытка через 1 секунду
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(1000, self._init_subscription_check)
        except Exception as e:
            log(f"Ошибка проверки подписки: {e}", "ERROR")

    # ───────────────────────── верификация и пост-задачи ─────────────────────

    def _required_components(self):
        """Список требуемых компонентов для успешного старта"""
        return ['dpi_starter', 'dpi_controller', 'strategy_manager', 'managers']

    def _check_and_complete_initialization(self) -> bool:
        """
        Проверяет, все ли компоненты готовы, и если да — завершает инициализацию:
        - ставит финальный статус
        - запускает отложенные post-init задачи
        - синхронизирует автозапуск
        Возвращает True если всё готово, иначе False.
        """
        required_components = self._required_components()
        missing = [c for c in required_components if c not in self.init_tasks_completed]

        if missing:
            return False

        # Все компоненты готовы
        if not self._verify_done:
            self._verify_done = True
            try:
                self.app.set_status("✅ Инициализация завершена")
            except Exception:
                pass
            log("Все компоненты успешно инициализированы", "✅ SUCCESS")

            # Финальные задачи
            QTimer.singleShot(500, self._post_init_tasks)
            QTimer.singleShot(3000, self._sync_autostart_status)

        return True

    def _verify_initialization(self):
        """
        «Мягкая» верификация: делаем несколько попыток с интервалом.
        Предупреждение показываем только после истечения дедлайна.
        """
        if self._verify_done:
            return

        if self._check_and_complete_initialization():
            return  # все ок

        # Если не готовы — подождём ещё несколько раз
        self._verify_attempts += 1
        required_components = self._required_components()
        missing = [c for c in required_components if c not in self.init_tasks_completed]
        log(
            f"Ожидание инициализации (попытка {self._verify_attempts}/{self._verify_max_attempts}), "
            f"не готовы: {', '.join(missing)}",
            "DEBUG"
        )

        if self._verify_attempts < self._verify_max_attempts:
            QTimer.singleShot(self._verify_interval_ms, self._verify_initialization)
            return

        # Дедлайн истёк — показываем предупреждение
        self._verify_done = True
        error_msg = f"Не инициализированы: {', '.join(missing)}"
        try:
            self.app.set_status(f"⚠️ {error_msg}")
        except Exception:
            pass
        log(error_msg, "❌ ERROR")

        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.app,
                "Неполная инициализация",
                f"Некоторые компоненты не были инициализированы:\n{', '.join(missing)}\n\n"
                "Приложение может работать нестабильно."
            )
        except Exception as e:
            log(f"Не удалось показать предупреждение: {e}", "ERROR")

    def _sync_autostart_status(self):
        """Синхронизирует статус автозапуска с реальным состоянием"""
        try:
            from autostart.registry_check import verify_autostart_status
            real_status = verify_autostart_status()
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_autostart_ui(real_status)
            log(f"Статус автозапуска синхронизирован: {real_status}", "INFO")
        except Exception as e:
            log(f"Ошибка синхронизации автозапуска: {e}", "❌ ERROR")

    def _on_managers_init_done(self):
        """
        Обработчик успешной инициализации менеджеров:
        - запускает Heavy Init (если есть)
        - пытается «завершить» общую инициализацию сразу, без ожидания таймера
        """
        log("Менеджеры инициализированы, запускаем Heavy Init", "✅ SUCCESS")
        try:
            self.app.set_status("Инициализация завершена")
        except Exception:
            pass

        # Heavy Init
        if hasattr(self.app, 'heavy_init_manager'):
            QTimer.singleShot(100, self.app.heavy_init_manager.start_heavy_init)
            log("🔵 Heavy Init запланирован", "DEBUG")
        else:
            log("❌ Heavy Init Manager не найден", "ERROR")

        # Пробуем завершить общую инициализацию уже сейчас
        self._check_and_complete_initialization()

    def _post_init_tasks(self):
        """Задачи после успешной инициализации (запускаются один раз)"""
        if self._post_init_scheduled:
            return
        self._post_init_scheduled = True

        try:
            # Проверка локальных файлов и автозапуск DPI
            if hasattr(self.app, 'heavy_init_manager'):
                if self.app.heavy_init_manager.check_local_files():
                    if hasattr(self.app, 'dpi_manager'):
                        QTimer.singleShot(1000, self.app.dpi_manager.delayed_dpi_start)
            
            # Обновления проверяются вручную на вкладке "Серверы"
                
        except Exception as e:
            log(f"Ошибка post-init задач: {e}", "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")