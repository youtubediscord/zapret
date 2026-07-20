from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtCore import QTimer

from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


@dataclass(slots=True)
class TrayFeature:
    _deps: Any
    _runtime_feature: Any
    _telegram_proxy_feature: Any
    _notify: Any = None
    _log_startup_metric: Any = None
    _tray_manager: Any = None
    _opacity_save_runtime: OneShotWorkerRuntime = field(default_factory=OneShotWorkerRuntime)
    _opacity_save_runtime_worker: Any = None
    _opacity_save_state: LatestValueWorkerState | None = None
    _github_api_removal_toggle_runtime: OneShotWorkerRuntime = field(default_factory=OneShotWorkerRuntime)
    _discord_restart_toggle_runtime: OneShotWorkerRuntime = field(default_factory=OneShotWorkerRuntime)

    @staticmethod
    def _commands():
        import tray_commands

        return tray_commands

    def configure(self, *, notify=None, log_startup_metric=None) -> None:
        if notify is not None:
            self._notify = notify
        if log_startup_metric is not None:
            self._log_startup_metric = log_startup_metric

    def init(self) -> None:
        self._init_manager()

    def _init_manager(self):
        commands = self._commands()
        icon_path = commands.resolve_tray_icon_path()
        from config.build_info import APP_VERSION
        from tray import SystemTrayManager

        self._tray_manager = commands.init_tray(
            window_port=self._deps.window_port,
            icon_path=icon_path,
            app_version=APP_VERSION,
            tray_manager_factory=SystemTrayManager,
            startup_state=self._deps.startup_state,
            tray_feature=self,
            notify=self._notify,
            log_startup_metric=self._log_startup_metric,
            existing_manager=self._tray_manager,
        )
        return self._tray_manager

    def ensure_initialized(self) -> bool:
        return self._ensure_manager() is not None

    def is_initialized(self) -> bool:
        return self._manager() is not None

    def _ensure_manager(self):
        manager = self._manager()
        if manager is not None:
            return manager
        return self._init_manager()

    def _manager(self):
        return self._tray_manager

    def record_startup_metric(self, marker: str, details: str = "") -> None:
        if self._log_startup_metric is None:
            return
        self._log_startup_metric(marker, details)

    def install_post_startup(self) -> None:
        self._commands().install_post_startup_tray(
            startup_state=self._deps.startup_state,
            close_state=self._deps.close_state,
            start_in_tray=self._deps.start_in_tray,
            startup_post_init_ready=self._deps.startup_post_init_ready,
            tray_feature=self,
        )

    def show_notification_if_available(self, title: str, content: str) -> bool:
        return bool(
            self._commands().show_tray_notification_if_available(
                tray_manager=self._manager(),
                title=title,
                content=content,
            )
        )

    def hide_icon_for_exit(self) -> None:
        self._commands().hide_tray_icon_for_exit(self._manager())

    def cleanup(self) -> None:
        self._commands().cleanup_tray_for_close(self._manager())
        self._tray_manager = None

    def hide_to_tray(self, *, show_hint: bool = True) -> bool:
        manager = self._ensure_manager()
        if manager is None:
            return False
        return bool(manager.hide_to_tray(show_hint=show_hint))

    def launch_state(self) -> tuple[bool, str]:
        try:
            snapshot = self._runtime_feature.snapshot()
            running = bool(
                getattr(snapshot, "running", getattr(snapshot, "launch_running", False))
            )
            phase = (
                str(getattr(snapshot, "phase", getattr(snapshot, "launch_phase", "")) or "")
                .strip()
                .lower()
            )
            return running, phase or ("running" if running else "stopped")
        except Exception:
            return False, "stopped"

    def telegram_proxy_label(self) -> str:
        return str(self._telegram_proxy_feature.status_label())

    def connect_telegram_proxy_status_changed(self, callback) -> None:
        self._telegram_proxy_feature.connect_status_changed(callback)

    def set_telegram_proxy_enabled(self, running: bool) -> None:
        try:
            self._telegram_proxy_feature.set_enabled(bool(running))
        except Exception:
            pass

    def toggle_telegram_proxy(self) -> None:
        self._telegram_proxy_feature.toggle_async()

    def toggle_github_api_removal(self, *, status_callback=None) -> bool:
        if self._github_api_removal_toggle_runtime.is_running():
            if status_callback:
                status_callback("Переключение удаления GitHub API уже выполняется")
            return False

        self._github_api_removal_toggle_runtime.start_qthread_worker(
            worker_factory=lambda _request_id: self.create_github_api_removal_toggle_worker(parent=None),
            on_loaded=lambda _request_id, ok, message: self._on_github_api_removal_toggle_finished(
                bool(ok),
                str(message or ""),
                status_callback,
            ),
            on_failed=lambda _request_id, error: self._on_github_api_removal_toggle_failed(
                str(error or ""),
                status_callback,
            ),
            signal_includes_request_id=False,
            loaded_signal_name="completed",
        )
        return True

    def toggle_discord_restart(self, *, status_callback=None, confirm_disable=None) -> bool:
        if self._discord_restart_toggle_runtime.is_running():
            if status_callback:
                status_callback("Переключение автоперезапуска Discord уже выполняется")
            return False

        commands = self._commands()
        try:
            current = bool(commands.get_discord_restart_enabled(default=True))
        except Exception:
            current = True
        enabled = not current

        if current and callable(confirm_disable):
            try:
                if not bool(confirm_disable()):
                    return False
            except Exception:
                return False

        self._discord_restart_toggle_runtime.start_qthread_worker(
            worker_factory=lambda _request_id: self.create_discord_restart_toggle_worker(
                enabled=enabled,
                parent=None,
            ),
            on_loaded=lambda _request_id, ok, message: self._on_discord_restart_toggle_finished(
                bool(ok),
                str(message or ""),
                status_callback,
            ),
            on_failed=lambda _request_id, error: self._on_discord_restart_toggle_failed(
                str(error or ""),
                status_callback,
            ),
            signal_includes_request_id=False,
            loaded_signal_name="completed",
        )
        return True

    def apply_window_opacity(self, value: int) -> None:
        normalized = max(0, min(100, int(value)))
        self._commands().apply_window_opacity(
            set_window_opacity=self._deps.set_window_opacity,
            value=normalized,
        )
        self._request_window_opacity_save(normalized)

    def create_opacity_save_worker(self, value: int):
        from settings.appearance_workers import AppearanceSettingsSaveWorker

        return AppearanceSettingsSaveWorker(
            action="window_opacity",
            value=int(value),
            parent=None,
        )

    def create_github_api_removal_toggle_worker(self, *, parent=None):
        from tray_workers import TrayGithubApiRemovalToggleWorker

        return TrayGithubApiRemovalToggleWorker(
            toggle_github_api_removal=self._commands().toggle_github_api_removal,
            parent=parent,
        )

    def create_discord_restart_toggle_worker(self, *, enabled: bool, parent=None):
        from tray_workers import TrayDiscordRestartToggleWorker

        return TrayDiscordRestartToggleWorker(
            set_discord_restart_enabled=self._commands().set_discord_restart_enabled,
            enabled=bool(enabled),
            parent=parent,
        )

    def _on_github_api_removal_toggle_finished(self, ok: bool, message: str, status_callback) -> None:
        if status_callback and message:
            status_callback(message)

    def _on_github_api_removal_toggle_failed(self, error: str, status_callback) -> None:
        message = error or "Ошибка при переключении удаления GitHub API"
        if status_callback:
            status_callback(message)

    def _on_discord_restart_toggle_finished(self, ok: bool, message: str, status_callback) -> None:
        _ = ok
        if status_callback and message:
            status_callback(message)

    def _on_discord_restart_toggle_failed(self, error: str, status_callback) -> None:
        message = error or "Ошибка при переключении автоперезапуска Discord"
        if status_callback:
            status_callback(message)

    def _request_window_opacity_save(self, value: int) -> None:
        normalized = max(0, min(100, int(value)))
        state = self._opacity_save_state_obj()
        if state.is_busy():
            state.pending = normalized
            return
        state.pending = None
        self._start_window_opacity_save_worker(normalized)

    def _start_window_opacity_save_worker(self, value: int) -> None:
        started = self._opacity_save_runtime.start_qthread_worker(
            worker_factory=lambda _request_id: self.create_opacity_save_worker(int(value)),
            on_finished=self._on_window_opacity_save_worker_finished,
        )
        worker = started[1] if isinstance(started, tuple) and len(started) > 1 else getattr(
            self._opacity_save_runtime,
            "worker",
            None,
        )
        self._opacity_save_runtime_worker = worker

    def _on_window_opacity_save_worker_finished(self, worker) -> None:
        current_worker = self._opacity_save_runtime_worker
        if current_worker is not None and worker is not current_worker:
            return
        self._opacity_save_runtime_worker = None
        pending = self._opacity_save_state_obj().pending
        self._opacity_save_state_obj().pending = None
        if pending is not None:
            self._schedule_window_opacity_save_worker_start(int(pending))

    def _schedule_window_opacity_save_worker_start(self, value: int) -> None:
        pending = max(0, min(100, int(value)))
        state = self._opacity_save_state_obj()
        state.pending = pending
        state.schedule_start(
            QTimer.singleShot,
            self._run_scheduled_window_opacity_save_worker_start,
            pending_when_already_scheduled=pending,
        )

    def _run_scheduled_window_opacity_save_worker_start(self) -> None:
        pending = self._opacity_save_state_obj().take_pending_for_scheduled_start()
        if pending is not None:
            self._start_window_opacity_save_worker(int(pending))

    def _opacity_save_state_obj(self) -> LatestValueWorkerState:
        state = self._opacity_save_state
        if state is None:
            state = LatestValueWorkerState(self._opacity_save_runtime, empty_value=None)
            self._opacity_save_state = state
        elif getattr(state, "runtime", None) is None:
            state.runtime = self._opacity_save_runtime
        return state

    @property
    def _opacity_save_pending(self) -> int | None:
        pending = self._opacity_save_state_obj().pending
        return None if pending is None else int(pending)

    @_opacity_save_pending.setter
    def _opacity_save_pending(self, value: int | None) -> None:
        if value is None:
            self._opacity_save_state_obj().pending = None
        else:
            self._opacity_save_state_obj().pending = max(0, min(100, int(value)))

    @property
    def _opacity_save_start_scheduled(self) -> bool:
        return bool(self._opacity_save_state_obj().start_scheduled)

    @_opacity_save_start_scheduled.setter
    def _opacity_save_start_scheduled(self, value: bool) -> None:
        self._opacity_save_state_obj().start_scheduled = bool(value)


def build_tray_feature(*, deps, runtime_feature, telegram_proxy_feature) -> TrayFeature:
    return TrayFeature(
        _deps=deps,
        _runtime_feature=runtime_feature,
        _telegram_proxy_feature=telegram_proxy_feature,
    )
