from __future__ import annotations

from dataclasses import dataclass
from PyQt6.QtCore import QTimer
from typing import TYPE_CHECKING, Callable

from presets.ui.control.control_page_runtime_shared import set_toggle_checked

if TYPE_CHECKING:
    from app.state_store import MainWindowStateStore
    from ui.one_shot_worker_runtime import OneShotWorkerRuntime


RUNTIME_START_RETRY_MS = 250
RUNTIME_START_MAX_RETRIES = 24
RUNTIME_START_CONFLICT_STOP_MAX_RETRIES = 240


@dataclass(frozen=True, slots=True)
class ControlRuntimeActions:
    start: Callable[[], object]
    stop: Callable[[], object]
    stop_and_exit: Callable[[], object]
    is_available: Callable[[], object]


class ControlPageActionMixin:
    """Общие действия для страниц управления."""

    def _start_dpi(self) -> None:
        if self._request_runtime_conflicting_checks_stop():
            self._queue_runtime_start_retry(
                "Останавливаем подбор стратегии перед запуском Zapret...",
                reason="conflict_stop",
            )
            return
        if not self._runtime_start_available():
            self._queue_runtime_start_retry()
            return
        self._runtime_actions.start()

    def _runtime_start_available(self) -> bool:
        available = getattr(self._runtime_actions, "is_available", None)
        if callable(available):
            try:
                return bool(available())
            except Exception:
                return False
        return False

    def _request_runtime_conflicting_checks_stop(self) -> bool:
        try:
            window_getter = getattr(self, "window", None)
            window = window_getter() if callable(window_getter) else None
            if window is None:
                return False
            from app.page_names import PageName
            from ui.window_adapter import send_page_command

            return bool(
                send_page_command(
                    window,
                    PageName.BLOCKCHECK,
                    "stop_runtime_conflicting_checks",
                    {"source": "dpi_start"},
                    ensure=False,
                )
            )
        except Exception:
            return False

    def _queue_runtime_start_retry(self, message: str = "Подготовка запуска...", *, reason: str = "runtime") -> None:
        if bool(getattr(self, "_runtime_start_retry_pending", False)):
            return
        self._runtime_start_retry_pending = True
        self._runtime_start_retry_count = 0
        self._runtime_start_retry_reason = str(reason or "runtime")
        self._show_runtime_preparing_state(message)
        QTimer.singleShot(RUNTIME_START_RETRY_MS, self._retry_start_dpi_after_runtime_ready)

    def _show_runtime_preparing_state(self, message: str = "Подготовка запуска...") -> None:
        message = str(message or "").strip() or "Подготовка запуска..."
        set_loading = getattr(self, "set_loading", None)
        if callable(set_loading):
            set_loading(True, message)
        set_status = getattr(self, "_set_status", None)
        if callable(set_status):
            set_status(message)

    def _retry_start_dpi_after_runtime_ready(self) -> None:
        if bool(getattr(self, "_cleanup_in_progress", False)):
            self._runtime_start_retry_pending = False
            return

        if self._request_runtime_conflicting_checks_stop():
            retries = int(getattr(self, "_runtime_start_retry_count", 0)) + 1
            self._runtime_start_retry_count = retries
            if retries >= RUNTIME_START_CONFLICT_STOP_MAX_RETRIES:
                self._runtime_start_retry_pending = False
                set_loading = getattr(self, "set_loading", None)
                if callable(set_loading):
                    set_loading(False, "")
                set_status = getattr(self, "_set_status", None)
                if callable(set_status):
                    set_status("Подбор стратегии ещё останавливается. Дождитесь остановки и запустите Zapret снова.")
                return
            QTimer.singleShot(RUNTIME_START_RETRY_MS, self._retry_start_dpi_after_runtime_ready)
            return

        if self._runtime_start_available():
            self._runtime_start_retry_pending = False
            set_loading = getattr(self, "set_loading", None)
            if callable(set_loading):
                set_loading(False, "")
            self._runtime_actions.start()
            return

        retries = int(getattr(self, "_runtime_start_retry_count", 0)) + 1
        self._runtime_start_retry_count = retries
        if retries >= RUNTIME_START_MAX_RETRIES:
            self._runtime_start_retry_pending = False
            set_loading = getattr(self, "set_loading", None)
            if callable(set_loading):
                set_loading(False, "")
            set_status = getattr(self, "_set_status", None)
            if callable(set_status):
                set_status("Запуск ещё не готов. Попробуйте ещё раз через пару секунд.")
            return

        QTimer.singleShot(RUNTIME_START_RETRY_MS, self._retry_start_dpi_after_runtime_ready)

    def _stop_dpi(self) -> None:
        self._runtime_actions.stop()

    def _stop_and_exit(self) -> None:
        from log.log import log
        from PyQt6.QtWidgets import QApplication

        log("Остановка winws и закрытие программы...", "INFO")

        request_exit = getattr(self, "_request_exit_callback", None)
        if callable(request_exit):
            request_exit(stop_dpi=True)
            return

        if self._runtime_actions.stop_and_exit():
            return

        QApplication.quit()

    def _open_connection_test(self) -> None:
        handler = getattr(self, "_open_connection_test_callback", None)
        if callable(handler):
            handler()

    def _open_folder(self) -> None:
        handler = getattr(self, "_open_folder_callback", None)
        if callable(handler):
            handler()

    def create_external_open_url_worker(self, request_id: int, *, url: str):
        return self._create_external_open_url_worker(request_id, url=url, parent=self)

    def _ensure_external_open_url_runtime(self) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get("_external_open_url_runtime")
        if runtime is None:
            from ui.one_shot_worker_runtime import OneShotWorkerRuntime

            runtime = OneShotWorkerRuntime()
            self._external_open_url_runtime = runtime
            self._external_open_url_pending = []
            self._external_open_url_start_scheduled = False
        elif self.__dict__.get("_external_open_url_pending") is None:
            self._external_open_url_pending = []
        return runtime

    def _request_external_open_url(self, url: str, *, error_title: str, error_default: str) -> None:
        runtime = self._ensure_external_open_url_runtime()
        request = (str(url or "").strip(), str(error_title), str(error_default))
        if runtime.is_running() or self.__dict__.get("_external_open_url_start_scheduled", False):
            self._queue_external_open_url_request(request)
            return
        self._start_external_open_url_worker(*request)

    def _queue_external_open_url_request(self, request: tuple[str, str, str]) -> None:
        pending = self.__dict__.setdefault("_external_open_url_pending", [])
        queued = tuple(request)
        if queued in pending:
            return
        pending.append(queued)

    def _start_external_open_url_worker(self, url: str, error_title: str, error_default: str) -> None:
        runtime = self._ensure_external_open_url_runtime()
        runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_external_open_url_worker(request_id, url=url),
            on_loaded=lambda request_id, result: self._on_external_open_url_finished(
                request_id,
                result,
                error_title=error_title,
                error_default=error_default,
            ),
            on_failed=lambda request_id, error: self._on_external_open_url_failed(
                request_id,
                error,
                error_title=error_title,
                error_default=error_default,
            ),
            on_finished=self._on_external_open_url_worker_finished,
        )

    def _on_external_open_url_finished(
        self,
        request_id: int,
        result,
        *,
        error_title: str,
        error_default: str,
    ) -> None:
        runtime = self._ensure_external_open_url_runtime()
        if not runtime.is_current(request_id, cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))):
            return
        if self.__dict__.get("_external_open_url_pending"):
            return
        if getattr(result, "ok", False):
            return
        self._show_external_open_url_error(
            error_title,
            error_default,
            str(getattr(result, "error", "") or ""),
        )

    def _on_external_open_url_failed(
        self,
        request_id: int,
        error: str,
        *,
        error_title: str,
        error_default: str,
    ) -> None:
        runtime = self._ensure_external_open_url_runtime()
        if not runtime.is_current(request_id, cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False))):
            return
        if self.__dict__.get("_external_open_url_pending"):
            return
        self._show_external_open_url_error(error_title, error_default, str(error))

    def _on_external_open_url_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_external_open_url_runtime"), _worker):
            return
        pending = self.__dict__.get("_external_open_url_pending") or []
        if pending and not bool(getattr(self, "_cleanup_in_progress", False)):
            self._schedule_external_open_url_worker_start(pending.pop(0))

    def _schedule_external_open_url_worker_start(self, request: tuple[str, str, str]) -> None:
        pending = tuple(request)
        if self.__dict__.get("_external_open_url_start_scheduled", False):
            self._queue_external_open_url_request(pending)
            return
        self._external_open_url_start_scheduled = True
        try:
            QTimer.singleShot(0, lambda: self._run_scheduled_external_open_url_worker_start(pending))
        except Exception:
            self._run_scheduled_external_open_url_worker_start(pending)

    def _run_scheduled_external_open_url_worker_start(self, request: tuple[str, str, str]) -> None:
        self._external_open_url_start_scheduled = False
        if bool(getattr(self, "_cleanup_in_progress", False)):
            return
        self._start_external_open_url_worker(*request)

    def _show_external_open_url_error(self, title: str, default: str, error: str) -> None:
        from qfluentwidgets import InfoBar

        InfoBar.warning(title=title, content=default.format(error=error), parent=self.window())

    def _stop_external_open_url_worker(self) -> None:
        self.__dict__.setdefault("_external_open_url_pending", []).clear()
        self._external_open_url_start_scheduled = False
        runtime = self.__dict__.get("_external_open_url_runtime")
        if runtime is not None:
            runtime.stop(blocking=True, warning_prefix="External open url worker")

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
        set_toggle_checked(toggle, checked)

    def _set_status(self, msg: str) -> None:
        try:
            status_setter = getattr(self, "_set_status_callback", None)
            if callable(status_setter):
                status_setter(msg)
        except Exception:
            pass

    def create_program_settings_save_worker(self, request_id: int, *, action: str, enabled: bool):
        return self._create_program_settings_save_worker(
            request_id,
            action=action,
            enabled=bool(enabled),
            parent=self,
        )

    def create_program_settings_load_worker(self, request_id: int):
        return self._create_program_settings_load_worker(
            request_id,
            parent=self,
        )

    def _request_program_settings_load(self) -> None:
        runtime = self._refresh_runtime
        if (
            runtime.program_settings_load_runtime.is_running()
            or bool(getattr(runtime, "program_settings_load_start_scheduled", False))
        ):
            runtime.program_settings_load_pending = True
            return

        runtime.program_settings_load_runtime.start_qthread_worker(
            worker_factory=self.create_program_settings_load_worker,
            on_loaded=self._on_program_settings_load_finished,
            on_failed=self._on_program_settings_load_failed,
            on_finished=self._on_program_settings_load_worker_finished,
        )

    def _on_program_settings_load_finished(self, request_id: int, snapshot) -> None:
        runtime = self._refresh_runtime
        if not runtime.program_settings_load_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if bool(getattr(runtime, "program_settings_load_pending", False)):
            return
        try:
            self._publish_program_settings_snapshot(snapshot)
        except Exception:
            pass
        apply_snapshot = getattr(self, "_apply_program_settings_snapshot", None)
        if callable(apply_snapshot):
            apply_snapshot(snapshot)

    def _on_program_settings_load_failed(self, request_id: int, error: str) -> None:
        runtime = self._refresh_runtime
        if not runtime.program_settings_load_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if bool(getattr(runtime, "program_settings_load_pending", False)):
            return
        try:
            from log.log import log

            log(f"Не удалось загрузить настройки программы: {error}", "WARNING")
        except Exception:
            pass

    def _on_program_settings_load_worker_finished(self, _worker) -> None:
        runtime = self._refresh_runtime
        if not self._is_current_worker_finish(runtime.program_settings_load_runtime, _worker):
            return
        if runtime.program_settings_load_pending and not bool(getattr(self, "_cleanup_in_progress", False)):
            runtime.program_settings_load_pending = False
            self._schedule_program_settings_load_start()
            return
        runtime.program_settings_load_pending = False

    def _schedule_program_settings_load_start(self) -> None:
        runtime = self._refresh_runtime
        if bool(getattr(runtime, "program_settings_load_start_scheduled", False)):
            runtime.program_settings_load_pending = True
            return
        runtime.program_settings_load_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_program_settings_load_start)
        except Exception:
            self._run_scheduled_program_settings_load_start()

    def _run_scheduled_program_settings_load_start(self) -> None:
        runtime = self._refresh_runtime
        runtime.program_settings_load_start_scheduled = False
        if bool(getattr(self, "_cleanup_in_progress", False)):
            return
        runtime.program_settings_load_pending = False
        self._request_program_settings_load()

    def _request_program_settings_save(self, action: str, enabled: bool) -> None:
        runtime = self._refresh_runtime
        if (
            runtime.program_settings_save_runtime.is_running()
            or bool(getattr(runtime, "program_settings_save_start_scheduled", False))
        ):
            runtime.queue_program_settings_save(action, bool(enabled))
            return

        runtime.program_settings_save_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_program_settings_save_worker(
                request_id,
                action=action,
                enabled=bool(enabled),
            ),
            on_loaded=self._on_program_settings_save_finished,
            on_failed=self._on_program_settings_save_failed,
            on_finished=self._on_program_settings_save_worker_finished,
            bind_worker=self._bind_program_settings_save_worker,
            loaded_signal_name="saved",
        )

    def _bind_program_settings_save_worker(self, worker) -> None:
        status_signal = getattr(worker, "status", None)
        if status_signal is not None:
            status_signal.connect(self._on_program_settings_save_status)

    def _on_program_settings_save_status(self, request_id: int, _action: str, message: str) -> None:
        runtime = self._refresh_runtime
        if not runtime.program_settings_save_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if runtime.program_settings_save_pending:
            return
        self._set_status(str(message or ""))

    def _on_program_settings_save_finished(self, request_id: int, action: str, result) -> None:
        runtime = self._refresh_runtime
        if not runtime.program_settings_save_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if runtime.program_settings_save_pending:
            return
        try:
            if action == "auto_dpi":
                self._set_status(str(getattr(result, "message", "") or ""))
                from qfluentwidgets import InfoBar

                InfoBar.success(
                    title=str(getattr(result, "title", "Автозапуск DPI") or "Автозапуск DPI"),
                    content=str(getattr(result, "message", "") or ""),
                    parent=self.window(),
                )
            elif action == "defender_disabled":
                self._show_windows_feature_action_result(result, self.defender_toggle)
            elif action == "max_block":
                self._show_windows_feature_action_result(result, self.max_block_toggle)
            elif action == "hide_to_tray":
                self._remember_hide_to_tray_on_minimize_close(bool(result))
        finally:
            sync_program_settings = getattr(self, "_sync_program_settings", None)
            if callable(sync_program_settings):
                sync_program_settings()

    def _on_program_settings_save_failed(self, request_id: int, action: str, error: str) -> None:
        runtime = self._refresh_runtime
        if not runtime.program_settings_save_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if runtime.program_settings_save_pending:
            return
        from qfluentwidgets import InfoBar

        InfoBar.warning(title="Ошибка", content=f"Не удалось сохранить настройку: {error}", parent=self.window())
        sync_program_settings = getattr(self, "_sync_program_settings", None)
        if callable(sync_program_settings):
            sync_program_settings()

    def _on_program_settings_save_worker_finished(self, _worker) -> None:
        runtime = self._refresh_runtime
        if not self._is_current_worker_finish(runtime.program_settings_save_runtime, _worker):
            return
        pending = runtime.program_settings_save_pending
        if pending and not bool(getattr(self, "_cleanup_in_progress", False)):
            next_save = pending.pop(0)
            self._schedule_program_settings_save_start(str(next_save[0]), bool(next_save[1]))

    def _schedule_program_settings_save_start(self, action: str, enabled: bool) -> None:
        runtime = self._refresh_runtime
        if bool(getattr(runtime, "program_settings_save_start_scheduled", False)):
            runtime.queue_program_settings_save(action, bool(enabled), front=True)
            return
        runtime.program_settings_save_start_scheduled = True
        try:
            QTimer.singleShot(
                0,
                lambda: self._run_scheduled_program_settings_save_start(str(action or ""), bool(enabled)),
            )
        except Exception:
            self._run_scheduled_program_settings_save_start(str(action or ""), bool(enabled))

    def _run_scheduled_program_settings_save_start(self, action: str, enabled: bool) -> None:
        self._refresh_runtime.program_settings_save_start_scheduled = False
        if bool(getattr(self, "_cleanup_in_progress", False)):
            return
        self._request_program_settings_save(str(action or ""), bool(enabled))

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False


