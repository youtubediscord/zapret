from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True, init=False)
class UpdaterFeature:
    _check_coordinator: Any | None = field(default=None, repr=False, compare=False)

    def __init__(self, check_coordinator: Any | None = None) -> None:
        object.__setattr__(self, "_check_coordinator", check_coordinator)

    @staticmethod
    def _commands():
        import updater.public as updater_commands

        return updater_commands

    @staticmethod
    def _create_check_coordinator():
        from core.runtime.update_check_coordinator import UpdateCheckCoordinator

        return UpdateCheckCoordinator()

    @property
    def check_coordinator(self):
        coordinator = self._check_coordinator
        if coordinator is None:
            coordinator = self._create_check_coordinator()
            object.__setattr__(self, "_check_coordinator", coordinator)
        return coordinator

    def begin_update_check(self, *, source: str) -> int | None:
        return self.check_coordinator.begin(source=source)

    def finish_update_check(self, result: dict, *, source: str, token: int) -> bool:
        return bool(
            self.check_coordinator.finish(
                dict(result or {}),
                source=source,
                token=int(token),
            )
        )

    def current_update_check_snapshot(self):
        return self.check_coordinator.snapshot()

    def subscribe_update_check(self, callback, *, emit_initial: bool = False):
        return self.check_coordinator.subscribe(callback, emit_initial=bool(emit_initial))

    def is_auto_update_enabled(self) -> bool:
        return bool(self._commands().is_auto_update_enabled())

    def set_auto_update_enabled(self, enabled: bool) -> None:
        self._commands().set_auto_update_enabled(bool(enabled))

    def create_auto_check_save_worker(self, request_id: int, *, enabled: bool, parent=None):
        from updater.settings_workers import UpdaterAutoCheckSaveWorker

        return UpdaterAutoCheckSaveWorker(
            request_id,
            enabled=bool(enabled),
            set_auto_update_enabled=self.set_auto_update_enabled,
            parent=parent,
        )

    def create_auto_check_load_worker(self, request_id: int, *, parent=None):
        from updater.settings_workers import UpdaterAutoCheckLoadWorker

        return UpdaterAutoCheckLoadWorker(
            request_id,
            is_auto_update_enabled=self.is_auto_update_enabled,
            parent=parent,
        )

    def create_update_channel_open_worker(self, request_id: int, *, channel: str, parent=None):
        from updater.settings_workers import UpdaterChannelOpenWorker

        return UpdaterChannelOpenWorker(
            request_id,
            channel=channel,
            open_update_channel=self.open_update_channel,
            parent=parent,
        )

    def create_cache_invalidate_worker(self, request_id: int, *, channel: str, context: str, parent=None):
        from updater.settings_workers import UpdaterCacheInvalidateWorker

        return UpdaterCacheInvalidateWorker(
            request_id,
            channel=channel,
            context=context,
            invalidate_update_cache=self.invalidate_update_cache,
            parent=parent,
        )

    def create_server_full_check_gate_worker(self, request_id: int, *, skip_rate_limit: bool, parent=None):
        from updater.settings_workers import UpdaterServerFullCheckGateWorker

        return UpdaterServerFullCheckGateWorker(
            request_id,
            skip_rate_limit=bool(skip_rate_limit),
            prepare_server_full_check=self.prepare_server_full_check,
            parent=parent,
        )

    def create_server_retry_without_dpi_worker(self, request_id: int, *, is_any_running, shutdown_sync, parent=None):
        from updater.retry_workers import UpdaterServerRetryWithoutDpiWorker

        return UpdaterServerRetryWithoutDpiWorker(
            request_id,
            is_any_running=is_any_running,
            shutdown_sync=shutdown_sync,
            retry_server_check_without_dpi=self.retry_server_check_without_dpi,
            parent=parent,
        )

    def create_dpi_restart_worker(self, request_id: int, *, is_available, restart, context: str, parent=None):
        from updater.retry_workers import UpdaterDpiRestartWorker

        return UpdaterDpiRestartWorker(
            request_id,
            is_available=is_available,
            restart=restart,
            restart_dpi_after_update=self.restart_dpi_after_update,
            context=context,
            parent=parent,
        )

    def create_update_install_worker(self, *, parent_window, is_any_running, shutdown_sync):
        from updater.update import UpdateWorker

        return UpdateWorker(
            parent_window,
            silent=True,
            skip_rate_limit=True,
            is_any_running=is_any_running,
            shutdown_sync=shutdown_sync,
            stop_dpi_for_download=self.stop_dpi_for_download,
        )

    def run_startup_update_check(self) -> dict:
        return self._commands().run_startup_update_check()

    def open_update_channel(self, channel: str):
        return self._commands().open_update_channel(channel)

    def prepare_server_full_check(self, *, skip_rate_limit: bool = False):
        return self._commands().prepare_server_full_check(skip_rate_limit=bool(skip_rate_limit))

    def invalidate_update_cache(self, channel: str) -> None:
        from updater import invalidate_cache

        invalidate_cache(channel)

    def retry_server_check_without_dpi(self, *, is_any_running, shutdown_sync):
        return self._commands().retry_server_check_without_dpi(
            is_any_running=is_any_running,
            shutdown_sync=shutdown_sync,
        )

    def stop_dpi_for_download(self, *, is_any_running, shutdown_sync) -> bool:
        return bool(
            self._commands().stop_dpi_for_download(
                is_any_running=is_any_running,
                shutdown_sync=shutdown_sync,
            )
        )

    def restart_dpi_after_update(self, *, is_available, restart) -> bool:
        return bool(
            self._commands().restart_dpi_after_update(
                is_available=is_available,
                restart=restart,
            )
        )


def build_updater_feature() -> UpdaterFeature:
    return UpdaterFeature()
