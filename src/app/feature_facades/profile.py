from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProfileFeature:
    _presets_feature: Any
    _app_paths: Any
    _preset_service_cache: dict[str, Any] = field(default_factory=dict, init=False, repr=False, compare=False)

    @staticmethod
    def _commands():
        from profile import commands as profile_internal_commands

        return profile_internal_commands

    @staticmethod
    def _settings():
        from profile import settings as profile_settings

        return profile_settings

    def list_profiles(self, launch_method: str):
        return self._commands().list_profiles(self, launch_method)

    def count_enabled_profiles(self, launch_method: str) -> int:
        return int(self._commands().count_enabled_profiles(self, launch_method))

    def get_enabled_profile_count_snapshot(self, launch_method: str) -> int | None:
        return self._commands().get_enabled_profile_count_snapshot(self, launch_method)

    def get_profile_strategy_display_state(self, launch_method: str, max_items: int = 2):
        return self._commands().get_profile_strategy_display_state(self, launch_method, max_items=max_items)

    def get_profile_selection_details(
        self,
        launch_method: str,
        *,
        selected_profile_key: str = "",
        max_items: int = 2,
    ):
        return self._commands().get_profile_selection_details(
            self,
            launch_method,
            selected_profile_key=selected_profile_key,
            max_items=max_items,
        )

    def get_profile_setup(self, launch_method: str, profile_key: str):
        return self._commands().get_profile_setup(self, launch_method, profile_key)

    def get_profile_list_file_editor_state(
        self,
        launch_method: str,
        profile_key: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ):
        return self._commands().get_profile_list_file_editor_state(
            self,
            launch_method,
            profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
        )

    def apply_strategy_to_profile(self, launch_method: str, profile_key: str, strategy_id: str) -> str | None:
        return self._commands().apply_strategy_to_profile(self, launch_method, profile_key, strategy_id)

    def set_profile_enabled(
        self,
        launch_method: str,
        profile_key: str,
        enabled: bool,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> str | None:
        return self._commands().set_profile_enabled(
            self,
            launch_method,
            profile_key,
            enabled,
            filter_kind=filter_kind,
            filter_value=filter_value,
        )

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
        return self._commands().update_winws2_profile_settings(
            self,
            launch_method,
            profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            in_range=in_range,
            out_range=out_range,
        )

    def update_profile_raw_text(
        self,
        launch_method: str,
        profile_key: str,
        raw_text: str,
    ) -> str | None:
        return self._commands().update_profile_raw_text(
            self,
            launch_method,
            profile_key,
            raw_text,
        )

    def validate_profile_list_file_text(
        self,
        launch_method: str,
        kind: str,
        text: str,
    ) -> tuple[tuple[int, str], ...]:
        return self._commands().validate_profile_list_file_text(
            self,
            launch_method,
            kind,
            text,
        )

    def save_profile_list_file_text(
        self,
        launch_method: str,
        profile_key: str,
        text: str,
    ):
        return self._commands().save_profile_list_file_text(
            self,
            launch_method,
            profile_key,
            text,
        )

    def set_profile_filter_kind(self, launch_method: str, profile_key: str, filter_kind: str) -> str | None:
        return self._commands().set_profile_filter_kind(self, launch_method, profile_key, filter_kind)

    def set_current_strategy_state(
        self,
        launch_method: str,
        profile_key: str,
        *,
        rating: str | None = None,
        favorite: bool | None = None,
        clear: bool = False,
    ):
        return self._commands().set_current_strategy_state(
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
        return self._commands().set_strategy_state(
            self,
            launch_method,
            profile_key,
            strategy_id,
            rating=rating,
            favorite=favorite,
            clear=clear,
        )

    def delete_profile(self, launch_method: str, profile_key: str) -> bool:
        return bool(self._commands().delete_profile(self, launch_method, profile_key))

    def duplicate_profile(self, launch_method: str, profile_key: str) -> str | None:
        return self._commands().duplicate_profile(self, launch_method, profile_key)

    def move_profile_before(
        self,
        launch_method: str,
        source_profile_key: str,
        destination_profile_key: str,
    ) -> str | None:
        return self._commands().move_profile_before(
            self,
            launch_method,
            source_profile_key,
            destination_profile_key,
        )

    def move_profile_to_end(self, launch_method: str, profile_key: str) -> str | None:
        return self._commands().move_profile_to_end(self, launch_method, profile_key)

    def create_user_profile(self, *, name: str, protocol: str, ports: str) -> str:
        return self._commands().create_user_profile(
            self,
            name=name,
            protocol=protocol,
            ports=ports,
        )

    def update_user_profile(self, profile_id: str, *, name: str, protocol: str, ports: str) -> int:
        return int(self._commands().update_user_profile(
            self,
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        ))

    def delete_user_profile(self, profile_id: str) -> int:
        return int(self._commands().delete_user_profile(self, profile_id))

    def get_additional_settings_state(self, launch_method: str):
        return self._settings().get_additional_settings_state(self, launch_method=launch_method)

    def get_wssize_enabled(self, launch_method: str) -> bool:
        return bool(self._settings().get_wssize_enabled(self, launch_method=launch_method))

    def set_wssize_enabled(self, enabled: bool, *, launch_method: str) -> bool:
        return bool(self._settings().set_wssize_enabled(self, bool(enabled), launch_method=launch_method))

    def get_debug_log_enabled(self, launch_method: str) -> bool:
        return bool(self._settings().get_debug_log_enabled(self, launch_method=launch_method))

    def set_debug_log_enabled(self, enabled: bool, *, launch_method: str) -> bool:
        return bool(self._settings().set_debug_log_enabled(self, bool(enabled), launch_method=launch_method))

    def create_additional_settings_load_worker(self, request_id: int, parent=None, *, launch_method: str):
        from profile.additional_settings_loader import AdditionalSettingsLoadWorker

        return AdditionalSettingsLoadWorker(request_id, self, launch_method=launch_method, parent=parent)

    def create_profile_list_load_worker(self, request_id: int, launch_method: str, parent=None):
        from profile.profile_list_loader import ProfileListLoadWorker

        return ProfileListLoadWorker(request_id, self, launch_method, parent)
