from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from settings.mode import normalize_launch_method

from PyQt6.QtCore import QObject, Qt, pyqtSignal


class RuntimeEventDispatcher(QObject):
    runner_failure = pyqtSignal(object)
    launch_error = pyqtSignal(str)
    active_preset_content_changed = pyqtSignal(str)


@dataclass(slots=True)
class RuntimeUiPort:
    runtime_ui_bridge: Any = None
    notify: Any = None

    def set_status(self, text: str) -> None:
        self.require_runtime_ui_bridge().set_status(str(text or ""))

    def show_launch_error(self, text: str) -> None:
        self.require_runtime_ui_bridge().show_launch_error(str(text or ""))

    def handle_runtime_content_changed(self, key: str) -> None:
        self.require_runtime_ui_bridge().handle_runtime_content_changed(str(key or ""))

    def require_runtime_ui_bridge(self):
        bridge = self.runtime_ui_bridge
        if bridge is None:
            raise RuntimeError("Runtime UI bridge is not configured")
        return bridge

    def configure_runtime_ui_bridge(self, bridge) -> None:
        self.runtime_ui_bridge = bridge

    def configure_notifications(self, *, notify) -> None:
        self.notify = notify

    def require_notifications(self):
        if self.notify is None:
            raise RuntimeError("Runtime notifications are not configured")
        return self.notify


@dataclass(frozen=True, slots=True)
class RuntimeLifecyclePort:
    startup_state: Any = None
    qt_parent: Any = None
    mark_stop_and_exit_requested_callback: Any = None

    def mark_stop_and_exit_requested(self) -> None:
        callback = self.mark_stop_and_exit_requested_callback
        if callable(callback):
            callback()


@dataclass(frozen=True, slots=True)
class RuntimeDependencies:
    presets_feature: Any
    profile_feature: Any
    orchestra_feature: Any


@dataclass(slots=True)
class RuntimeFlags:
    manually_stopped: bool = False
    intentional_start: bool = False

    def mark_manual_stop(self) -> None:
        self.manually_stopped = True

    def mark_intentional_start(self) -> None:
        self.intentional_start = True


@dataclass(slots=True)
class RuntimeObjects:
    runtime_service: Any
    process_monitor_manager: Any = None
    launch_runtime_api: Any = None
    launch_runtime: Any = None

    def snapshot(self):
        if self.runtime_service is None:
            raise RuntimeError("Runtime service is required")
        return self.runtime_service.snapshot()

    def is_available(self) -> bool:
        return self.launch_runtime is not None

    def is_running(self) -> bool:
        if self.launch_runtime is None:
            return False
        try:
            return bool(self.launch_runtime.is_running())
        except Exception:
            return False

    def is_any_running(self, *, silent: bool = True) -> bool:
        if self.launch_runtime_api is None:
            return False
        try:
            return bool(self.launch_runtime_api.is_any_running(silent=silent))
        except Exception:
            return False

    def transition_pipeline_in_progress(self, launch_method: str | None = None) -> bool:
        if self.launch_runtime is None:
            return False
        return bool(self.launch_runtime.transition_pipeline_in_progress(launch_method))

    def observe_process_details(self, details: dict | None) -> None:
        try:
            self.runtime_service.observe_process_details(dict(details or {}))
        except Exception:
            pass

    def current_process_pid(self, launch_method: str, *, refresh: bool = False) -> int | None:
        if refresh:
            manager = self.ensure_process_monitor_manager()
            if manager is None or not hasattr(manager, "refresh_now"):
                return None
            try:
                manager.refresh_now()
            except Exception:
                return None

        try:
            snapshot = self.runtime_service.snapshot()
        except Exception:
            snapshot = None
        snapshot_pid = getattr(snapshot, "pid", None)
        snapshot_running = bool(getattr(snapshot, "running", False))
        snapshot_method = str(getattr(snapshot, "launch_method", "") or "").strip().lower()
        requested_method = normalize_launch_method(launch_method, default="")
        if isinstance(snapshot_pid, int) and snapshot_running and snapshot_method == requested_method:
            return snapshot_pid
        return None

    def ensure_process_monitor_manager(self):
        if self.process_monitor_manager is None:
            from winws_runtime.monitoring import ProcessMonitorManager

            self.process_monitor_manager = ProcessMonitorManager(
                observe_process_details=self.observe_process_details,
            )
        return self.process_monitor_manager

    def cleanup_process_monitor(self) -> None:
        manager = self.process_monitor_manager
        if manager is not None:
            manager.stop_monitoring()


