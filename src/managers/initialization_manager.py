# managers/initialization_manager.py

from dataclasses import dataclass
import threading
import time as _time

from app_notifications import advisory_notification, notification_action
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from log.log import log



class _StrategyCacheBridge(QObject):
    summary_ready = pyqtSignal(str, str)


class _StartupPhaseBridge(QObject):
    continue_phase_two = pyqtSignal()


class _PostInitLaunchBridge(QObject):
    launch_requested = pyqtSignal(str)


@dataclass(frozen=True, slots=True)
class InitializationAppStateTouchpoints:
    ui_state_store_updates: tuple[str, ...]
    app_runtime_state_updates: tuple[str, ...]
    runtime_service_calls: tuple[str, ...]
    infrastructure_calls: tuple[str, ...]


class InitializationManager:
    """
    Менеджер запуска приложения.

    Логика разделена на две стадии:
    1. Минимальный интерактивный контур — только то, без чего окно не может
       быстро показаться и обработать первый клик.
    2. Остальная инициализация — служебные менеджеры, мониторинг, сеть,
       кеши и фоновые проверки.

    Такой разрез нужен, чтобы GUI перестал держать главный поток занятым
    первые 2-3 секунды после появления окна.
    """

    @staticmethod
    def build_app_state_touchpoints() -> InitializationAppStateTouchpoints:
        """Явная карта допустимых app-level интеграций startup-слоя.

        InitializationManager не должен владеть page-level UI state.
        Его допустимые точки касания ограничены общими app/runtime слоями:
        - `ui_state_store` только для window-level summary/revision state;
        - `app_runtime_state` только как узкий facade для launch/autostart reads;
        - `launch_runtime_service` для канонического DPI runtime state;
        - инфраструктурные менеджеры tray/notification/subscription.
        """

        return InitializationAppStateTouchpoints(
            ui_state_store_updates=(
                "_resolve_strategy_cache_summary -> ui_state_store.snapshot().current_strategy_summary",
                "_apply_strategy_cache_summary -> ui_state_store.set_current_strategy_summary(...)",
            ),
            app_runtime_state_updates=(
                "_finalize_managers_init -> app_runtime_state.set_autostart(...)",
                "_sync_autostart_status -> app_runtime_state.set_autostart(...)",
            ),
            runtime_service_calls=(
                "_init_process_monitor -> launch_runtime_service.bootstrap_probe(...)",
            ),
            infrastructure_calls=(
                "ensure_tray_initialized -> _init_tray()",
                "_init_tray -> window_notification_controller.notify(...)",
                "_init_subscription_check -> subscription_manager.check_and_update_subscription_async(...)",
            ),
        )

    def __init__(self, app_instance):
        self.app = app_instance
        self.init_tasks_completed = set()

        # Финализация старта теперь идёт по прямому жизненному циклу, а не через
        # таймерную "проверку готовности".
        self._verify_done = False
        self._post_init_scheduled = False

        # Для фоновой проверки ipsets, чтобы можно было корректно завершить поток
        self._ipsets_thread = None
        self._strategy_cache_bridge = _StrategyCacheBridge()
        self._strategy_cache_bridge.summary_ready.connect(self._apply_strategy_cache_summary)
        self._startup_phase_bridge = _StartupPhaseBridge()
        self._startup_phase_bridge.continue_phase_two.connect(
            self._run_phase_two_init,
            Qt.ConnectionType.QueuedConnection,
        )
        self._phase_two_started = False
        self._post_init_dispatch_started = False
        self._strategy_cache_started = False
        self._post_init_launch_bridge = _PostInitLaunchBridge()
        self._post_init_launch_bridge.launch_requested.connect(
            self._run_deferred_post_init_launch,
            Qt.ConnectionType.QueuedConnection,
        )

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
        """Запускает старт в два этапа без блокировки первого показа окна."""
        log("🟡 InitializationManager: начало оптимизированной инициализации", "DEBUG")
        
        self.app.set_status("Инициализация компонентов...")

        # Фаза 1: только минимальный контур, который нужен для немедленного
        # взаимодействия с окном. Всё остальное — позже отдельным queued-шагом.
        startup_steps = [
            self._init_launch_runtime_api,
            self._init_launch_controller,
            self._init_menu,
            self._connect_signals,
        ]

        for task in startup_steps:
            log(f"🟡 Выполняем {task.__name__} сразу", "DEBUG")
            task()

        self._check_and_complete_initialization()
        self._startup_phase_bridge.continue_phase_two.emit()

    def _run_phase_two_init(self) -> None:
        """Продолжает старт после первого возврата в цикл интерфейса."""
        if self._phase_two_started:
            return
        self._phase_two_started = True

        phase_two_steps = [
            self._init_process_monitor,
            self._init_core_managers,
            self._init_strategy_manager,
            self._init_theme_manager,
            self._init_telegram_proxy_autostart,
            self._init_network_managers,
            self._finalize_managers_init,
        ]

        # Native tray icon should be available for the whole app session,
        # not only after explicit "hide to tray".
        phase_two_steps.append(self._init_tray)

        phase_two_steps.append(self._init_logger)

        for task in phase_two_steps:
            log(f"🟡 Выполняем {task.__name__} после первого показа окна", "DEBUG")
            task()

        # Некритичные тяжёлые операции уже сами уходят в фоновые потоки.
        self._init_hostlists_check()
        self._init_ipsets_check()
        self._init_subscription_check()

        self._check_and_complete_initialization()

    # ───────────────────────── инициализация подсистем ───────────────────────

    def _init_strategy_manager(self):
        """Stub: старый strategy manager удалён — теперь используется direct preset UI."""
        self.app.strategy_manager = None
        log("Legacy strategy manager отключён — используется direct preset UI", "DEBUG")
        self.init_tasks_completed.add('strategy_manager')

    def _init_strategy_cache(self):
        """Прогрев кэша стратегий для быстрого открытия вкладок"""
        def _worker() -> None:
            import time as _t
            t0 = _t.perf_counter()
            try:
                from settings.dpi.strategy_settings import get_strategy_launch_method

                method = get_strategy_launch_method()

                # Прогреваем кэш выборов/source preset только для поддерживаемых direct-режимов.
                if method in ("direct_zapret1", "direct_zapret2"):
                    from direct_preset.facade import DirectPresetFacade

                    DirectPresetFacade.from_launch_method(
                        method,
                        app_context=self.app.app_context,
                    ).get_strategy_selections()
                elif method == "orchestra":
                    pass

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

    def _maybe_start_strategy_cache(self, source: str) -> None:
        """Запускает прогрев кэша только после критичного startup-path."""
        if self._strategy_cache_started:
            return
        self._strategy_cache_started = True
        self._log_startup_step("StrategyCacheWarmupQueued", str(source or "unknown"))
        self._init_strategy_cache()

    def _resolve_strategy_cache_summary(self, method: str) -> str:
        """Считает итоговую строку стратегии без выполнения UI-кода в рабочем потоке."""
        try:
            # Убедимся, что выбранные source-пресеты подготовлены до расчёта summary.
            if method == "direct_zapret2":
                try:
                    self.app.app_context.direct_flow_coordinator.get_startup_snapshot("direct_zapret2")
                except Exception as e:
                    log(
                        f"direct_zapret2: не удалось подготовить выбранный source-пресет: {e}",
                        "ERROR",
                    )
            elif method == "direct_zapret1":
                try:
                    self.app.app_context.direct_flow_coordinator.get_startup_snapshot("direct_zapret1")
                except Exception:
                    log("direct_zapret1: не удалось подготовить выбранный source-пресет", "ERROR")

            if method in ("direct_zapret2", "direct_zapret1"):
                from ui.window_display_state import get_direct_strategy_summary

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

    def _init_launch_runtime_api(self):
        """Инициализация launch runtime API."""
        try:
            from winws_runtime.runtime.runtime_api import DirectLaunchRuntimeApi
            from config.config import get_winws_exe_for_method, is_zapret2_mode

            from settings.dpi.strategy_settings import get_strategy_launch_method

            # Выбираем исполняемый файл в зависимости от режима запуска
            launch_method = get_strategy_launch_method()
            winws_exe = get_winws_exe_for_method(launch_method)
            if is_zapret2_mode(launch_method):
                log(f"Используется winws2.exe для режима {launch_method} (Zapret 2)", "INFO")
            else:
                log(f"Используется winws.exe для режима {launch_method}", "INFO")

            self.app.launch_runtime_api = DirectLaunchRuntimeApi(
                expected_exe_path=winws_exe,
                status_callback=self.app.set_status,
                app_instance=self.app,
            )
            log("Launch runtime API инициализирован", "INFO")
            self.init_tasks_completed.add('launch_runtime_api')
        except Exception as e:
            log(f"Ошибка инициализации launch runtime API: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка запуска: {e}")

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
                from lists.hostlists_manager import startup_hostlists_check

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
                from lists.ipsets_manager import startup_ipsets_check

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

    def _init_launch_controller(self):
        """Инициализация launch controller."""
        try:
            from winws_runtime.runtime.controller import DirectLaunchController
            self.app.launch_controller = DirectLaunchController(self.app)
            log("Launch controller инициализирован", "INFO")
            self.init_tasks_completed.add('launch_controller')
        except Exception as e:
            log(f"Ошибка инициализации launch controller: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка контроллера: {e}")

    def _init_telegram_proxy_autostart(self):
        """Фоновый автозапуск Telegram Proxy сразу после общего старта приложения."""
        try:
            from telegram_proxy.manager import autostart_proxy_if_enabled_async

            started = bool(autostart_proxy_if_enabled_async())
            if started:
                log("Telegram Proxy автозапуск запланирован через общий startup flow", "INFO")
            else:
                log("Telegram Proxy автозапуск не требуется или уже выполнен", "DEBUG")
        except Exception as e:
            log(f"Ошибка автозапуска Telegram Proxy: {e}", "WARNING")

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
        from settings.dpi.strategy_settings import get_strategy_launch_method

        launch_method = get_strategy_launch_method()

        # Для новых direct режимов проверяем сам source preset, а не legacy selections dict.
        if launch_method in ("direct_zapret2", "direct_zapret1"):
            try:
                self.app.app_context.direct_flow_coordinator.get_startup_snapshot(launch_method, require_filters=True)
            except Exception:
                self._show_strategy_required_warning(for_bat=False)
                self.app.set_status("⚠️ Выберите стратегию для запуска")
                return

        elif launch_method != "orchestra":
            self.app.set_status("⚠️ Выбран неподдерживаемый режим. Откройте настройки DPI и выберите актуальный режим.")
            return

        # orchestra режим не требует выбора стратегии - работает автоматически

        # Запускаем DPI
        self.app.launch_controller.start_dpi_async()

    def _show_strategy_required_warning(self, for_bat: bool = False) -> None:
        """Показывает fluent-предупреждение о том, что выбранный direct-пресет пуст для запуска."""
        launch_method = ""
        try:
            from settings.dpi.strategy_settings import get_strategy_launch_method

            launch_method = str(get_strategy_launch_method() or "").strip().lower()
        except Exception:
            pass

        if for_bat:
            subtitle = (
                "Для запуска Zapret выберите готовый пресет в разделе «Стратегии»."
            )
            button_text = "Открыть стратегии"
        else:
            subtitle = (
                "Для запуска Zapret выберите хотя бы одну стратегию "
                "в разделе «Стратегии»."
            )
            button_text = "Выбрать стратегию"

        try:
            controller = getattr(self.app, "window_notification_controller", None)
            if controller is None:
                raise RuntimeError("WindowNotificationController недоступен")

            controller.notify(
                advisory_notification(
                    level="warning",
                    title="Стратегия не выбрана",
                    content=subtitle,
                    source="launch.strategy_required",
                    presentation="infobar",
                    queue="immediate",
                    duration=-1,
                    dedupe_key=f"launch.strategy_required:{launch_method or 'unknown'}:{'bat' if for_bat else 'direct'}",
                    buttons=[
                        notification_action(
                            "open_strategy_page",
                            button_text,
                            value=launch_method,
                        ),
                    ],
                )
            )
        except Exception as e:
            log(f"Не удалось показать fluent-предупреждение о стратегии: {e}", "DEBUG")

    # ═══════════════════════════════════════════════════════════════════
    # ФАЗА 2: Инициализация менеджеров (разбито на логические группы)
    # ═══════════════════════════════════════════════════════════════════
    
    def _init_core_managers(self):
        """Инициализация ядра: DPI Manager и обязательные файлы."""
        try:
            import time as _t
            t0 = _t.perf_counter()
            
            # Создаем необходимые файлы
            from lists.file_manager import ensure_required_files
            ensure_required_files()
            
            # Launch autostart manager
            if not getattr(self.app, 'launch_autostart_manager', None):
                from managers.launch_autostart_manager import LaunchAutostartManager
                self.app.launch_autostart_manager = LaunchAutostartManager(self.app)
            
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
                runtime_service = getattr(self.app, "launch_runtime_service", None)
                launch_runtime_api = getattr(self.app, "launch_runtime_api", None)
                if runtime_service is not None and launch_runtime_api is not None:
                    from config.config import get_winws_exe_for_method

                    from settings.dpi.strategy_settings import get_strategy_launch_method
                    import os

                    launch_method = str(get_strategy_launch_method() or "").strip().lower()
                    expected_process = ""
                    if launch_method != "orchestra":
                        target_exe = get_winws_exe_for_method(launch_method)
                        expected_process = os.path.basename(target_exe).strip().lower()
                    else:
                        target_exe = get_winws_exe_for_method("direct_zapret2")

                    launch_runtime_api.set_expected_exe_path(target_exe)
                    runtime_service.bootstrap_probe(
                        launch_runtime_api.is_expected_running(silent=True),
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
                from dns.dns_worker import DNSUIManager, DNSStartupManager

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
            
            from ui.theme import ThemeManager
            from config.config import THEME_FOLDER

            from PyQt6.QtWidgets import QApplication
            
            # Создаём ThemeManager БЕЗ применения темы
            self.app.theme_manager = ThemeManager(
                app=QApplication.instance(),
                widget=self.app,
                theme_folder=THEME_FOLDER,
                donate_checker=getattr(self.app, 'donate_checker', None),
                apply_on_init=False
            )
            
            # ✅ Получаем текущую тему из theme_manager
            current_theme = self.app.theme_manager.current_theme
            is_premium = False
            if hasattr(self.app, 'donate_checker') and self.app.donate_checker:
                try:
                    sub_info = self.app.donate_checker.get_full_subscription_info(use_cache=True)
                    is_premium = bool(sub_info.get("is_premium"))
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
    
    def _finalize_managers_init(self):
        """Финализация инициализации менеджеров и обновление UI"""
        try:
            # Каноническая синхронизация автозапуска выполняется позже в
            # `_sync_autostart_status()`, поэтому здесь не дублируем тот же
            # внешний запрос второй раз подряд.
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
            from config.config import ICON_PATH, ICON_DEV_PATH
            from config.build_info import APP_VERSION, CHANNEL

            from PyQt6.QtGui import QIcon
            from PyQt6.QtWidgets import QApplication
            import os

            icon_path = ICON_DEV_PATH if CHANNEL.lower() == "dev" else ICON_PATH
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
                log("subscription_manager не инициализирован, фоновая проверка подписки пропущена", "WARNING")
        except Exception as e:
            log(f"Ошибка проверки подписки: {e}", "ERROR")

    # ───────────────────────── верификация и пост-задачи ─────────────────────

    def _required_components(self):
        """Список требуемых компонентов для успешного старта"""
        return ['launch_runtime_api', 'launch_controller', 'strategy_manager', 'managers']

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
            log("Критический startup-контур успешно инициализирован", "✅ SUCCESS")

            # Финальные задачи запускаем сразу по факту готовности, без таймерной оркестрации.
            self._post_init_tasks()
            self._sync_autostart_status()

        return True

    def _sync_autostart_status(self):
        """Синхронизирует статус автозапуска с реальным состоянием"""
        try:
            import time as _t
            t0 = _t.perf_counter()
            from autostart.autostart_exe import is_autostart_enabled
            real_status = is_autostart_enabled()
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
        post_init_metric_source = "post_init_scheduled"
        t_total = _time.perf_counter()

        try:
            exe_name, _ = self._get_current_winws_target()
            t_winws = _time.perf_counter()
            if not self._check_winws_exists():
                log(f"{exe_name} не найден", "❌ ERROR")
                self.app.set_status(f"❌ {exe_name} не найден")
                post_init_metric_source = "post_init_winws_missing"
                return
            self._log_startup_step("PostInitCheckWinws", f"{(_time.perf_counter() - t_winws)*1000:.0f}ms")

            log(f"✅ {exe_name} найден", "DEBUG")

            # Быструю часть post-init оставляем в критическом пути,
            # а реальный автозапуск передаём в единый dispatcher после возврата в event loop.
            t_method = _time.perf_counter()
            from settings.dpi.strategy_settings import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            self._log_startup_step(
                "PostInitResolveMethod",
                f"{launch_method} {(_time.perf_counter() - t_method)*1000:.0f}ms",
            )

            self._post_init_launch_bridge.launch_requested.emit(str(launch_method or ""))
            self._log_startup_step(
                "PostInitDeferredScheduled",
                f"{launch_method}, queued_connection",
            )
            post_init_metric_source = f"post_init_scheduled:{launch_method}"

            # Обновления проверяются вручную на вкладке "Серверы"

        except Exception as e:
            post_init_metric_source = f"post_init_error:{type(e).__name__}"
            log(f"Ошибка post-init задач: {e}", "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
        finally:
            self._log_startup_step("PostInitQuickPhase", f"{(_time.perf_counter() - t_total)*1000:.0f}ms")
            try:
                if hasattr(self.app, '_mark_startup_post_init_done'):
                    self.app._mark_startup_post_init_done(post_init_metric_source)
            except Exception:
                pass

    def _run_deferred_post_init_launch(self, launch_method: str) -> None:
        """Запускает тяжёлую post-init часть позже, когда окно уже стабилизировалось."""
        if self._post_init_dispatch_started:
            return
        self._post_init_dispatch_started = True

        started_at = _time.perf_counter()
        method = str(launch_method or "").strip().lower()
        self._log_startup_step("PostInitDeferredStart", method or "unknown")

        try:
            if hasattr(self.app, 'launch_autostart_manager'):
                self.app.launch_autostart_manager.delayed_dpi_start(launch_method=method)
        except Exception as e:
            log(f"Ошибка deferred post-init запуска ({method}): {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
        finally:
            self._maybe_start_strategy_cache(f"deferred_post_init:{method or 'unknown'}")
            self._log_startup_step(
                "PostInitDeferredDispatch",
                f"{method or 'unknown'} {(_time.perf_counter() - started_at)*1000:.0f}ms",
            )

    def _get_current_winws_target(self) -> tuple[str, str]:
        try:
            import os
            from config.config import get_winws_exe_for_method

            from settings.dpi.strategy_settings import get_strategy_launch_method

            launch_method = get_strategy_launch_method()
            target_file = get_winws_exe_for_method(launch_method)
            exe_name = os.path.basename(target_file) or "winws.exe"
            return exe_name, target_file
        except Exception:
            try:
                from config.config import WINWS_EXE

                import os

                return os.path.basename(WINWS_EXE) or "winws.exe", WINWS_EXE
            except Exception:
                return "winws.exe", ""

    def _check_winws_exists(self) -> bool:
        """Проверка наличия текущего winws.exe/winws2.exe для выбранного режима."""
        try:
            import os

            _, target_file = self._get_current_winws_target()
            return bool(target_file) and os.path.exists(target_file)

        except Exception as e:
            log(f"Ошибка при проверке winws файла: {e}", "DEBUG")
            # Fallback на WINWS_EXE
            try:
                from config.config import WINWS_EXE

                import os
                return os.path.exists(WINWS_EXE)
            except Exception:
                return False
