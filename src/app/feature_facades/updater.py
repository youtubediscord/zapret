from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UpdaterFeature:
    @staticmethod
    def _commands():
        import updater.public as updater_commands

        return updater_commands

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
        )

    def run_startup_update_check(self) -> dict:
        return self._commands().run_startup_update_check()

    def open_update_channel(self, channel: str):
        return self._commands().open_update_channel(channel)

    def retry_server_check_without_dpi(self, *, is_any_running, shutdown_sync):
        return self._commands().retry_server_check_without_dpi(
            is_any_running=is_any_running,
            shutdown_sync=shutdown_sync,
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
