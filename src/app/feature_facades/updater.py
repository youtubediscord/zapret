from __future__ import annotations

from dataclasses import dataclass

import updater.public as updater_commands


@dataclass(frozen=True, slots=True)
class UpdaterFeature:
    def is_auto_update_enabled(self) -> bool:
        return bool(updater_commands.is_auto_update_enabled())

    def set_auto_update_enabled(self, enabled: bool) -> None:
        updater_commands.set_auto_update_enabled(bool(enabled))

    def run_startup_update_check(self) -> dict:
        return updater_commands.run_startup_update_check()


def build_updater_feature() -> UpdaterFeature:
    return UpdaterFeature()
