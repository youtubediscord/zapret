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
            updater_feature=self,
            enabled=bool(enabled),
            parent=parent,
        )

    def create_auto_check_load_worker(self, request_id: int, *, parent=None):
        from updater.settings_workers import UpdaterAutoCheckLoadWorker

        return UpdaterAutoCheckLoadWorker(
            request_id,
            updater_feature=self,
            parent=parent,
        )

    def run_startup_update_check(self) -> dict:
        return self._commands().run_startup_update_check()

    def open_update_channel(self, channel: str):
        return self._commands().open_update_channel(channel)


def build_updater_feature() -> UpdaterFeature:
    return UpdaterFeature()
