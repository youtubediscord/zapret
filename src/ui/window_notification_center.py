from __future__ import annotations

import time

from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, Qt, QTimer, pyqtSlot

from app_notifications import advisory_notification, normalize_notification_payload, notification_action
from log.log import global_logger, log
from ui.accessibility import set_control_accessibility, set_state_text
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.window_notification_actions import WindowNotificationActionHandler, WindowNotificationRuntimeActions


class WindowNotificationCenter(QObject):
    """Единый центр показа верхнеуровневых системных уведомлений."""

    def __init__(
        self,
        parent,
        *,
        startup_state,
        runtime_actions: WindowNotificationRuntimeActions,
        create_open_url_worker,
        create_notification_action_worker,
        show_tray_notification,
        show_page,
        is_window_visible,
        is_window_minimized,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._startup_state = startup_state
        self._runtime_actions = runtime_actions
        self._create_open_url_worker = create_open_url_worker
        self._create_notification_action_worker = create_notification_action_worker
        self._show_tray_notification = show_tray_notification
        self._show_page = show_page
        self._is_window_visible = is_window_visible
        self._is_window_minimized = is_window_minimized
        self._external_open_url_runtime = OneShotWorkerRuntime()
        self._notification_action_runtime = OneShotWorkerRuntime()
        self._notification_action_context: dict[int, dict[str, object]] = {}
        self._startup_notification_queue: list[dict] = []
        self._startup_notification_timer = QTimer(self)
        self._startup_notification_timer.setSingleShot(True)
        self._startup_notification_timer.timeout.connect(self.flush_startup_notification_queue)
        self._recent_signatures: dict[str, float] = {}
        self._action_handler = WindowNotificationActionHandler(
            notify=self.notify,
            runtime_actions=runtime_actions,
            show_page=self._show_page,
            open_url=self._request_external_open_url,
            request_disable_proxy=self._request_disable_proxy,
            request_disable_kaspersky_warning=self._request_disable_kaspersky_warning,
            request_disable_telega_warning=self._request_disable_telega_warning,
            request_windivert_autofix=self._request_windivert_autofix,
            request_windows_server_wlanapi_install=self._request_windows_server_wlanapi_install,
            request_launch_conflict_action=self._request_launch_conflict_action,
        )

    def register_global_error_notifier(self) -> None:
        """Подключает глобальные ERROR/CRITICAL логи к общему центру уведомлений."""
        try:
            if hasattr(global_logger, "set_ui_error_notifier"):
                global_logger.set_ui_error_notifier(self.enqueue_global_error_notification)
        except Exception as e:
            log(f"Ошибка подключения глобального error-notifier: {e}", "DEBUG")

    def enqueue_global_error_notification(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return

        self.notify_threadsafe(
            advisory_notification(
                level="error",
                title="Ошибка",
                content=text,
                source="global_logger",
                presentation="infobar",
                queue="immediate",
                duration=10000,
                dedupe_key=f"global_logger:{' '.join(text.split()).lower()}",
                dedupe_window_ms=2000,
            )
        )

    def notify_threadsafe(self, payload: dict | None) -> None:
        normalized = normalize_notification_payload(payload)
        if normalized is None:
            return

        try:
            QMetaObject.invokeMethod(
                self,
                "_notify_from_payload",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(object, dict(normalized)),
            )
        except Exception:
            self.notify(normalized)

    @pyqtSlot(object)
    def _notify_from_payload(self, payload: object) -> None:
        self.notify(payload if isinstance(payload, dict) else None)

    def notify_many(self, payloads: list[dict] | tuple[dict, ...] | None) -> None:
        for payload in payloads or ():
            self.notify(payload)

    def create_open_url_worker(self, request_id: int, *, url: str):
        return self._create_open_url_worker(request_id, url=url, parent=self)

    def _request_external_open_url(self, url: str) -> None:
        target = str(url or "").strip()
        if not target:
            return
        self._external_open_url_state_obj().request_or_start(
            target,
            self._start_external_open_url_worker,
        )

    def _start_external_open_url_worker(self, url: str) -> None:
        self._external_open_url_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_open_url_worker(request_id, url=url),
            on_loaded=self._on_external_open_url_finished,
            on_failed=self._on_external_open_url_failed,
            on_finished=self._on_external_open_url_worker_finished,
        )

    def _on_external_open_url_finished(self, request_id: int, result) -> None:
        if not self._external_open_url_runtime.is_current(request_id):
            return
        if self._external_open_url_state_obj().has_pending():
            return
        if getattr(result, "ok", False):
            return
        self._notify_external_open_url_error(str(getattr(result, "error", "") or ""))

    def _on_external_open_url_failed(self, request_id: int, error: str) -> None:
        if not self._external_open_url_runtime.is_current(request_id):
            return
        if self._external_open_url_state_obj().has_pending():
            return
        self._notify_external_open_url_error(str(error or ""))

    def _on_external_open_url_worker_finished(self, _worker) -> None:
        self._external_open_url_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_external_open_url_worker_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )

    def _schedule_external_open_url_worker_start(self, url: str) -> None:
        target = str(url or "").strip()
        if not target:
            return
        self._external_open_url_state_obj().schedule_start(
            QTimer.singleShot,
            lambda value=target: self._run_scheduled_external_open_url_worker_start(value),
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
            pending_when_already_scheduled=target,
        )

    def _run_scheduled_external_open_url_worker_start(self, url: str = "") -> None:
        pending = str(
            self._external_open_url_state_obj().take_pending_for_scheduled_start(
                cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False)
            )
            or ""
        ).strip()
        target = pending or str(url or "").strip()
        if target:
            self._start_external_open_url_worker(target)

    def _notify_external_open_url_error(self, error: str) -> None:
        self.notify(
            advisory_notification(
                level="warning",
                title="Не удалось открыть ссылку",
                content=str(error or "Ссылка не была открыта."),
                source="notification.open_url",
                presentation="infobar",
                queue="immediate",
                duration=7000,
                dedupe_key="notification.open_url.failure",
            )
        )

    def create_notification_action_worker(self, request_id: int, *, action_name: str, action_fn):
        return self._create_notification_action_worker(
            request_id,
            action_name=action_name,
            action_fn=action_fn,
            parent=self,
        )

    def _request_disable_proxy(self, bar=None) -> None:
        self._request_notification_action(
            "disable_proxy",
            self._disable_proxy_action,
            bar=bar,
        )

    def _request_disable_kaspersky_warning(self, bar=None) -> None:
        self._request_notification_action(
            "disable_kaspersky_warning",
            self._disable_kaspersky_warning_action,
            bar=bar,
        )

    def _request_disable_telega_warning(self, bar=None) -> None:
        self._request_notification_action(
            "disable_telega_warning",
            self._disable_telega_warning_action,
            bar=bar,
        )

    def _request_windivert_autofix(self, action: str, bar=None) -> None:
        value = str(action or "").strip()
        if not value:
            return
        self._request_notification_action(
            "windivert_autofix",
            lambda: self._runtime_actions.execute_windivert_autofix(value),
            bar=bar,
            context={"action": value},
        )

    def _request_windows_server_wlanapi_install(self, bar=None) -> None:
        self._request_notification_action(
            "install_windows_server_wlanapi",
            self._runtime_actions.install_windows_server_wlanapi,
            bar=bar,
        )

    def _request_launch_conflict_action(self, request_id: int, close_conflicts: bool, bar=None) -> None:
        self._request_notification_action(
            "launch_conflict_resume",
            lambda: self._runtime_actions.prepare_launch_conflict_resolution(
                int(request_id or 0),
                close_conflicts=bool(close_conflicts),
            ),
            bar=bar,
            context={
                "request_id": int(request_id or 0),
                "close_conflicts": bool(close_conflicts),
            },
        )

    def _request_notification_action(self, action_name: str, action_fn, *, bar=None, context=None) -> None:
        request = (str(action_name or "").strip(), action_fn, bar, dict(context or {}))
        self._notification_action_state_obj().request_or_start(
            request,
            lambda value: self._run_notification_action_worker(*value),
        )

    def _run_notification_action_worker(self, action_name: str, action_fn, bar, context: dict[str, object]) -> None:
        def _worker_factory(request_id: int):
            self._notification_action_context[int(request_id)] = {
                "action_name": action_name,
                "bar": bar,
                **context,
            }
            return self.create_notification_action_worker(
                request_id,
                action_name=action_name,
                action_fn=action_fn,
            )

        self._notification_action_runtime.start_qthread_worker(
            worker_factory=_worker_factory,
            on_loaded=self._on_notification_action_finished,
            on_failed=self._on_notification_action_failed,
            on_finished=self._on_notification_action_worker_finished,
        )

    @staticmethod
    def _disable_proxy_action():
        from startup.check_start import _disable_proxy

        return _disable_proxy()

    @staticmethod
    def _disable_kaspersky_warning_action() -> bool:
        from startup.kaspersky import disable_kaspersky_warning_forever

        return bool(disable_kaspersky_warning_forever())

    @staticmethod
    def _disable_telega_warning_action() -> bool:
        from startup.telega_check import disable_telega_warning_forever

        return bool(disable_telega_warning_forever())

    def _on_notification_action_finished(self, request_id: int, action_name: str, result) -> None:
        context = self._notification_action_context.pop(int(request_id), {})
        if not self._notification_action_runtime.is_current(request_id):
            return
        if self._notification_action_state_obj().has_pending():
            return

        action = str(action_name or context.get("action_name") or "")
        bar = context.get("bar")
        if action == "disable_proxy":
            self._notify_disable_proxy_result(result, bar=bar)
        elif action == "disable_kaspersky_warning":
            self._notify_disable_warning_result(
                bool(result),
                bar=bar,
                product="Kaspersky",
                source="startup.kaspersky.action",
                success_content="Предупреждение о Kaspersky больше не будет показываться.",
                failure_content="Не удалось сохранить настройку для предупреждения о Kaspersky.",
                dedupe_key="startup.kaspersky.action.disable_warning",
            )
        elif action == "disable_telega_warning":
            self._notify_disable_warning_result(
                bool(result),
                bar=bar,
                product="Telega Desktop",
                source="startup.telega.action",
                success_content="Предупреждение о Telega Desktop больше не будет показываться.",
                failure_content="Не удалось сохранить настройку для предупреждения о Telega Desktop.",
                dedupe_key="startup.telega.action.disable_warning",
            )
        elif action == "windivert_autofix":
            self._notify_windivert_autofix_result(
                result,
                bar=bar,
                action=str(context.get("action") or ""),
            )
        elif action == "install_windows_server_wlanapi":
            self._notify_windows_server_wlanapi_install_result(result, bar=bar)
        elif action == "launch_conflict_resume":
            self._finish_launch_conflict_action(result, context=context, bar=bar)

    def _on_notification_action_failed(self, request_id: int, action_name: str, error: str) -> None:
        context = self._notification_action_context.pop(int(request_id), {})
        if not self._notification_action_runtime.is_current(request_id):
            return
        if self._notification_action_state_obj().has_pending():
            return
        action = str(action_name or context.get("action_name") or "")
        bar = context.get("bar")
        if action == "disable_proxy":
            self._notify_disable_proxy_result((False, error), bar=bar)
        elif action == "disable_kaspersky_warning":
            self._notify_disable_warning_result(
                False,
                bar=bar,
                product="Kaspersky",
                source="startup.kaspersky.action",
                success_content="Предупреждение о Kaspersky больше не будет показываться.",
                failure_content="Не удалось сохранить настройку для предупреждения о Kaspersky.",
                dedupe_key="startup.kaspersky.action.disable_warning",
            )
        elif action == "disable_telega_warning":
            self._notify_disable_warning_result(
                False,
                bar=bar,
                product="Telega Desktop",
                source="startup.telega.action",
                success_content="Предупреждение о Telega Desktop больше не будет показываться.",
                failure_content="Не удалось сохранить настройку для предупреждения о Telega Desktop.",
                dedupe_key="startup.telega.action.disable_warning",
            )
        elif action == "install_windows_server_wlanapi":
            self._notify_windows_server_wlanapi_install_result((False, error), bar=bar)
        elif action == "windivert_autofix":
            self._notify_windivert_autofix_result(
                (False, error),
                bar=bar,
                action=str(context.get("action") or ""),
            )
        elif action == "launch_conflict_resume":
            self._finish_launch_conflict_action((False, error), context=context, bar=bar)

    def _on_notification_action_worker_finished(self, _worker) -> None:
        self._notification_action_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_notification_action_worker_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )

    def _schedule_notification_action_worker_start(self, request) -> None:
        if request is None:
            return
        self._notification_action_state_obj().schedule_start(
            QTimer.singleShot,
            lambda value=request: self._run_scheduled_notification_action_worker_start(value),
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
            pending_when_already_scheduled=request,
        )

    def _run_scheduled_notification_action_worker_start(self, request=None) -> None:
        pending = self._notification_action_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False)
        )
        next_request = pending if pending is not None else request
        if next_request is not None:
            self._run_notification_action_worker(*next_request)

    def _external_open_url_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_external_open_url_state")
        runtime = self.__dict__.get("_external_open_url_runtime")
        if state is None:
            pending = str(self.__dict__.pop("_external_open_url_pending", "") or "")
            start_scheduled = bool(self.__dict__.pop("_external_open_url_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value="",
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_external_open_url_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _external_open_url_pending(self):
        return self._external_open_url_state_obj().pending

    @_external_open_url_pending.setter
    def _external_open_url_pending(self, value) -> None:
        self._external_open_url_state_obj().pending = str(value or "")

    @property
    def _external_open_url_start_scheduled(self) -> bool:
        return bool(self._external_open_url_state_obj().start_scheduled)

    @_external_open_url_start_scheduled.setter
    def _external_open_url_start_scheduled(self, value: bool) -> None:
        self._external_open_url_state_obj().start_scheduled = bool(value)

    def _notification_action_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_notification_action_state")
        runtime = self.__dict__.get("_notification_action_runtime")
        if state is None:
            pending = self.__dict__.pop("_notification_action_pending", None)
            start_scheduled = bool(self.__dict__.pop("_notification_action_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_notification_action_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _notification_action_pending(self):
        return self._notification_action_state_obj().pending

    @_notification_action_pending.setter
    def _notification_action_pending(self, value) -> None:
        self._notification_action_state_obj().pending = value

    @property
    def _notification_action_start_scheduled(self) -> bool:
        return bool(self._notification_action_state_obj().start_scheduled)

    @_notification_action_start_scheduled.setter
    def _notification_action_start_scheduled(self, value: bool) -> None:
        self._notification_action_state_obj().start_scheduled = bool(value)

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

    def _notify_disable_proxy_result(self, result, *, bar=None) -> None:
        success, error = self._coerce_bool_message_result(result)
        if success:
            self._close_bar(bar)
        self.notify(
            advisory_notification(
                level="success" if success else "warning",
                title="Прокси отключен" if success else "Не удалось отключить прокси",
                content=(
                    "Ручной системный прокси был отключен."
                    if success else str(error or "Настройки прокси не были изменены.")
                ),
                source="startup.proxy.action",
                presentation="infobar",
                queue="immediate",
                duration=7000 if success else 10000,
                dedupe_key="startup.proxy.action",
            )
        )

    def _notify_disable_warning_result(
        self,
        success: bool,
        *,
        bar=None,
        product: str,
        source: str,
        success_content: str,
        failure_content: str,
        dedupe_key: str,
    ) -> None:
        if success:
            self._close_bar(bar)
        _ = product
        self.notify(
            advisory_notification(
                level="success" if success else "warning",
                title="Напоминание отключено" if success else "Не удалось отключить напоминание",
                content=success_content if success else failure_content,
                source=source,
                presentation="infobar",
                queue="immediate",
                duration=5000 if success else 8000,
                dedupe_key=dedupe_key,
            )
        )

    def _notify_windivert_autofix_result(self, result, *, bar=None, action: str = "") -> None:
        ok, message = self._coerce_bool_message_result(result)
        self._close_bar(bar)
        self.notify(
            advisory_notification(
                level="success" if ok else "warning",
                title="Готово" if ok else "Не удалось",
                content=str(message or ""),
                source="launch.autofix",
                presentation="infobar",
                queue="immediate",
                duration=5000 if ok else 8000,
                dedupe_key=f"launch.autofix:{action}",
            )
        )

    def _notify_windows_server_wlanapi_install_result(self, result, *, bar=None) -> None:
        ok, message = self._coerce_bool_message_result(result)
        self._close_bar(bar)
        self.notify(
            advisory_notification(
                level="success" if ok else "warning",
                title="Компонент установлен" if ok else "Не удалось установить компонент",
                content=str(message or ""),
                source="launch.windows_server_wlanapi",
                presentation="infobar",
                queue="immediate",
                duration=-1 if ok else 10000,
                dedupe_key="launch.windows_server_wlanapi.install_result",
            )
        )

    def _finish_launch_conflict_action(self, result, *, context: dict[str, object], bar=None) -> None:
        ok, reason = self._coerce_bool_message_result(result)
        request_id = int(context.get("request_id") or 0)
        if ok:
            self._close_bar(bar)
            try:
                self._runtime_actions.continue_start_after_conflict_resolution(request_id)
            except Exception as exc:
                log(f"Не удалось продолжить запуск после конфликта: {exc}", "DEBUG")
                self._notify_launch_conflict_action_error()
            return

        self._close_bar(bar)
        if str(reason or "") == "kill_failed":
            self._notify_launch_conflict_kill_failed(request_id)
            return
        if str(reason or "") != "stale":
            self._notify_launch_conflict_action_error()

    def _notify_launch_conflict_kill_failed(self, request_id: int) -> None:
        self.notify(
            advisory_notification(
                level="warning",
                title="Не удалось закрыть процессы",
                content=(
                    "Некоторые конфликтующие процессы не удалось закрыть.\n"
                    "Запуск DPI может завершиться ошибкой."
                ),
                source="launch.conflicting_processes.kill_failed",
                presentation="infobar",
                queue="immediate",
                duration=-1,
                dedupe_key=f"launch.conflicting_processes.kill_failed:{int(request_id or 0)}",
                dedupe_window_ms=0,
                buttons=[
                    notification_action("launch_conflict_ignore_start", "Продолжить запуск", value=request_id),
                    notification_action("launch_conflict_cancel", "Отмена", value=request_id),
                ],
            )
        )

    def _notify_launch_conflict_action_error(self) -> None:
        self.notify(
            advisory_notification(
                level="warning",
                title="Не удалось продолжить запуск",
                content="Во время обработки конфликтующих процессов произошла ошибка.",
                source="launch.conflicting_processes.action",
                presentation="infobar",
                queue="immediate",
                duration=7000,
                dedupe_key="launch.conflicting_processes.action",
            )
        )

    @staticmethod
    def _coerce_bool_message_result(result) -> tuple[bool, str]:
        if isinstance(result, (tuple, list)) and result:
            ok = bool(result[0])
            message = str(result[1] if len(result) > 1 else "")
            return ok, message
        return bool(result), ""

    @staticmethod
    def _close_bar(bar) -> None:
        try:
            if bar is not None:
                bar.close()
        except Exception:
            pass

    def notify(self, payload: dict | None) -> None:
        normalized = normalize_notification_payload(payload)
        if normalized is None:
            return

        try:
            log(
                "Notification received: "
                f"source={normalized.get('source', '')}, "
                f"level={normalized.get('level', '')}, "
                f"queue={normalized.get('queue', '')}",
                "⏱ STARTUP",
            )
        except Exception:
            pass

        if self._should_skip_duplicate(normalized):
            try:
                log(
                    f"Notification skipped as duplicate: source={normalized.get('source', '')}",
                    "⏱ STARTUP",
                )
            except Exception:
                pass
            return

        if self._show_tray_notification_if_needed(normalized):
            try:
                log(
                    f"Notification redirected to tray: source={normalized.get('source', '')}",
                    "⏱ STARTUP",
                )
            except Exception:
                pass
            return

        if self._should_enqueue_for_startup(normalized):
            self._startup_notification_queue.append(dict(normalized))
            try:
                log(
                    "Notification queued for startup display: "
                    f"source={normalized.get('source', '')}, "
                    f"queue_size={len(self._startup_notification_queue)}",
                    "⏱ STARTUP",
                )
            except Exception:
                pass
            self.schedule_startup_notification_queue()
            return

        self._present_notification(normalized)

    def can_show_startup_notification_now(self) -> bool:
        startup_state = self._startup_state
        if startup_state is None:
            return False
        if not bool(startup_state.post_init_ready):
            return False
        if not bool(startup_state.background_init_started):
            return False
        try:
            return bool(self._is_window_visible())
        except Exception:
            return False

    def schedule_startup_notification_queue(self, delay_ms: int = 0) -> None:
        if self._startup_notification_timer.isActive():
            return
        self._startup_notification_timer.start(max(0, int(delay_ms)))

    def flush_startup_notification_queue(self) -> None:
        startup_state = self._startup_state
        if startup_state is None:
            self.schedule_startup_notification_queue(300)
            return
        if not bool(startup_state.post_init_ready):
            self.schedule_startup_notification_queue(300)
            return
        if not bool(startup_state.background_init_started):
            self.schedule_startup_notification_queue(300)
            return
        if not self._is_window_visible():
            return
        if not self._startup_notification_queue:
            return

        payload = self._startup_notification_queue.pop(0)
        try:
            log(
                "Notification dequeued for display: "
                f"source={payload.get('source', '')}, "
                f"remaining={len(self._startup_notification_queue)}",
                "⏱ STARTUP",
            )
        except Exception:
            pass
        self._present_notification(payload)

        if self._startup_notification_queue:
            self.schedule_startup_notification_queue(900)

    def _should_enqueue_for_startup(self, payload: dict) -> bool:
        queue_mode = str(payload.get("queue") or "auto").lower()
        if queue_mode == "immediate":
            return False
        if queue_mode == "startup":
            return not self.can_show_startup_notification_now()

        source = str(payload.get("source") or "")
        if source.startswith(("startup.", "deferred.")):
            return not self.can_show_startup_notification_now()

        return False

    def _present_notification(self, payload: dict) -> None:
        presentation = str(payload.get("presentation") or "auto").lower()

        try:
            log(
                "Notification presenting: "
                f"source={payload.get('source', '')}, "
                f"presentation={presentation}",
                "⏱ STARTUP",
            )
        except Exception:
            pass

        self._show_infobar_notification(payload)

    def _show_infobar_notification(self, payload: dict) -> None:
        try:
            from qfluentwidgets import InfoBar as _InfoBar, InfoBarPosition as _IBPos, PushButton

            level = str(payload.get("level") or "warning").strip().lower()
            title = self._resolve_title(payload)
            content = str(payload.get("content") or "").strip()
            duration = int(payload.get("duration", 12000) or 12000)
            orient = Qt.Orientation.Vertical if len(content) > 120 or "\n" in content else Qt.Orientation.Horizontal
            position = (
                _IBPos.TOP
                if str(payload.get("source") or "").startswith(("launch.", "global_logger"))
                else _IBPos.TOP_RIGHT
            )

            factory = {
                "success": _InfoBar.success,
                "info": _InfoBar.info,
                "error": _InfoBar.error,
                "warning": _InfoBar.warning,
            }.get(level, _InfoBar.warning)

            bar = factory(
                title=title,
                content=content,
                orient=orient,
                isClosable=True,
                position=position,
                duration=duration,
                parent=self._parent,
            )
            self._apply_infobar_layout_limits(bar, content=content)
            self._set_infobar_accessibility(bar, level=level, title=title, content=content)

            for action in payload.get("buttons") or []:
                button_text = str(action.get("text") or "").strip()
                if not button_text or bar is None:
                    continue

                callback = self._action_handler.build_action_callback(action, bar)
                if callback is None:
                    continue

                btn = PushButton(button_text)
                btn.setAutoDefault(False)
                btn.setDefault(False)
                self._set_infobar_action_button_accessibility(btn, action, button_text)

                def _wrap(_checked=False, _btn=btn, _callback=callback):
                    try:
                        _btn.setEnabled(False)
                        _callback()
                    finally:
                        _btn.setEnabled(True)

                btn.clicked.connect(_wrap)
                bar.addWidget(btn)
        except Exception as e:
            log(f"Не удалось показать InfoBar уведомление: {e}", "DEBUG")

    def _apply_infobar_layout_limits(self, bar, *, content: str) -> None:
        if bar is None:
            return

        try:
            parent_width = 0
            width_fn = getattr(self._parent, "width", None)
            if callable(width_fn):
                parent_width = int(width_fn() or 0)
            max_width = 760
            if parent_width > 0:
                max_width = max(420, min(max_width, parent_width - 96))

            if callable(getattr(bar, "setMaximumWidth", None)):
                bar.setMaximumWidth(max_width)
            if callable(getattr(bar, "setMinimumWidth", None)):
                bar.setMinimumWidth(min(420, max_width))

            for label_name in ("contentLabel", "titleLabel"):
                label = getattr(bar, label_name, None)
                if label is None:
                    continue
                if callable(getattr(label, "setWordWrap", None)):
                    label.setWordWrap(True)
                if callable(getattr(label, "setMaximumWidth", None)):
                    label.setMaximumWidth(max(260, max_width - 96))

            text = str(content or "")
            if len(text) > 160 and callable(getattr(bar, "adjustSize", None)):
                bar.adjustSize()
        except Exception:
            return

    def _set_infobar_accessibility(self, bar, *, level: str, title: str, content: str) -> None:
        level_text = {
            "success": "Готово",
            "info": "Информация",
            "warning": "Предупреждение",
            "error": "Ошибка",
        }.get(str(level or "").strip().lower(), "Уведомление")
        title_text = str(title or "").strip()
        content_text = str(content or "").strip()
        if title_text:
            state_text = f"{level_text}: {title_text}"
        else:
            state_text = level_text
        if content_text:
            state_text = f"{state_text}. {content_text}"
        set_state_text(bar, state_text)
        set_control_accessibility(
            bar,
            name=state_text,
            description="Системное уведомление ZapretGUI.",
        )

    def _set_infobar_action_button_accessibility(self, button, action: dict, button_text: str) -> None:
        description = str(action.get("description") or "").strip()
        if not description:
            description = f"Выполняет действие уведомления: {button_text}."
        name = f"Действие уведомления: {button_text}"
        set_state_text(button, name)
        set_control_accessibility(
            button,
            name=name,
            description=description,
        )

    def _show_tray_notification_if_needed(self, payload: dict) -> bool:
        tray_title = str(payload.get("tray_title") or "").strip()
        tray_content = str(payload.get("tray_content") or "").strip()
        if not tray_title or not tray_content:
            return False

        if self._window_available_for_parenting():
            return False

        try:
            return bool(self._show_tray_notification(tray_title, tray_content))
        except Exception as e:
            log(f"Не удалось показать tray-уведомление: {e}", "DEBUG")
            return False

    def _window_available_for_parenting(self) -> bool:
        try:
            if not self._is_window_visible():
                return False
        except Exception:
            return False

        try:
            if self._is_window_minimized():
                return False
        except Exception:
            pass

        return True

    def _resolve_title(self, payload: dict) -> str:
        title = str(payload.get("title") or "").strip()
        if title:
            return title

        level = str(payload.get("level") or "info").strip().lower()
        return {
            "success": "Готово",
            "info": "Информация",
            "warning": "Предупреждение",
            "error": "Ошибка",
        }.get(level, "Уведомление")

    def _should_skip_duplicate(self, payload: dict) -> bool:
        self._prune_old_signatures()

        dedupe_window_ms = int(payload.get("dedupe_window_ms", 1500) or 0)
        if dedupe_window_ms <= 0:
            return False

        signature = str(payload.get("dedupe_key") or "").strip()
        if not signature:
            signature = "|".join(
                [
                    str(payload.get("source") or ""),
                    str(payload.get("level") or ""),
                    str(payload.get("title") or ""),
                    " ".join(str(payload.get("content") or "").split()),
                ]
            ).lower()

        if not signature:
            return False

        now_ts = time.time()
        last_ts = float(self._recent_signatures.get(signature, 0.0) or 0.0)
        if last_ts and (now_ts - last_ts) < (dedupe_window_ms / 1000.0):
            return True

        self._recent_signatures[signature] = now_ts
        return False

    def _prune_old_signatures(self) -> None:
        if not self._recent_signatures:
            return

        cutoff = time.time() - 30.0
        stale_keys = [key for key, ts in self._recent_signatures.items() if ts < cutoff]
        for key in stale_keys:
            self._recent_signatures.pop(key, None)
