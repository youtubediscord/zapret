# managers/initialization_manager.py

import threading

from app_notifications import advisory_notification
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from log import log


class _StrategyCacheBridge(QObject):
    summary_ready = pyqtSignal(str, str)


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
        self._strategy_cache_bridge = _StrategyCacheBridge()
        self._strategy_cache_bridge.summary_ready.connect(self._apply_strategy_cache_summary)

    def _log_startup_step(self, marker: str, details: str = "") -> None:
        try:
            if hasattr(self.app, "log_startup_metric"):
                self.app.log_startup_metric(marker, details)
        except Exception:
            pass

    def ensure_tray_initialized(self):
        """Синхронно гарантирует наличие tray manager перед сценарием сворачивания."""
        tray_manager = getattr(self.app, "tray_manager", None)
        if tray_manager is not None:
            return tray_manager

        self._init_tray()
        return getattr(self.app, "tray_manager", None)

    # ───────────────────────── запуск и планирование ─────────────────────────

    def run_async_init(self):
        """Полностью асинхронная инициализация с оптимизированным порядком загрузки.
        
        Порядок загрузки оптимизирован по зависимостям:
        
        ФАЗА 1 (0-50ms): Критичные компоненты UI
        - DPI Starter → нужен для состояния кнопок
        - DPI Controller → управление DPI
        - Меню и сигналы → UI готов к взаимодействию
        
        ФАЗА 2 (50-300ms): Менеджеры ядра и быстрые UI-зависимости
        - Core: DPI Manager и обязательные файлы
        - Content: Strategy Manager
        - Theme: ThemeManager (асинхронная генерация CSS)
        - Service: автозапуск/службы

        ФАЗА 3 (600ms+): Idle-инициализация тяжёлых/необязательных менеджеров
        - Process Monitor
        - Network: Discord, Hosts, DNS
        - Tray, Logger, прогрев кэша

        ФАЗА 4 (1800ms+): Отложенные фоновые проверки
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
            (50,  self._init_core_managers),      # DPI Manager + обязательные файлы
            (70,  self._init_strategy_manager),   # Стратегии (локально)
            (90,  self._init_theme_manager),      # Тема (асинхронно)
            (1400, self._init_service_managers),  # Service, Update
        ])
        
        # ═══════════════════════════════════════════════════════════════
        # ФАЗА 3: Фоновые сервисы (не критичны для UI)
        # ═══════════════════════════════════════════════════════════════
        init_tasks.extend([
            (300, self._finalize_managers_init),  # Финализация
            (2200, self._init_process_monitor),   # Process Monitor (idle)
            (3200, self._init_network_managers),  # Discord, Hosts, DNS (idle)
            (450 if getattr(self.app, "start_in_tray", False) else 4200, self._init_tray),
            (1500, self._init_logger),            # Логирование (idle)
            (5200, self._init_strategy_cache),    # Отложенный прогрев кэша
        ])
        
        # ═══════════════════════════════════════════════════════════════
        # ФАЗА 4: Отложенные проверки (могут быть медленными)
        # ═══════════════════════════════════════════════════════════════
        init_tasks.extend([
            (1800, self._init_hostlists_check),   # Проверка hostlists (в фоне)
            (2000, self._init_ipsets_check),      # Проверка ipsets (в фоне)
            (12000, self._init_subscription_check),# Проверка подписки (сеть, отложено)
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
        """Stub: BAT strategy manager removed — preset-based zapret1 replaces it."""
        # BatZapret1Manager was only used for .bat file strategy management.
        # Zapret1 now uses the preset_zapret1 module for strategy management.
        self.app.strategy_manager = None
        log("Strategy Manager (BAT) отключён — используется preset_zapret1", "DEBUG")
        self.init_tasks_completed.add('strategy_manager')

    def _init_strategy_cache(self):
        """Прогрев кэша стратегий для быстрого открытия вкладок"""
        def _worker() -> None:
            import time as _t
            t0 = _t.perf_counter()
            try:
                from legacy_registry_launch.strategies_registry import registry
                from strategy_menu import get_strategy_launch_method

                # Прогреваем кэш отсортированных ключей
                registry.get_all_target_keys_sorted()

                method = get_strategy_launch_method()

                # Прогреваем кэш выборов/source preset для текущего режима.
                if method in ("direct_zapret1", "direct_zapret2"):
                    from core.presets.direct_facade import DirectPresetFacade

                    DirectPresetFacade.from_launch_method(method).get_strategy_selections()
                else:
                    from legacy_registry_launch.selection_store import get_direct_strategy_selections

                    get_direct_strategy_selections()

                log("Кэш стратегий прогрет", "DEBUG")
                self._log_startup_step(
                    "StrategyCacheWarmup",
                    f"{(_t.perf_counter() - t0) * 1000:.0f}ms",
                )

                strategy_summary = self._resolve_strategy_cache_summary(method)
                self._strategy_cache_bridge.summary_ready.emit(str(method or ""), str(strategy_summary or ""))
            except Exception as e:
                log(f"Ошибка прогрева кэша стратегий: {e}", "WARNING")

        threading.Thread(target=_worker, daemon=True, name="StrategyCacheWarmupWorker").start()

    def _resolve_strategy_cache_summary(self, method: str) -> str:
        """Считает итоговую строку стратегии без выполнения UI-кода в рабочем потоке."""
        try:
            # Убедимся, что выбранные source-пресеты подготовлены до расчёта summary.
            if method == "direct_zapret2":
                from core.services import get_direct_flow_coordinator

                try:
                    get_direct_flow_coordinator().ensure_selected_source_path("direct_zapret2")
                except Exception as e:
                    log(
                        f"direct_zapret2: не удалось подготовить выбранный source-пресет: {e}",
                        "ERROR",
                    )
            elif method == "direct_zapret2_orchestra":
                from preset_orchestra_zapret2 import ensure_default_preset_exists

                if not ensure_default_preset_exists():
                    log(
                        "direct_zapret2_orchestra: не удалось подготовить preset-zapret2-orchestra.txt (нет шаблона Default)",
                        "ERROR",
                    )
            elif method == "direct_zapret1":
                from core.services import get_direct_flow_coordinator

                try:
                    get_direct_flow_coordinator().ensure_selected_source_path("direct_zapret1")
                except Exception:
                    log("direct_zapret1: не удалось подготовить выбранный source-пресет", "ERROR")

            if method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                from ui.main_window_display import get_direct_strategy_summary

                return get_direct_strategy_summary(self.app)
        except Exception as e:
            log(f"Ошибка расчёта стартового summary стратегии: {e}", "DEBUG")

        initial_name = ""
        store = getattr(self.app, "ui_state_store", None)
        if store is not None:
            try:
                initial_name = store.snapshot().current_strategy_summary or ""
            except Exception:
                initial_name = ""

        if initial_name:
            return initial_name
        if method == "orchestra":
            return "Оркестр"
        return "Прямой запуск"

    def _apply_strategy_cache_summary(self, launch_method: str, strategy_summary: str) -> None:
        """Возвращает результат прогрева в единый store уже в GUI-потоке."""
        try:
            store = getattr(self.app, "ui_state_store", None)
            if store is None:
                return

            store.set_current_strategy_summary(strategy_summary)
        except Exception as e:
            log(f"Ошибка применения стартового summary стратегии: {e}", "DEBUG")

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
                # Ensure default preset exists for direct_zapret2 mode
                if launch_method == "direct_zapret2":
                    from core.services import get_direct_flow_coordinator
                    try:
                        get_direct_flow_coordinator().ensure_selected_source_path("direct_zapret2")
                    except Exception as e:
                        log(
                            f"direct_zapret2: не удалось подготовить выбранный source-пресет: {e}",
                            "ERROR",
                        )
                        try:
                            self.app.set_status(f"Ошибка: не удалось подготовить выбранный пресет: {e}")
                        except Exception:
                            pass
                elif launch_method == "direct_zapret2_orchestra":
                    from preset_orchestra_zapret2 import ensure_default_preset_exists
                    if not ensure_default_preset_exists():
                        log(
                            "direct_zapret2_orchestra: не удалось подготовить preset-zapret2-orchestra.txt (нет шаблона Default)",
                            "ERROR",
                        )
                        try:
                            self.app.set_status("Ошибка: отсутствует Default шаблон оркестра")
                        except Exception:
                            pass
            else:
                log(f"Используется winws.exe для режима {launch_method}", "INFO")
                # Ensure default preset exists for direct_zapret1 mode
                if launch_method == "direct_zapret1":
                    from core.services import get_direct_flow_coordinator
                    try:
                        get_direct_flow_coordinator().ensure_selected_source_path("direct_zapret1")
                    except Exception:
                        log("direct_zapret1: не удалось подготовить выбранный source-пресет", "ERROR")
                        try:
                            self.app.set_status("Ошибка: не удалось подготовить выбранный пресет")
                        except Exception:
                            pass

            self.app.dpi_starter = BatDPIStart(
                winws_exe=winws_exe,
                status_callback=self.app.set_status,
                app_instance=self.app
            )
            log("DPI Starter инициализирован", "INFO")
            self.init_tasks_completed.add('dpi_starter')
        except Exception as e:
            log(f"Ошибка инициализации DPI Starter: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка DPI: {e}")

    def _handle_startup_dns_status(self, message: str) -> None:
        """Фильтрует служебные DNS-статусы, чтобы они не выглядели как главный статус приложения."""
        text = str(message or "").strip()
        if not text:
            return

        silent_prefixes = (
            "DNS будет применен",
            "⚙️ Принудительный DNS отключен",
            "⏳ Применение DNS настроек",
        )
        if text.startswith(silent_prefixes):
            log(f"DNS startup status suppressed from main status: {text}", "DEBUG")
            return

        try:
            self.app.set_status(text)
        except Exception:
            pass

    def _init_hostlists_check(self):
        """Фоновая проверка и создание хостлистов (не блокирует GUI)."""

        def _worker() -> None:
            try:
                log("🔧 Начинаем проверку хостлистов (background)", "DEBUG")
                from utils.hostlists_manager import startup_hostlists_check

                result = startup_hostlists_check()
                if result:
                    log("✅ Хостлисты проверены и готовы", "SUCCESS")
                else:
                    log("⚠️ Проблемы с хостлистами, создаем минимальные", "WARNING")
                self.init_tasks_completed.add('hostlists')
            except Exception as e:
                log(f"❌ Ошибка проверки хостлистов: {e}", "ERROR")

        threading.Thread(target=_worker, daemon=True, name="HostlistsCheckWorker").start()

    def _init_ipsets_check(self):
        """Фоновая проверка IPsets (не блокирует GUI)."""

        def _worker() -> None:
            try:
                log("🔧 Начинаем проверку IPsets (background)", "DEBUG")
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

        threading.Thread(target=_worker, daemon=True, name="IPsetsCheckWorker").start()

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
        # Alt-меню отключено: все настройки/ссылки перенесены в страницы интерфейса.
        try:
            self.init_tasks_completed.add('menu')
            log("Alt-меню отключено (перенесено в страницы)", "INFO")
        except Exception as e:
            log(f"Ошибка отключения меню: {e}", "❌ ERROR")

    def _connect_signals(self):
        """Подключение всех сигналов"""
        try:
            self.app._start_requested_handler = self._on_start_clicked
            
            self.init_tasks_completed.add('signals')

            # Фиксируем метрику "interactive": базовые сигналы UI уже подключены.
            try:
                if hasattr(self.app, '_mark_startup_interactive'):
                    self.app._mark_startup_interactive("signals_connected")
            except Exception:
                pass
        except Exception as e:
            log(f"Ошибка при подключении сигналов: {e}", "❌ ERROR")

    def _on_start_clicked(self):
        """Обработчик нажатия кнопки запуска с проверкой выбранной стратегии"""
        from strategy_menu import get_strategy_launch_method

        launch_method = get_strategy_launch_method()

        # Для новых direct режимов проверяем сам source preset, а не legacy selections dict.
        if launch_method in ("direct_zapret2", "direct_zapret1"):
            from core.services import get_direct_flow_coordinator

            try:
                get_direct_flow_coordinator().ensure_launch_profile(launch_method, require_filters=True)
            except Exception:
                self._show_strategy_required_warning(for_bat=False)
                self.app.set_status("⚠️ Выберите стратегию для запуска")
                return

        # Для orchestra direct-режима пока остаётся legacy selections path.
        elif launch_method == "direct_zapret2_orchestra":
            from legacy_registry_launch.selection_store import get_direct_strategy_selections

            selections = get_direct_strategy_selections()
            has_any = any(v and v != 'none' for v in selections.values())
            if not has_any:
                self._show_strategy_required_warning(for_bat=False)
                self.app.set_status("⚠️ Выберите стратегию для запуска")
                return

        # orchestra режим не требует выбора стратегии - работает автоматически

        # Запускаем DPI
        self.app.dpi_controller.start_dpi_async()

    def _show_strategy_required_warning(self, for_bat: bool = False) -> None:
        """Показывает popup-предупреждение без смены текущей страницы."""
        if for_bat:
            subtitle = (
                "Для запуска Zapret выберите готовый пресет в разделе «Стратегии»."
            )
        else:
            subtitle = (
                "Для запуска Zapret выберите хотя бы одну стратегию "
                "в разделе «Стратегии»."
            )

        try:
            from ui.start_strategy_warning_dialog import show_start_strategy_warning

            show_start_strategy_warning(parent=self.app, subtitle=subtitle)
            return
        except Exception as e:
            log(f"Не удалось открыть фирменное предупреждение запуска: {e}", "DEBUG")

        try:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self.app, "Стратегия не выбрана", subtitle)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════
    # ФАЗА 2: Инициализация менеджеров (разбито на логические группы)
    # ═══════════════════════════════════════════════════════════════════
    
    def _init_core_managers(self):
        """Инициализация ядра: DPI Manager и обязательные файлы."""
        try:
            import time as _t
            t0 = _t.perf_counter()
            
            # Создаем необходимые файлы
            from utils.file_manager import ensure_required_files
            ensure_required_files()
            
            # DPI Manager
            if not getattr(self.app, 'dpi_manager', None):
                from managers.dpi_manager import DPIManager
                self.app.dpi_manager = DPIManager(self.app)
            
            self.app.last_strategy_change_time = __import__('time').time()
            
            log(f"✅ Core managers: {(_t.perf_counter() - t0)*1000:.0f}ms", "DEBUG")
            self.init_tasks_completed.add('core_managers')
        except Exception as e:
            log(f"❌ Ошибка core managers: {e}", "ERROR")

    def _init_process_monitor(self):
        """Отложенный запуск Process Monitor после первой интерактивности UI."""
        try:
            import time as _t
            t0 = _t.perf_counter()

            if hasattr(self.app, 'process_monitor_manager'):
                self.app.process_monitor_manager.initialize_process_monitor()

            try:
                runtime_service = getattr(self.app, "dpi_runtime_service", None)
                dpi_starter = getattr(self.app, "dpi_starter", None)
                if runtime_service is not None and dpi_starter is not None:
                    from config import get_winws_exe_for_method
                    from strategy_menu import get_strategy_launch_method
                    import os

                    launch_method = str(get_strategy_launch_method() or "").strip().lower()
                    expected_process = ""
                    if launch_method != "orchestra":
                        expected_process = os.path.basename(get_winws_exe_for_method(launch_method)).strip().lower()
                    runtime_service.bootstrap_probe(
                        bool(dpi_starter.check_process_running_wmi(silent=True)),
                        launch_method=launch_method,
                        expected_process=expected_process,
                    )
            except Exception:
                pass

            log(f"✅ Process monitor: {(_t.perf_counter() - t0)*1000:.0f}ms", "DEBUG")
            self.init_tasks_completed.add('process_monitor')
        except Exception as e:
            log(f"❌ Ошибка process monitor: {e}", "ERROR")
    
    def _init_network_managers(self):
        """Инициализация сетевых менеджеров: Discord, Hosts, DNS"""
        try:
            import time as _t
            t0 = _t.perf_counter()
            
            # Discord Manager
            if not getattr(self.app, 'discord_manager', None):
                from discord.discord import DiscordManager
                self.app.discord_manager = DiscordManager(status_callback=self.app.set_status)
            
            # Hosts Manager
            if not getattr(self.app, 'hosts_manager', None):
                from hosts.hosts import HostsManager
                self.app.hosts_manager = HostsManager(status_callback=self.app.set_status)
            
            # DNS UI Manager
            if not getattr(self.app, 'dns_ui_manager', None):
                from dns import DNSUIManager, DNSStartupManager

                self.app.dns_ui_manager = DNSUIManager(
                    parent=self.app,
                    status_callback=self.app.set_status
                )

                # Применяем DNS при запуске (асинхронно)
                DNSStartupManager.apply_dns_on_startup_async(status_callback=self._handle_startup_dns_status)
            
            log(f"✅ Network managers: {(_t.perf_counter() - t0)*1000:.0f}ms", "DEBUG")
            self._log_startup_step("NetworkManagers", f"{(_t.perf_counter() - t0)*1000:.0f}ms")
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
            self.app.theme_handler = ThemeHandler(self.app, target_widget=self.app)
            self.app.theme_handler.set_theme_manager(self.app.theme_manager)
            self.app.theme_handler.update_available_themes()
            
            # ✅ Получаем текущую тему из theme_manager
            current_theme = self.app.theme_manager.current_theme
            is_premium = False
            if hasattr(self.app, 'donate_checker') and self.app.donate_checker:
                try:
                    is_premium, _, _ = self.app.donate_checker.check_subscription_status(use_cache=True)
                except Exception:
                    pass
            log(f"🎨 Тема инициализирована: '{current_theme}' (premium={is_premium})", "DEBUG")
            
            # ✅ qfluentwidgets manages ALL styling via setTheme(DARK/LIGHT/AUTO).
            # Legacy qt-material CSS (overlay_css) conflicts with FluentWindow's internal
            # theming: applying it via main_window.setStyleSheet() injects hardcoded dark-mode
            # QLabel colors (color: rgba(255,255,255,0.87)) that persist when the user
            # switches to Light mode → white text on white background.
            # Solution: skip apply_theme_async() entirely.
            log(f"⏭️ Применение CSS пропущено — qfluentwidgets управляет стилями нативно", "DEBUG")
            
            log(f"✅ Theme manager: {(_t.perf_counter() - t0)*1000:.0f}ms (CSS в фоне)", "DEBUG")
            self.init_tasks_completed.add('theme_manager')
        except Exception as e:
            log(f"❌ Ошибка theme manager: {e}", "ERROR")
    
    def _init_service_managers(self):
        """Инициализация сервисных менеджеров: автозапуск, обновления"""
        try:
            import time as _t
            t0 = _t.perf_counter()

            if getattr(self.app, 'service_manager', None):
                self.init_tasks_completed.add('service_managers')
                log("Service managers уже инициализированы, пропускаем", "DEBUG")
                return
            
            # Service Manager (автозапуск)
            from autostart.checker import CheckerManager
            from config import WINWS_EXE
            
            self.app.service_manager = CheckerManager(
                winws_exe=WINWS_EXE,
                status_callback=self.app.set_status
            )
            
            log(f"✅ Service managers: {(_t.perf_counter() - t0)*1000:.0f}ms", "DEBUG")
            self._log_startup_step("ServiceManagers", f"{(_t.perf_counter() - t0)*1000:.0f}ms")
            self.init_tasks_completed.add('service_managers')
        except Exception as e:
            log(f"❌ Ошибка service managers: {e}", "ERROR")
    
    def _finalize_managers_init(self):
        """Финализация инициализации менеджеров и обновление UI"""
        try:
            # Обновляем UI состояние
            from autostart.registry_check import is_autostart_enabled
            autostart_exists = is_autostart_enabled()

            app_runtime_state = getattr(self.app, "app_runtime_state", None)
            if app_runtime_state is not None:
                app_runtime_state.apply_runtime_state(
                    autostart_enabled=bool(autostart_exists),
                )

            self.init_tasks_completed.add('managers')
            self._on_managers_init_done()
            log("✅ Managers init finalized", "DEBUG")
        except Exception as e:
            log(f"❌ Ошибка финализации: {e}", "ERROR")

    def _init_tray(self):
        """Инициализация системного трея"""
        try:
            import time as _t
            t0 = _t.perf_counter()
            if getattr(self.app, 'tray_manager', None):
                self.init_tasks_completed.add('tray')
                log("Системный трей уже инициализирован, пропускаем", "DEBUG")
                return

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
            self._log_startup_step("TrayInit", f"{(_t.perf_counter() - t0)*1000:.0f}ms")
            self.init_tasks_completed.add('tray')

            if bool(getattr(self.app, "_tray_launch_notification_pending", False)):
                controller = getattr(self.app, "window_notification_controller", None)
                if controller is not None:
                    controller.notify(
                        advisory_notification(
                            level="info",
                            title="Zapret работает в трее",
                            content="Приложение запущено в фоновом режиме",
                            source="startup.tray_launch",
                            presentation="infobar",
                            queue="immediate",
                            duration=5000,
                            dedupe_key="startup.tray_launch",
                            tray_title="Zapret работает в трее",
                            tray_content="Приложение запущено в фоновом режиме",
                        )
                    )
                self.app._tray_launch_notification_pending = False
        except Exception as e:
            log(f"Ошибка инициализации трея: {e}", "❌ ERROR")

    def _init_logger(self):
        """Автоматическая отправка логов отключена.
        Логи можно отправить вручную через UI (страница Логи → Отправить)."""
        pass
    
    def _init_subscription_check(self):
        """Фоновая проверка подписки при запуске"""
        try:
            log("Запуск фоновой проверки подписки...", "DEBUG")
            
            if hasattr(self.app, 'subscription_manager') and self.app.subscription_manager:
                # Не дублируем сетевые проверки: если первичная инициализация уже
                # выполняется или завершилась, дополнительная проверка не нужна.
                if bool(getattr(self.app, '_startup_subscription_ready', False)):
                    log("Фоновая проверка подписки пропущена: первичная проверка уже завершена", "DEBUG")
                    return

                init_thread = getattr(self.app.subscription_manager, '_subscription_thread', None)
                try:
                    if init_thread is not None and init_thread.isRunning():
                        log("Фоновая проверка подписки пропущена: идет первичная инициализация", "DEBUG")
                        return
                except RuntimeError:
                    pass

                # Запускаем проверку в фоне (silent=True чтобы не показывать уведомления)
                started = self.app.subscription_manager.check_and_update_subscription_async(silent=True)
                if started:
                    log("Фоновая проверка подписки запущена", "INFO")
                else:
                    log("Фоновая проверка подписки отложена: donate_checker еще не готов", "DEBUG")
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

    def _get_post_init_delay_ms(self) -> int:
        """Возвращает задержку перед post-init задачами."""
        try:
            from strategy_menu import get_strategy_launch_method

            # Для direct-режимов запускаем post-init почти сразу:
            # искусственная пауза в 500ms только раздувает Startup PostInitDone
            # и делает старт окна визуально более "вязким", хотя компоненты уже готовы.
            if get_strategy_launch_method() in ("direct_zapret2", "direct_zapret1"):
                return 75
        except Exception:
            pass

        return 500

    def _get_dpi_autostart_delay_ms(self, launch_method: str) -> int:
        """Возвращает задержку перед автозапуском DPI по режиму."""
        if launch_method == "direct_zapret2":
            return 75
        return 1000

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
            QTimer.singleShot(self._get_post_init_delay_ms(), self._post_init_tasks)
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
            import time as _t
            t0 = _t.perf_counter()
            from autostart.registry_check import verify_autostart_status
            real_status = verify_autostart_status()
            app_runtime_state = getattr(self.app, "app_runtime_state", None)
            if app_runtime_state is not None:
                app_runtime_state.set_autostart(bool(real_status))
            log(f"Статус автозапуска синхронизирован: {real_status}", "INFO")
            self._log_startup_step("AutostartSync", f"{(_t.perf_counter() - t0)*1000:.0f}ms")
        except Exception as e:
            log(f"Ошибка синхронизации автозапуска: {e}", "❌ ERROR")

    def _on_managers_init_done(self):
        """
        Обработчик успешной инициализации менеджеров:
        - обновляет статус
        - завершает общую инициализацию
        """
        log("Менеджеры инициализированы", "✅ SUCCESS")
        try:
            if hasattr(self.app, '_mark_startup_managers_ready'):
                self.app._mark_startup_managers_ready("initialization_manager")
        except Exception:
            pass

        try:
            self.app.set_status("Инициализация завершена")
        except Exception:
            pass

        # Пробуем завершить общую инициализацию уже сейчас
        self._check_and_complete_initialization()

    def _post_init_tasks(self):
        """Задачи после успешной инициализации (запускаются один раз)"""
        if self._post_init_scheduled:
            return
        self._post_init_scheduled = True
        post_init_metric_source = "post_init_ok"

        try:
            # Проверка winws.exe
            if not self._check_winws_exists():
                log("winws.exe не найден", "❌ ERROR")
                self.app.set_status("❌ winws.exe не найден")
                post_init_metric_source = "post_init_winws_missing"
                return

            log("✅ winws.exe найден", "DEBUG")

            # Проверяем режим запуска ПЕРЕД делегированием
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            autostart_delay_ms = self._get_dpi_autostart_delay_ms(launch_method)

            if launch_method == "direct_zapret2":
                # Отдельный путь для direct_zapret2 (использует preset файл)
                QTimer.singleShot(autostart_delay_ms, self._start_direct_zapret2_autostart)
            else:
                # Все остальные режимы через dpi_manager
                if hasattr(self.app, 'dpi_manager'):
                    QTimer.singleShot(autostart_delay_ms, self.app.dpi_manager.delayed_dpi_start)

            # Обновления проверяются вручную на вкладке "Серверы"

        except Exception as e:
            post_init_metric_source = f"post_init_error:{type(e).__name__}"
            log(f"Ошибка post-init задач: {e}", "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
        finally:
            try:
                if hasattr(self.app, '_mark_startup_post_init_done'):
                    self.app._mark_startup_post_init_done(post_init_metric_source)
            except Exception:
                pass

    def _check_winws_exists(self) -> bool:
        """Проверка наличия winws.exe"""
        try:
            import os
            from config import get_winws_exe_for_method
            from strategy_menu import get_strategy_launch_method

            launch_method = get_strategy_launch_method()
            target_file = get_winws_exe_for_method(launch_method)

            return os.path.exists(target_file)

        except Exception as e:
            log(f"Ошибка при проверке winws.exe: {e}", "DEBUG")
            # Fallback на WINWS_EXE
            try:
                from config import WINWS_EXE
                import os
                return os.path.exists(WINWS_EXE)
            except:
                return False

    def _start_direct_zapret2_autostart(self):
        """Автозапуск для режима direct_zapret2 (использует preset файл)"""
        # 1. Проверяем включен ли автозапуск
        from config import get_dpi_autostart
        if not get_dpi_autostart():
            log("Автозапуск DPI отключен", "INFO")
            self.app.set_status("Готово")
            return

        # 2. Проверяем наличие preset файла
        try:
            from core.services import get_direct_flow_coordinator

            profile = get_direct_flow_coordinator().ensure_launch_profile(
                "direct_zapret2",
                require_filters=False,
            )
            preset_path = profile.launch_config_path
            preset_name = profile.preset_name

            if not preset_path.exists():
                log(f"Preset файл не найден: {preset_path}", "ERROR")
                self.app.set_status("Ошибка: preset файл не найден")
                return

            # 3. Формируем selected_mode для запуска из preset файла
            selected_mode = profile.to_selected_mode()

            log(f"Автозапуск direct_zapret2 из выбранного source-пресета: {preset_path}", "INFO")

            # 4. Запускаем через dpi_controller
            if hasattr(self.app, "update_current_strategy_display"):
                self.app.update_current_strategy_display(profile.display_name)
            self.app.dpi_controller.start_dpi_async(
                selected_mode=selected_mode, launch_method="direct_zapret2"
            )

        except Exception as e:
            log(f"Ошибка автозапуска direct_zapret2: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            self.app.set_status(f"Ошибка автозапуска: {e}")