@dataclass(slots=True)
class RuntimeEvents:
    runtime_service: Any
    ui_port: Any = None
    ui_state: Any = None
    qt_parent: Any = None
    dispatcher: RuntimeEventDispatcher | None = None

    def ensure_dispatcher(self) -> RuntimeEventDispatcher:
        if self.dispatcher is None:
            dispatcher = RuntimeEventDispatcher(self.qt_parent)
            dispatcher.runner_failure.connect(
                self.handle_runner_failure,
                Qt.ConnectionType.QueuedConnection,
            )
            dispatcher.launch_error.connect(
                self.handle_launch_error,
                Qt.ConnectionType.QueuedConnection,
            )
            dispatcher.active_preset_content_changed.connect(
                self.handle_active_preset_content_changed,
                Qt.ConnectionType.QueuedConnection,
            )
            self.dispatcher = dispatcher
        return self.dispatcher

    def publish_runner_failure(self, *, launch_method: str, error: str = "") -> None:
        self.ensure_dispatcher().runner_failure.emit(
            {
                "launch_method": str(launch_method or "").strip().lower(),
                "error": str(error or "").strip(),
            }
        )

    def publish_launch_error(self, error: str = "") -> None:
        text = str(error or "").strip()
        if text:
            self.ensure_dispatcher().launch_error.emit(text)

    def publish_active_preset_content_changed(self, path: str) -> None:
        normalized_path = str(path or "").strip()
        if normalized_path:
            self.ensure_dispatcher().active_preset_content_changed.emit(normalized_path)

    def handle_runner_failure(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        launch_method = str(payload.get("launch_method") or "").strip().lower()
        try:
            from settings.mode import is_preset_launch_method

            if not is_preset_launch_method(launch_method):
                return
        except Exception:
            return

        error_text = str(payload.get("error") or "").strip()
        self.mark_start_failed_if_current(
            launch_method=launch_method,
            error_text=error_text,
        )
        if error_text and self.ui_port is not None:
            try:
                self.ui_port.show_launch_error(error_text)
            except Exception:
                pass

    def handle_launch_error(self, error: str) -> None:
        if self.ui_port is None:
            return
        try:
            self.ui_port.show_launch_error(str(error or ""))
        except Exception:
            pass

    def mark_start_failed_if_current(
        self,
        *,
        launch_method: str,
        error_text: str,
    ) -> bool:
        method = str(launch_method or "").strip().lower()
        snapshot = self.runtime_service.snapshot()
        current_method = str(snapshot.launch_method or "").strip().lower()
        if current_method and current_method != method and snapshot.phase in {"starting", "running", "autostart_pending"}:
            return False
        self.runtime_service.mark_start_failed(
            str(error_text or "").strip() or "Запуск завершился ошибкой",
        )
        return True

    def handle_active_preset_content_changed(self, path: str) -> None:
        if self.ui_port is None:
            return
        try:
            self.ui_port.handle_runtime_content_changed(path)
        except Exception:
            pass


@dataclass(slots=True)
class RuntimeCommandPort:
    owner: Any

    @staticmethod
    def _runtime_commands():
        from winws_runtime.runtime import commands as runtime_commands

        return runtime_commands

    def current_strategy_runner(self):
        runtime_commands = self._runtime_commands()
        return runtime_commands.get_current_strategy_runner()

    def _mark_startup_runtime_init_failed(self, exc: Exception) -> None:
        runtime_service = self.owner.objects.runtime_service
        try:
            runtime_service.set_busy(False)
        except Exception:
            pass
        try:
            runtime_service.mark_start_failed(str(exc or "").strip() or "Ошибка подготовки запуска")
        except Exception:
            pass

    def init_launch_runtime_api(self) -> None:
        runtime_commands = self._runtime_commands()
        try:
            self.owner.objects.launch_runtime_api = runtime_commands.init_launch_runtime_api(runtime_feature=self.owner)
        except Exception as exc:
            self._mark_startup_runtime_init_failed(exc)
            raise

    def init_launch_runtime(self) -> None:
        runtime_commands = self._runtime_commands()
        try:
            notify = self.owner.ui_port.require_notifications()
            self.owner.objects.launch_runtime = runtime_commands.init_launch_runtime(
                runtime_feature=self.owner,
                runtime_api=self.owner.objects.launch_runtime_api,
                notify=notify,
            )
            self.owner.objects.runtime_service.set_busy(False)
        except Exception as exc:
            self._mark_startup_runtime_init_failed(exc)
            raise

    def init_process_monitor(self) -> None:
        runtime_commands = self._runtime_commands()
        runtime_commands.init_process_monitor(
            process_monitor_manager=self.owner.objects.ensure_process_monitor_manager(),
            runtime_api=self.owner.objects.launch_runtime_api,
            runtime_service=self.owner.objects.runtime_service,
        )

    def init_core_startup(self) -> None:
        runtime_commands = self._runtime_commands()
        runtime_commands.init_core_startup()

    def start(
        self,
        selected_mode: Any = None,
        launch_method: Any = None,
        *,
        skip_conflict_prompt: bool = False,
        startup_autostart: bool = False,
    ) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.start_dpi_async(
                runtime_feature=self.owner,
                selected_mode=selected_mode,
                launch_method=launch_method,
                skip_conflict_prompt=skip_conflict_prompt,
                startup_autostart=startup_autostart,
            )
        )

    def stop(
        self,
        *,
        force_cleanup: bool = False,
        cleanup_services: bool = False,
    ) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.stop_dpi_async(
                runtime_feature=self.owner,
                force_cleanup=force_cleanup,
                cleanup_services=cleanup_services,
            )
        )

    def restart(self, *, force_full_stop: bool = False) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.restart_dpi_async(
                runtime_feature=self.owner,
                force_full_stop=force_full_stop,
            )
        )

    def switch_preset(self, method: str | None = None) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(runtime_commands.switch_presets_async(runtime_feature=self.owner, method=method))

    def stop_and_exit(self) -> bool:
        runtime_commands = self._runtime_commands()
        self.owner.lifecycle.mark_stop_and_exit_requested()
        return bool(runtime_commands.stop_and_exit_async(runtime_feature=self.owner))

    def cleanup_threads(self) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(runtime_commands.cleanup_launch_threads(runtime_feature=self.owner))

    def shutdown_sync(
        self,
        *,
        reason: str = "",
        include_cleanup: bool = True,
        cleanup_services: bool = True,
        update_runtime_state: bool = True,
    ):
        runtime_commands = self._runtime_commands()
        return runtime_commands.shutdown_runtime_sync(
            runtime_feature=self.owner,
            reason=reason,
            include_cleanup=include_cleanup,
            cleanup_services=cleanup_services,
            update_runtime_state=update_runtime_state,
        )

    def start_autostart(self, launch_method: str | None = None) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.start_dpi_autostart(
                self.owner.lifecycle.startup_state,
                runtime_feature=self.owner,
                ui_state=self.owner.events.ui_state,
                launch_method=launch_method,
            )
        )

    def handle_launch_method_changed(self, method: str, *, set_status=None):
        runtime_commands = self._runtime_commands()
        return runtime_commands.handle_launch_method_changed(
            method,
            runtime_feature=self.owner,
            ui_state=self.owner.events.ui_state,
            set_status=set_status,
        )

    def apply_selected_source_preset(
        self,
        *,
        launch_method: str,
        reason: str,
        preset_file_name: str = "",
    ) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.request_selected_source_preset_apply(
                runtime_feature=self.owner,
                launch_method=launch_method,
                reason=reason,
                preset_file_name=preset_file_name,
            )
        )

    def apply_preset_content(
        self,
        *,
        launch_method: str,
        reason: str,
        profile_key: str | None = None,
    ) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.request_preset_runtime_content_apply(
                runtime_feature=self.owner,
                launch_method=launch_method,
                reason=reason,
                profile_key=profile_key,
            )
        )

    def create_preset_runtime_coordinator(self, **kwargs):
        runtime_commands = self._runtime_commands()
        return runtime_commands.create_preset_runtime_coordinator(
            qt_parent=self.owner.lifecycle.qt_parent,
            runtime_feature=self.owner,
            **kwargs,
        )

    def resume_start_after_conflict_resolution(
        self,
        request_id: int,
        *,
        close_conflicts: bool,
    ) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.resume_start_after_conflict_resolution(
                request_id,
                runtime_feature=self.owner,
                close_conflicts=close_conflicts,
            )
        )

    def prepare_launch_conflict_resolution(self, request_id: int, *, close_conflicts: bool) -> tuple[bool, str]:
        runtime_commands = self._runtime_commands()
        return runtime_commands.prepare_launch_conflict_resolution(
            request_id,
            runtime_feature=self.owner,
            close_conflicts=close_conflicts,
        )

    def continue_start_after_conflict_resolution(self, request_id: int) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.continue_start_after_conflict_resolution(
                request_id,
                runtime_feature=self.owner,
            )
        )

    def cancel_start_after_conflict_prompt(self, request_id: int) -> bool:
        runtime_commands = self._runtime_commands()
        return bool(
            runtime_commands.cancel_start_after_conflict_prompt(
                request_id,
                runtime_feature=self.owner,
            )
        )

    def execute_windivert_autofix(self, action: str) -> tuple[bool, str]:
        runtime_commands = self._runtime_commands()
        return runtime_commands.execute_windivert_autofix(action)

    def install_windows_server_wlanapi(self) -> tuple[bool, str]:
        runtime_commands = self._runtime_commands()
        return runtime_commands.install_windows_server_wlanapi()
