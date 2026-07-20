import time as _time
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from log.log import log
from main.post_startup_threading import start_daemon_thread
from main.qt_dispatch import run_queued


TASK_LAUNCH_RUNTIME_API = "launch_runtime_api"
TASK_LAUNCH_RUNTIME = "launch_runtime"
TASK_PROCESS_MONITOR = "process_monitor"
TASK_CORE_STARTUP = "core_startup"
TASK_THEME_MANAGER = "theme_manager"
TASK_TRAY = "tray"
TASK_STARTUP_CORE_READY = "startup_core_ready"

STARTUP_STEP_GAP_MS = 0
STARTUP_DPI_AUTOSTART_DELAY_MS = 0

REQUIRED_STARTUP_COMPONENTS = (
    TASK_LAUNCH_RUNTIME_API,
    TASK_LAUNCH_RUNTIME,
    TASK_STARTUP_CORE_READY,
)


def _startup_step_metric_marker(task_name: str) -> str:
    words = str(task_name or "step").replace("-", "_").split("_")
    suffix = "".join(word[:1].upper() + word[1:] for word in words if word)
    return f"StartupStep{suffix or 'Step'}"


@dataclass(frozen=True, slots=True)
class StartupWindowShell:
    """Минимальный UI-интерфейс, который нужен startup-координатору."""

    start_in_tray: bool
    set_status: Callable[[str], None]
    mark_startup_core_ready: Callable[[str], None]
    mark_startup_post_init_done: Callable[[str], None]
    init_theme_manager: Callable[[], None]


