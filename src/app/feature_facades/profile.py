from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from profile.key_resolution import PresetProfileMoveResult
from profile.state import StrategyApplyResult
from ui.performance_metrics import log_ui_timing_since


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

    def get_cached_profile_list(self, launch_method: str):
        return self._commands().get_cached_profile_list(self, launch_method)

    def peek_cached_profile_list(self, launch_method: str):
        return self._commands().peek_cached_profile_list(self, launch_method)

    def warm_profile_list(self, launch_method: str):
        from settings.mode import normalize_launch_method
        from profile.profile_list_loader import ProfileListLoadResult
        from profile.list_view_state import build_profile_list_view_state

        method = normalize_launch_method(launch_method)
        service = self._commands()._profile_preset_service(self, method)
        started_at = time.perf_counter()
        payload = service.list_profiles()
        log_ui_timing_since("warmup", method, "profile_warmup.list_profiles", started_at, important=True)
        started_at = time.perf_counter()
        view_state = build_profile_list_view_state(tuple(getattr(payload, "items", ()) or ()))
        log_ui_timing_since("warmup", method, "profile_warmup.view_state", started_at, important=True)
        return ProfileListLoadResult(
            payload=payload,
            view_state=view_state,
        )

    def list_preset_order_profiles(self, launch_method: str):
        return self._commands().list_preset_order_profiles(self, launch_method)

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

    def create_profile_setup_load_worker(self, request_id: int, launch_method: str, *, profile_key: str, parent=None):
        from profile.profile_setup_loader import ProfileSetupLoadWorker

        clean_launch_method = str(launch_method or "")

        def _load_profile_setup(profile_key: str):
            return self.get_profile_setup(clean_launch_method, profile_key)

        return ProfileSetupLoadWorker(
            request_id,
            _load_profile_setup,
            profile_key,
            parent,
        )

    def create_profile_list_file_load_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_key: str,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileListFileLoadWorker

        clean_launch_method = str(launch_method or "")

        def _load_list_file_editor_state(
            profile_key: str,
            *,
            filter_kind: str = "",
            filter_value: str = "",
        ):
            return self.get_profile_list_file_editor_state(
                clean_launch_method,
                profile_key,
                filter_kind=filter_kind,
                filter_value=filter_value,
            )

        return ProfileListFileLoadWorker(
            request_id,
            _load_list_file_editor_state,
            profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            parent=parent,
        )

    def create_profile_list_file_save_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_key: str,
        text: str,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileListFileSaveWorker

        clean_launch_method = str(launch_method or "")

        def _save_list_file_text(
            *,
            profile_key: str,
            text: str,
            filter_kind: str = "",
            filter_value: str = "",
        ):
            return self.save_profile_list_file_text(
                clean_launch_method,
                profile_key,
                text,
                filter_kind=filter_kind,
                filter_value=filter_value,
            )

        def _load_profile_setup(profile_key: str):
            return self.get_profile_setup(clean_launch_method, profile_key)

        return ProfileListFileSaveWorker(
            request_id,
            _save_list_file_text,
            _load_profile_setup,
            profile_key,
            text,
            filter_kind=filter_kind,
            filter_value=filter_value,
            parent=parent,
        )

    def create_profile_list_file_validation_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        kind: str,
        text: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileListFileValidationWorker

        clean_launch_method = str(launch_method or "")

        def _validate_list_file_text(*, kind: str, text: str):
            return self.validate_profile_list_file_text(clean_launch_method, kind, text)

        return ProfileListFileValidationWorker(
            request_id,
            _validate_list_file_text,
            kind=kind,
            text=text,
            parent=parent,
        )

    def create_profile_settings_save_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_key: str,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileSettingsSaveWorker

        clean_launch_method = str(launch_method or "")

        def _save_settings(
            *,
            profile_key: str,
            filter_kind: str,
            filter_value: str,
            in_range: str,
            out_range: str,
        ):
            return self.update_winws2_profile_settings(
                clean_launch_method,
                profile_key,
                filter_kind=filter_kind,
                filter_value=filter_value,
                in_range=in_range,
                out_range=out_range,
            )

        def _load_profile_setup(profile_key: str):
            return self.get_profile_setup(clean_launch_method, profile_key)

        return ProfileSettingsSaveWorker(
            request_id,
            _save_settings,
            _load_profile_setup,
            profile_key=profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            in_range=in_range,
            out_range=out_range,
            parent=parent,
        )

    def create_profile_raw_text_save_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_key: str,
        raw_text: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileRawTextSaveWorker

        clean_launch_method = str(launch_method or "")

        def _save_raw_text(*, profile_key: str, raw_text: str):
            return self.update_profile_raw_text(clean_launch_method, profile_key, raw_text)

        def _load_profile_setup(profile_key: str):
            return self.get_profile_setup(clean_launch_method, profile_key)

        return ProfileRawTextSaveWorker(
            request_id,
            _save_raw_text,
            _load_profile_setup,
            profile_key,
            raw_text,
            parent,
        )

    def create_profile_enabled_save_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_key: str,
        enabled: bool,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileEnabledSaveWorker

        clean_launch_method = str(launch_method or "")

        def _set_enabled(
            *,
            profile_key: str,
            enabled: bool,
            filter_kind: str = "",
            filter_value: str = "",
        ):
            return self.set_profile_enabled(
                clean_launch_method,
                profile_key,
                enabled,
                filter_kind=filter_kind,
                filter_value=filter_value,
            )

        def _load_profile_setup(profile_key: str):
            return self.get_profile_setup(clean_launch_method, profile_key)

        return ProfileEnabledSaveWorker(
            request_id,
            _set_enabled,
            _load_profile_setup,
            profile_key=profile_key,
            enabled=enabled,
            filter_kind=filter_kind,
            filter_value=filter_value,
            parent=parent,
        )

    def create_profile_user_update_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileUserProfileUpdateWorker, load_user_profile_items_from_payload

        clean_launch_method = str(launch_method or "")

        def _update_user_profile(*, profile_id: str, name: str, protocol: str, ports: str) -> int:
            return self.update_user_profile(
                profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
            )

        def _load_user_profile_items(profile_id: str):
            return load_user_profile_items_from_payload(lambda: self.list_profiles(clean_launch_method), profile_id)

        return ProfileUserProfileUpdateWorker(
            request_id,
            _update_user_profile,
            _load_user_profile_items,
            profile_id=profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=parent,
        )

    def create_profile_user_delete_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_id: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileUserProfileDeleteWorker

        def _delete_user_profile(*, profile_id: str) -> int:
            return self.delete_user_profile(profile_id)

        return ProfileUserProfileDeleteWorker(
            request_id,
            _delete_user_profile,
            profile_id=profile_id,
            parent=parent,
        )

    def create_profile_strategy_apply_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_key: str,
        strategy_id: str,
        strategy_branch_id: str = "",
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileStrategyApplyWorker

        clean_launch_method = str(launch_method or "")

        def _apply_strategy(*, profile_key: str, strategy_id: str, strategy_branch_id: str = ""):
            return self.apply_strategy_to_profile(
                clean_launch_method,
                profile_key,
                strategy_id,
                strategy_branch_id=strategy_branch_id,
            )

        def _load_profile_setup(profile_key: str):
            return self.get_profile_setup(clean_launch_method, profile_key)

        return ProfileStrategyApplyWorker(
            request_id,
            _apply_strategy,
            _load_profile_setup,
            profile_key,
            strategy_id,
            strategy_branch_id,
            parent,
        )

    def create_profile_strategy_feedback_save_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_key: str,
        strategy_id: str,
        rating: str | None = None,
        favorite: bool | None = None,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileStrategyFeedbackSaveWorker

        clean_launch_method = str(launch_method or "")

        def _save_feedback(
            *,
            profile_key: str,
            rating: str | None = None,
            favorite: bool | None = None,
        ):
            return self.set_current_strategy_state(
                clean_launch_method,
                profile_key,
                rating=rating,
                favorite=favorite,
            )

        return ProfileStrategyFeedbackSaveWorker(
            request_id,
            _save_feedback,
            profile_key=profile_key,
            strategy_id=strategy_id,
            rating=rating,
            favorite=favorite,
            parent=parent,
        )

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

    def apply_strategy_to_profile(
        self,
        launch_method: str,
        profile_key: str,
        strategy_id: str,
        *,
        strategy_branch_id: str = "",
    ) -> StrategyApplyResult:
        return self._commands().apply_strategy_to_profile(
            self,
            launch_method,
            profile_key,
            strategy_id,
            strategy_branch_id=strategy_branch_id,
        )

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
    ) -> tuple[str, str] | None:
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
    ) -> tuple[str, str] | None:
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
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ):
        return self._commands().save_profile_list_file_text(
            self,
            launch_method,
            profile_key,
            text,
            filter_kind=filter_kind,
            filter_value=filter_value,
        )

    def set_profile_filter_kind(self, launch_method: str, profile_key: str, filter_kind: str) -> tuple[str, str] | None:
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
        *,
        destination_folder_key: str = "",
    ) -> str | None:
        return self._commands().move_profile_before(
            self,
            launch_method,
            source_profile_key,
            destination_profile_key,
            destination_folder_key=destination_folder_key,
        )

    def move_profile_after(
        self,
        launch_method: str,
        source_profile_key: str,
        destination_profile_key: str,
        *,
        destination_folder_key: str = "",
    ) -> str | None:
        return self._commands().move_profile_after(
            self,
            launch_method,
            source_profile_key,
            destination_profile_key,
            destination_folder_key=destination_folder_key,
        )

    def move_profile_to_end(self, launch_method: str, profile_key: str) -> str | None:
        return self._commands().move_profile_to_end(self, launch_method, profile_key)

    def move_profile_to_folder(self, launch_method: str, profile_key: str, folder_key: str) -> str | None:
        return self._commands().move_profile_to_folder(self, launch_method, profile_key, folder_key)

    def move_preset_profile_before(
        self,
        launch_method: str,
        source_profile_key: str,
        destination_profile_key: str,
    ) -> PresetProfileMoveResult | None:
        return self._commands().move_preset_profile_before(
            self,
            launch_method,
            source_profile_key,
            destination_profile_key,
        )

    def move_preset_profile_after(
        self,
        launch_method: str,
        source_profile_key: str,
        destination_profile_key: str,
    ) -> PresetProfileMoveResult | None:
        return self._commands().move_preset_profile_after(
            self,
            launch_method,
            source_profile_key,
            destination_profile_key,
        )

    def move_preset_profile_to_end(self, launch_method: str, profile_key: str) -> PresetProfileMoveResult | None:
        return self._commands().move_preset_profile_to_end(self, launch_method, profile_key)

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

        settings_api = self._settings()

        clean_launch_method = str(launch_method or "")

        def _load_additional_settings_state():
            return settings_api.get_additional_settings_state(self, launch_method=clean_launch_method)

        return AdditionalSettingsLoadWorker(
            request_id,
            _load_additional_settings_state,
            parent=parent,
        )

    def create_profile_list_load_worker(
        self,
        request_id: int,
        launch_method: str,
        parent=None,
        *,
        view_state_options: dict[str, Any] | None = None,
    ):
        from profile.profile_list_loader import ProfileListLoadResult, ProfileListLoadWorker
        from profile.list_view_state import build_profile_list_view_state

        service = self._commands()._profile_preset_service(self, launch_method)
        options = dict(view_state_options or {})
        active_profile_types = options.get("active_profile_types")
        search_query = str(options.get("search_query") or "")
        show_only_added = bool(options.get("show_only_added", False))
        group_expanded = options.get("group_expanded")

        def _build_profile_list_result(payload):
            return ProfileListLoadResult(
                payload=payload,
                view_state=build_profile_list_view_state(
                    tuple(getattr(payload, "items", ()) or ()),
                    active_profile_types=active_profile_types if isinstance(active_profile_types, set) else None,
                    search_query=search_query,
                    show_only_added=show_only_added,
                    group_expanded=group_expanded if isinstance(group_expanded, dict) else None,
                ),
            )

        def _load_profile_list_result():
            return _build_profile_list_result(service.list_profiles())

        return ProfileListLoadWorker(request_id, _load_profile_list_result, None, parent)

    def create_profile_order_load_worker(self, request_id: int, launch_method: str, parent=None):
        from profile.profile_order_loader import ProfileOrderListLoadWorker
        from profile.order_view_state import build_profile_order_list_view_state

        service = self._commands()._profile_preset_service(self, launch_method)
        return ProfileOrderListLoadWorker(
            request_id,
            service.list_preset_order_profiles,
            build_profile_order_list_view_state,
            parent,
        )

    def create_preset_profile_order_move_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        action: str,
        source_profile_key: str,
        destination_profile_key: str = "",
        parent=None,
    ):
        from profile.profile_order_loader import ProfilePresetOrderMoveWorker

        service = self._commands()._profile_preset_service(self, launch_method)
        return ProfilePresetOrderMoveWorker(
            request_id,
            service.move_preset_profile_before,
            service.move_preset_profile_after,
            service.move_preset_profile_to_end,
            action=action,
            source_profile_key=source_profile_key,
            destination_profile_key=destination_profile_key,
            parent=parent,
        )

    def create_profile_context_action_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        action: str,
        profile_key: str,
        enabled: bool | None = None,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfilePresetProfileActionWorker, load_profile_item_from_payload

        service = self._commands()._profile_preset_service(self, launch_method)
        return ProfilePresetProfileActionWorker(
            request_id,
            service.set_profile_enabled,
            service.duplicate_profile,
            service.delete_profile,
            lambda profile_key: load_profile_item_from_payload(service.list_profiles, profile_key),
            action=action,
            profile_key=profile_key,
            enabled=enabled,
            parent=parent,
        )

    def create_profile_item_refresh_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        old_profile_key: str,
        profile_key: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileItemRefreshWorker, load_profile_item_from_payload

        service = self._commands()._profile_preset_service(self, launch_method)
        return ProfileItemRefreshWorker(
            request_id,
            lambda profile_key: load_profile_item_from_payload(service.list_profiles, profile_key),
            old_profile_key=old_profile_key,
            profile_key=profile_key,
            parent=parent,
        )

    def create_profile_move_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        action: str,
        source_profile_key: str,
        destination_profile_key: str = "",
        destination_group_key: str = "",
        parent=None,
    ):
        from profile.profile_setup_loader import ProfilePresetProfileMoveWorker

        service = self._commands()._profile_preset_service(self, launch_method)
        return ProfilePresetProfileMoveWorker(
            request_id,
            service.move_profile_before,
            service.move_profile_after,
            service.move_profile_to_end,
            service.move_profile_to_folder,
            action=action,
            source_profile_key=source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
            parent=parent,
        )

    def create_user_profile_create_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileUserProfileCreateWorker, load_user_profile_items_from_payload

        service = self._commands()._profile_preset_service(self, launch_method)
        return ProfileUserProfileCreateWorker(
            request_id,
            service.create_user_profile,
            lambda profile_id: load_user_profile_items_from_payload(service.list_profiles, profile_id),
            name=name,
            protocol=protocol,
            ports=ports,
            parent=parent,
        )

    def create_user_profile_update_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileUserProfileUpdateWorker, load_user_profile_items_from_payload

        service = self._commands()._profile_preset_service(self, launch_method)
        return ProfileUserProfileUpdateWorker(
            request_id,
            service.update_user_profile,
            lambda profile_id: load_user_profile_items_from_payload(service.list_profiles, profile_id),
            profile_id=profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=parent,
        )

    def create_user_profile_delete_worker(self, request_id: int, launch_method: str, *, profile_id: str, parent=None):
        from profile.profile_setup_loader import ProfileUserProfileDeleteWorker

        service = self._commands()._profile_preset_service(self, launch_method)
        return ProfileUserProfileDeleteWorker(
            request_id,
            service.delete_user_profile,
            profile_id=profile_id,
            parent=parent,
        )

    def create_profile_folder_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        launch_method: str = "",
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        collapsed_by_key: dict[str, bool] | None = None,
        context_extra: dict | None = None,
        parent=None,
    ):
        from profile.folders import (
            create_profile_folder,
            delete_profile_folder,
            load_profile_folder_state,
            move_profile_folder_by_step,
            rename_profile_folder,
            reset_profile_folders,
            set_profile_folder_collapsed,
            set_profile_folders_collapsed,
        )
        from profile.profile_setup_loader import ProfileFolderActionWorker

        def _reset_profile_folders():
            # Сброс = дефолтные папки + раскладка живых профилей по начальному
            # правилу; раскладку считает сервис выбранного launch_method.
            assignments: dict[str, str] = {}
            if launch_method:
                try:
                    service = self._commands()._profile_preset_service(self, launch_method)
                    assignments = service.profile_folder_reset_assignments()
                except Exception:
                    assignments = {}
            return reset_profile_folders(assignments)

        return ProfileFolderActionWorker(
            request_id,
            load_profile_folder_state,
            create_profile_folder,
            rename_profile_folder,
            delete_profile_folder,
            move_profile_folder_by_step,
            set_profile_folder_collapsed,
            set_profile_folders_collapsed,
            _reset_profile_folders,
            action=action,
            folder_key=folder_key,
            name=name,
            direction=direction,
            collapsed=collapsed,
            collapsed_by_key=collapsed_by_key,
            context_extra=context_extra,
            parent=parent,
        )
