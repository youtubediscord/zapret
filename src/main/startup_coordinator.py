import time as _time
from dataclasses import dataclass
from typing import Callable

from log.log import log
from main.qt_dispatch import run_queued, run_queued_with_str
from settings.mode import normalize_launch_method


TASK_LAUNCH_RUNTIME_API = "launch_runtime_api"
TASK_LAUNCH_RUNTIME = "launch_runtime"
TASK_INTERACTIVE_READY = "interactive_ready"
TASK_PROCESS_MONITOR = "process_monitor"
TASK_CORE_STARTUP = "core_startup"
TASK_THEME_MANAGER = "theme_manager"
TASK_TRAY = "tray"
TASK_STARTUP_CORE_READY = "startup_core_ready"

REQUIRED_STARTUP_COMPONENTS = (
    TASK_LAUNCH_RUNTIME_API,
    TASK_LAUNCH_RUNTIME,
    TASK_STARTUP_CORE_READY,
)


@dataclass(frozen=True, slots=True)
class StartupWindowShell:
    """Минимальный UI-интерфейс, который нужен startup-координатору."""

    start_in_tray: bool
    set_status: Callable[[str], None]
    mark_startup_interactive: Callable[[str], None]
    mark_startup_core_ready: Callable[[str], None]
    mark_startup_post_init_done: Callable[[str], None]
    init_theme_manager: Callable[[], None]