def bind_control_ui_state_store(
    owner,
    store: MainWindowStateStore,
    *,
    callback,
    fields: set[str] | frozenset[str],
    emit_initial: bool = True,
) -> None:
    if owner._ui_state_store is store:
        return

    unsubscribe = getattr(owner, "_ui_state_unsubscribe", None)
    if callable(unsubscribe):
        try:
            unsubscribe()
        except Exception:
            pass

    owner._ui_state_store = store
    owner._ui_state_unsubscribe = store.subscribe(
        callback,
        fields=set(fields),
        emit_initial=bool(emit_initial),
    )


def cleanup_control_page_subscriptions(owner) -> None:
    unsubscribe = getattr(owner, "_ui_state_unsubscribe", None)
    if callable(unsubscribe):
        try:
            unsubscribe()
        except Exception:
            pass
    owner._ui_state_unsubscribe = None
    owner._ui_state_store = None

    unsubscribe_runtime = getattr(owner, "_program_settings_runtime_unsubscribe", None)
    if callable(unsubscribe_runtime):
        try:
            unsubscribe_runtime()
        except Exception:
            pass
    owner._program_settings_runtime_unsubscribe = None

    runtime = getattr(owner, "_refresh_runtime", None)
    if runtime is not None:
        runtime.top_summary_pending = False
        runtime.top_summary_start_scheduled = False
        runtime.top_summary_runtime.stop(warning_prefix="Control top summary worker")
        runtime.top_summary_runtime.cancel()

        runtime.program_settings_load_pending = False
        runtime.program_settings_load_start_scheduled = False
        runtime.program_settings_load_runtime.stop(warning_prefix="Program settings load worker")
        runtime.program_settings_load_runtime.cancel()

        runtime.program_settings_save_pending.clear()
        runtime.program_settings_save_start_scheduled = False
        runtime.program_settings_save_runtime.stop(warning_prefix="Program settings save worker")
        runtime.program_settings_save_runtime.cancel()
