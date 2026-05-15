from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from profile import commands as profile_internal_commands
from profile import settings as profile_settings


@dataclass(frozen=True, slots=True)
class ProfileFeature:
    _presets_feature: Any
    _app_paths: Any

    def list_profiles(self, launch_method: str):
        return profile_internal_commands.list_profiles(self, launch_method)

    def get_profile_setup(self, launch_method: str, profile_key: str):
        return profile_internal_commands.get_profile_setup(self, launch_method, profile_key)

    def apply_strategy_to_profile(self, launch_method: str, profile_key: str, strategy_id: str) -> str | None:
        return profile_internal_commands.apply_strategy_to_profile(self, launch_method, profile_key, strategy_id)

    def set_profile_enabled(self, launch_method: str, profile_key: str, enabled: bool) -> str | None:
        return profile_internal_commands.set_profile_enabled(self, launch_method, profile_key, enabled)

    def update_winws2_profile_settings(
        self,
        launch_method: str,
        profile_key: str,
        *,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
    ) -> str | None:
        return profile_internal_commands.update_winws2_profile_settings(
            self,
            launch_method,
            profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            in_range=in_range,
            out_range=out_range,
        )

    def set_current_strategy_state(
        self,
        launch_method: str,
        profile_key: str,
        *,
        rating: str | None = None,
        favorite: bool | None = None,
        clear: bool = False,
    ):
        return profile_internal_commands.set_current_strategy_state(
            self,
            launch_method,
            profile_key,
            rating=rating,
            favorite=favorite,
            clear=clear,
        )

    def set_strategy_state(
        self,
        launch_method: str,
        profile_key: str,
        strategy_id: str,
        *,
        rating: str | None = None,
        favorite: bool | None = None,
        clear: bool = False,
    ):
        return profile_internal_commands.set_strategy_state(
            self,
            launch_method,
            profile_key,
            strategy_id,
            rating=rating,
            favorite=favorite,
            clear=clear,
        )

    def delete_profile(self, launch_method: str, profile_key: str) -> bool:
        return bool(profile_internal_commands.delete_profile(self, launch_method, profile_key))

    def duplicate_profile(self, launch_method: str, profile_key: str) -> str | None:
        return profile_internal_commands.duplicate_profile(self, launch_method, profile_key)

    def move_profile_before(
        self,
        launch_method: str,
        source_profile_key: str,
        destination_profile_key: str,
    ) -> str | None:
        return profile_internal_commands.move_profile_before(
            self,
            launch_method,
            source_profile_key,
            destination_profile_key,
        )

    def move_profile_to_end(self, launch_method: str, profile_key: str) -> str | None:
        return profile_internal_commands.move_profile_to_end(self, launch_method, profile_key)

    def get_advanced_settings_state(self, launch_method: str):
        return profile_settings.get_advanced_settings_state(self, launch_method=launch_method)

    def get_wssize_enabled(self, launch_method: str) -> bool:
        return bool(profile_settings.get_wssize_enabled(self, launch_method=launch_method))

    def set_wssize_enabled(self, enabled: bool, *, launch_method: str) -> bool:
        return bool(profile_settings.set_wssize_enabled(self, bool(enabled), launch_method=launch_method))

    def get_debug_log_enabled(self, launch_method: str) -> bool:
        return bool(profile_settings.get_debug_log_enabled(self, launch_method=launch_method))

    def set_debug_log_enabled(self, enabled: bool, *, launch_method: str) -> bool:
        return bool(profile_settings.set_debug_log_enabled(self, bool(enabled), launch_method=launch_method))

    def create_advanced_settings_load_worker(self, request_id: int, parent=None):
        from profile.advanced_settings_loader import AdvancedSettingsLoadWorker

        return AdvancedSettingsLoadWorker(request_id, self, parent)