class _StartupStepBridge(QObject):
    finished = pyqtSignal(object)


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
        *,
        runtime_feature,
        tray_feature,
        window_shell: StartupWindowShell,
        log_startup_metric,
        migrate_gui_autostart: Callable[[], bool],
    ):
        self.window_shell = window_shell
        self.runtime = runtime_feature
        self.tray = tray_feature
        self.log_startup_metric = log_startup_metric
        self._migrate_gui_autostart = migrate_gui_autostart
        self.startup_tasks_completed = set()

        # Финализация старта теперь идёт по прямому жизненному циклу, а не через
        # таймерную "проверку готовности".
        self._verify_done = False
        self._post_init_scheduled = False

        self._phase_two_started = False
        self._post_init_dispatch_started = False
        self._step_bridge = _StartupStepBridge()
        self._step_bridge.finished.connect(self._on_background_step_finished)

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
        ]

        self._log_startup_step(
            "StartupRuntimeInitQueued",
            f"{STARTUP_STEP_GAP_MS}ms gaps",
        )
        self._run_startup_steps_queued(
            startup_steps,
            after_complete=lambda: run_queued(self._run_phase_two_init),
        )

    def _run_phase_two_init(self) -> None:
        """Продолжает старт после первого возврата в цикл интерфейса."""
        if self._phase_two_started:
            return
        self._phase_two_started = True

        phase_two_steps = []

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
        phase_two_steps.append(
            (
                TASK_THEME_MANAGER,
                "theme manager",
                self.window_shell.init_theme_manager,
                None,
            )
        )
        phase_two_steps.append(
            (
                TASK_PROCESS_MONITOR,
                "process monitor",
                self.runtime.init_process_monitor,
                None,
            )
        )
        phase_two_steps.append(
            (
                TASK_CORE_STARTUP,
                "core startup",
                self.runtime.init_core_startup,
                None,
            )
        )

        self._log_startup_step(
            "StartupRuntimePhaseTwoQueued",
            f"{STARTUP_STEP_GAP_MS}ms gaps",
        )
        self._run_startup_steps_queued(phase_two_steps)

    def _run_startup_steps_queued(
        self,
        steps,
        *,
        index: int = 0,
        after_complete=None,
    ) -> None:
        """Выполняет startup-шаги по одному, возвращая управление UI между ними."""
        if index >= len(steps):
            if callable(after_complete):
                after_complete()
            return

        task_name, label, task, error_status = steps[index]

        def _run_current_step() -> None:
            log(f"🟡 Выполняем {task_name} после готовности UI", "DEBUG")
            if task_name == TASK_CORE_STARTUP:
                self._run_step_in_background(
                    task_name,
                    label,
                    task,
                    error_status=error_status,
                    after_finished=lambda: self._run_startup_steps_queued(
                        steps,
                        index=index + 1,
                        after_complete=after_complete,
                    ),
                )
                return

            self._run_step(task_name, label, task, error_status=error_status)
            self._run_startup_steps_queued(
                steps,
                index=index + 1,
                after_complete=after_complete,
            )

        delay_ms = 0 if index == 0 else STARTUP_STEP_GAP_MS
        if delay_ms <= 0:
            run_queued(_run_current_step)
            return
        QTimer.singleShot(delay_ms, _run_current_step)

    # ───────────────────────── инициализация подсистем ───────────────────────

    def _run_step(self, task_name: str, label: str, func, *, error_status=None) -> bool:
        started_at = _time.perf_counter()
        metric_marker = _startup_step_metric_marker(task_name)
        try:
            func()
            elapsed_ms = (_time.perf_counter() - started_at) * 1000.0
            self._log_startup_step(metric_marker, f"{label} {elapsed_ms:.0f}ms")
            self.startup_tasks_completed.add(task_name)
            self._check_and_complete_initialization()
            return True
        except Exception as exc:
            elapsed_ms = (_time.perf_counter() - started_at) * 1000.0
            self._log_startup_step(
                metric_marker,
                f"{label} error:{type(exc).__name__} {elapsed_ms:.0f}ms",
            )
            log(f"Ошибка startup-шага {label}: {exc}", "❌ ERROR")
            if error_status is not None:
                try:
                    self.window_shell.set_status(error_status(exc))
                except Exception:
                    pass
            return False

    def _run_step_in_background(self, task_name: str, label: str, func, *, error_status=None, after_finished=None) -> None:
        """Выполняет тяжёлый startup-шаг вне главного потока и возвращает итог в UI."""
        metric_marker = _startup_step_metric_marker(task_name)

        def _worker() -> None:
            started_at = _time.perf_counter()
            try:
                func()
                self._step_bridge.finished.emit(
                    {
                        "task_name": task_name,
                        "label": label,
                        "metric_marker": metric_marker,
                        "error_status": error_status,
                        "after_finished": after_finished,
                        "elapsed_ms": (_time.perf_counter() - started_at) * 1000.0,
                        "error": None,
                    }
                )
            except Exception as exc:
                self._step_bridge.finished.emit(
                    {
                        "task_name": task_name,
                        "label": label,
                        "metric_marker": metric_marker,
                        "error_status": error_status,
                        "after_finished": after_finished,
                        "elapsed_ms": (_time.perf_counter() - started_at) * 1000.0,
                        "error": exc,
                    }
                )

        start_daemon_thread(f"StartupStep-{task_name}", _worker)

    def _on_background_step_finished(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        task_name = str(data.get("task_name") or "")
        label = str(data.get("label") or task_name or "step")
        metric_marker = str(data.get("metric_marker") or _startup_step_metric_marker(task_name))
        elapsed_ms = float(data.get("elapsed_ms") or 0.0)
        error = data.get("error")
        after_finished = data.get("after_finished")
        error_status = data.get("error_status")

        if error is None:
            self._log_startup_step(metric_marker, f"{label} {elapsed_ms:.0f}ms")
            self.startup_tasks_completed.add(task_name)
            self._check_and_complete_initialization()
        else:
            self._log_startup_step(
                metric_marker,
                f"{label} error:{type(error).__name__} {elapsed_ms:.0f}ms",
            )
            log(f"Ошибка startup-шага {label}: {error}", "❌ ERROR")
            if error_status is not None:
                try:
                    self.window_shell.set_status(error_status(error))
                except Exception:
                    pass

        if callable(after_finished):
            after_finished()

    def _finalize_startup_core(self):
        """Фиксирует готовность основного startup-контура."""
        log("Основной startup-контур готов", "✅ SUCCESS")
        self.window_shell.mark_startup_core_ready("startup_coordinator")
        self.window_shell.set_status("Инициализация завершена")
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
            start_daemon_thread("GuiAutostartMigration", self._run_gui_autostart_migration)

            # Быструю часть post-init оставляем в критическом пути,
            # а реальный автозапуск передаём в единый dispatcher после возврата в event loop.
            QTimer.singleShot(
                STARTUP_DPI_AUTOSTART_DELAY_MS,
                lambda: self._run_deferred_post_init_launch(None),
            )
            self._log_startup_step(
                "StartupPostInitDeferredScheduled",
                f"auto, {STARTUP_DPI_AUTOSTART_DELAY_MS}ms after post-init",
            )
            self._log_startup_step(
                "StartupDpiAutostart",
                f"auto, {STARTUP_DPI_AUTOSTART_DELAY_MS}ms after post-init",
            )
            post_init_metric_source = "post_init_scheduled:auto"

            # Обновления проверяются вручную на вкладке "Серверы"

        except Exception as e:
            post_init_metric_source = f"post_init_error:{type(e).__name__}"
            log(f"Ошибка post-init задач: {e}", "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
        finally:
            self._log_startup_step("StartupPostInitQuickPhase", f"{(_time.perf_counter() - t_total)*1000:.0f}ms")
            self.window_shell.mark_startup_post_init_done(post_init_metric_source)

    def _run_gui_autostart_migration(self) -> None:
        """Переводит автозапуск GUI со старого ярлыка на задачу Планировщика."""
        try:
            if self._migrate_gui_autostart():
                log("Автозапуск GUI мигрирован на задачу Планировщика", "INFO")
        except Exception as e:
            log(f"Ошибка миграции автозапуска GUI: {e}", "DEBUG")

    def _run_deferred_post_init_launch(self, launch_method: str | None) -> None:
        """Запускает тяжёлую post-init часть позже, когда окно уже стабилизировалось."""
        if self._post_init_dispatch_started:
            return
        self._post_init_dispatch_started = True

        started_at = _time.perf_counter()
        method = self._resolve_deferred_launch_method(launch_method)
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

    def _resolve_deferred_launch_method(self, launch_method: str | None) -> str:
        t_method = _time.perf_counter()
        from settings.mode import normalize_launch_method

        raw_method = launch_method
        if raw_method is None:
            from settings.dpi.strategy_settings import get_strategy_launch_method

            raw_method = get_strategy_launch_method()

        method = normalize_launch_method(raw_method)
        self._log_startup_step(
            "StartupPostInitResolveMethod",
            f"{method} {(_time.perf_counter() - t_method)*1000:.0f}ms",
        )
        return method