class StartupCoordinator:
    """
    Координатор запуска приложения.

    Логика разделена на две стадии:
    1. Минимальный интерактивный контур — только то, без чего окно не может
       быстро показаться и обработать первый клик.
    2. Остальная инициализация — runtime, мониторинг, тема и tray.

    Такой разрез нужен, чтобы GUI перестал держать главный поток занятым
    первые 2-3 секунды после появления окна.
    """

    def __init__(
        self,
        app_runtime,
        window_shell: StartupWindowShell,
        *,
        log_startup_metric,
    ):
        self.window_shell = window_shell
        self.runtime = app_runtime.features.runtime
        self.tray = app_runtime.features.tray
        self.log_startup_metric = log_startup_metric
        self.startup_tasks_completed = set()

        # Финализация старта теперь идёт по прямому жизненному циклу, а не через
        # таймерную "проверку готовности".
        self._verify_done = False
        self._post_init_scheduled = False

        self._phase_two_started = False
        self._post_init_dispatch_started = False

    def _log_startup_step(self, marker: str, details: str = "") -> None:
        try:
            self.log_startup_metric(marker, details)
        except Exception as e:
            log(f"Не удалось записать startup-метрику {marker}: {e}", "DEBUG")

    def _init_tray(self) -> None:
        self.tray.init()

    def ensure_tray_initialized(self):
        """Синхронно гарантирует, что системный трей готов к работе."""
        if self.tray.is_initialized():
            return True

        self._run_step(
            TASK_TRAY,
            "tray",
            self._init_tray,
            error_status=None,
        )
        return self.tray.is_initialized()

    # ───────────────────────── запуск и планирование ─────────────────────────

    def run_async_init(self):
        """Запускает старт в два этапа без блокировки первого показа окна."""
        log("🟡 StartupCoordinator: начало оптимизированной инициализации", "DEBUG")

        self.window_shell.set_status("Инициализация компонентов...")

        # Фаза 1: только минимальный контур, который нужен для немедленного
        # взаимодействия с окном. Всё остальное — позже отдельным queued-шагом.
        startup_steps = [
            (
                TASK_LAUNCH_RUNTIME_API,
                "launch runtime API",
                self.runtime.init_launch_runtime_api,
                lambda exc: f"Ошибка запуска: {exc}",
            ),
            (
                TASK_LAUNCH_RUNTIME,
                "launch runtime",
                self.runtime.init_launch_runtime,
                lambda exc: f"Ошибка runtime запуска: {exc}",
            ),
            (
                TASK_INTERACTIVE_READY,
                "interactive ready",
                self._mark_interactive_ready,
                None,
            ),
        ]

        for task_name, label, task, error_status in startup_steps:
            log(f"🟡 Выполняем {task_name} сразу", "DEBUG")
            self._run_step(task_name, label, task, error_status=error_status)

        self._check_and_complete_initialization()
        run_queued(self._run_phase_two_init)

    def _run_phase_two_init(self) -> None:
        """Продолжает старт после первого возврата в цикл интерфейса."""
        if self._phase_two_started:
            return
        self._phase_two_started = True

        phase_two_steps = [
            (
                TASK_PROCESS_MONITOR,
                "process monitor",
                self.runtime.init_process_monitor,
                None,
            ),
            (
                TASK_CORE_STARTUP,
                "core startup",
                self.runtime.init_core_startup,
                None,
            ),
            (
                TASK_THEME_MANAGER,
                "theme manager",
                self.window_shell.init_theme_manager,
                None,
            ),
        ]

        if bool(self.window_shell.start_in_tray):
            phase_two_steps.append(
                (
                    TASK_TRAY,
                    "tray",
                    self._init_tray,
                    None,
                )
            )
        else:
            log("Системный трей отложен до post-init для обычного запуска", "DEBUG")

        phase_two_steps.append(
            (
                TASK_STARTUP_CORE_READY,
                "startup core",
                self._finalize_startup_core,
                None,
            )
        )

        for task_name, label, task, error_status in phase_two_steps:
            log(f"🟡 Выполняем {task_name} после первого показа окна", "DEBUG")
            self._run_step(task_name, label, task, error_status=error_status)

    # ───────────────────────── инициализация подсистем ───────────────────────

    def _run_step(self, task_name: str, label: str, func, *, error_status=None) -> bool:
        try:
            func()
            self.startup_tasks_completed.add(task_name)
            return True
        except Exception as exc:
            log(f"Ошибка startup-шага {label}: {exc}", "❌ ERROR")
            if error_status is not None:
                try:
                    self.window_shell.set_status(error_status(exc))
                except Exception:
                    pass
            return False

    def _mark_interactive_ready(self):
        """Фиксирует момент, когда минимальный контур окна уже готов к кликам."""
        self.window_shell.mark_startup_interactive("startup_minimal_ready")

    def _finalize_startup_core(self):
        """Фиксирует готовность основного startup-контура."""
        log("Основной startup-контур готов", "✅ SUCCESS")
        self.window_shell.mark_startup_core_ready("startup_coordinator")
        self.window_shell.set_status("Инициализация завершена")
        self._check_and_complete_initialization()
        log("✅ Startup core finalized", "DEBUG")

    # ───────────────────────── верификация и пост-задачи ─────────────────────

    def _required_components(self):
        """Список требуемых компонентов для успешного старта"""
        return REQUIRED_STARTUP_COMPONENTS

    def _check_and_complete_initialization(self) -> bool:
        """
        Проверяет, все ли компоненты готовы, и если да — завершает инициализацию:
        - ставит финальный статус
        - запускает отложенные post-init задачи
        Возвращает True если всё готово, иначе False.
        """
        required_components = self._required_components()
        missing = [c for c in required_components if c not in self.startup_tasks_completed]

        if missing:
            return False

        # Все компоненты готовы
        if not self._verify_done:
            self._verify_done = True
            self.window_shell.set_status("✅ Инициализация завершена")
            log("Критический startup-контур успешно инициализирован", "✅ SUCCESS")

            # Финальные задачи запускаем сразу по факту готовности, без таймерной оркестрации.
            self._post_init_tasks()

        return True

    def _post_init_tasks(self):
        """Задачи после успешной инициализации (запускаются один раз)"""
        if self._post_init_scheduled:
            return
        self._post_init_scheduled = True
        post_init_metric_source = "post_init_scheduled"
        t_total = _time.perf_counter()

        try:
            # Быструю часть post-init оставляем в критическом пути,
            # а реальный автозапуск передаём в единый dispatcher после возврата в event loop.
            t_method = _time.perf_counter()
            from settings.dpi.strategy_settings import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            self._log_startup_step(
                "StartupPostInitResolveMethod",
                f"{launch_method} {(_time.perf_counter() - t_method)*1000:.0f}ms",
            )

            run_queued_with_str(self._run_deferred_post_init_launch, str(launch_method or ""))
            self._log_startup_step(
                "StartupPostInitDeferredScheduled",
                f"{launch_method}, queued_connection",
            )
            self._log_startup_step(
                "StartupDpiAutostart",
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
            self._log_startup_step("StartupPostInitQuickPhase", f"{(_time.perf_counter() - t_total)*1000:.0f}ms")
            self.window_shell.mark_startup_post_init_done(post_init_metric_source)

    def _run_deferred_post_init_launch(self, launch_method: str) -> None:
        """Запускает тяжёлую post-init часть позже, когда окно уже стабилизировалось."""
        if self._post_init_dispatch_started:
            return
        self._post_init_dispatch_started = True

        started_at = _time.perf_counter()
        method = normalize_launch_method(launch_method)
        self._log_startup_step("StartupPostInitDeferredStart", method or "unknown")

        try:
            self.runtime.start_autostart(launch_method=method)
        except Exception as e:
            log(f"Ошибка deferred post-init запуска ({method}): {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
        finally:
            self._log_startup_step(
                "StartupPostInitDeferredDispatch",
                f"{method or 'unknown'} {(_time.perf_counter() - started_at)*1000:.0f}ms",
            )
