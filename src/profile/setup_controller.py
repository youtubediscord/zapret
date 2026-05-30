"""Контроллер экрана настройки profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from profile.setup_workflow import (
    apply_strategy_to_profile,
    load_profile_list_file_editor_state,
    load_profile_setup,
    save_profile_raw_text,
    save_profile_list_file_text,
    save_winws2_profile_settings,
    set_current_strategy_feedback,
    set_profile_enabled,
    validate_profile_list_file_text,
)


@dataclass(frozen=True, slots=True)
class ProfileSetupActions:
    get_profile_setup: Callable[..., object]
    get_profile_list_file_editor_state: Callable[..., object]
    update_winws2_profile_settings: Callable[..., object]
    update_profile_raw_text: Callable[..., object]
    validate_profile_list_file_text: Callable[..., object]
    save_profile_list_file_text: Callable[..., object]
    set_profile_enabled: Callable[..., object]
    update_user_profile: Callable[..., object]
    list_profiles: Callable[..., object]
    delete_user_profile: Callable[..., object]
    apply_strategy_to_profile: Callable[..., object]
    set_current_strategy_state: Callable[..., object]


class ProfileSetupController:
    """Действия страницы настройки profile без привязки к QWidget."""

    def __init__(self, *, profile_setup_actions: ProfileSetupActions, launch_method: str) -> None:
        self._actions = profile_setup_actions
        self._launch_method = launch_method

    def load(self, profile_key: str):
        return load_profile_setup(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            profile_key=profile_key,
        )

    def create_load_worker(self, request_id: int, profile_key: str, parent=None):
        from profile.profile_setup_loader import ProfileSetupLoadWorker

        return ProfileSetupLoadWorker(request_id, self.load, profile_key, parent)

    def load_list_file_editor_state(self, profile_key: str, *, filter_kind: str = "", filter_value: str = ""):
        return load_profile_list_file_editor_state(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            profile_key=profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
        )

    def create_list_file_load_worker(
        self,
        request_id: int,
        profile_key: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileListFileLoadWorker

        return ProfileListFileLoadWorker(
            request_id,
            self.load_list_file_editor_state,
            profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            parent=parent,
        )

    def create_list_file_save_worker(self, request_id: int, profile_key: str, text: str, parent=None):
        from profile.profile_setup_loader import ProfileListFileSaveWorker

        return ProfileListFileSaveWorker(
            request_id,
            self.save_list_file_text,
            self.load,
            profile_key,
            text,
            parent,
        )

    def create_list_file_validation_worker(self, request_id: int, *, kind: str, text: str, parent=None):
        from profile.profile_setup_loader import ProfileListFileValidationWorker

        return ProfileListFileValidationWorker(
            request_id,
            self.validate_list_file_text,
            kind=kind,
            text=text,
            parent=parent,
        )

    def create_settings_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileSettingsSaveWorker

        return ProfileSettingsSaveWorker(
            request_id,
            self.save_winws2_settings,
            self.load,
            profile_key=profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            in_range=in_range,
            out_range=out_range,
            parent=parent,
        )

    def create_raw_profile_save_worker(self, request_id: int, profile_key: str, raw_text: str, parent=None):
        from profile.profile_setup_loader import ProfileRawTextSaveWorker

        return ProfileRawTextSaveWorker(
            request_id,
            self.save_raw_profile_text,
            self.load,
            profile_key,
            raw_text,
            parent,
        )

    def create_enabled_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        enabled: bool,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileEnabledSaveWorker

        return ProfileEnabledSaveWorker(
            request_id,
            self.set_enabled,
            self.load,
            profile_key=profile_key,
            enabled=enabled,
            filter_kind=filter_kind,
            filter_value=filter_value,
            parent=parent,
        )

    def create_user_profile_update_worker(
        self,
        request_id: int,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileUserProfileUpdateWorker

        return ProfileUserProfileUpdateWorker(
            request_id,
            self.update_user_profile,
            self.load_user_profile_items,
            profile_id=profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=parent,
        )

    def create_user_profile_delete_worker(self, request_id: int, *, profile_id: str, parent=None):
        from profile.profile_setup_loader import ProfileUserProfileDeleteWorker

        return ProfileUserProfileDeleteWorker(
            request_id,
            self.delete_user_profile,
            profile_id=profile_id,
            parent=parent,
        )

    def create_strategy_apply_worker(self, request_id: int, *, profile_key: str, strategy_id: str, parent=None):
        from profile.profile_setup_loader import ProfileStrategyApplyWorker

        return ProfileStrategyApplyWorker(
            request_id,
            self.apply_strategy,
            self.load,
            profile_key,
            strategy_id,
            parent,
        )

    def create_strategy_feedback_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        strategy_id: str,
        rating: str | None = None,
        favorite: bool | None = None,
        parent=None,
    ):
        from profile.profile_setup_loader import ProfileStrategyFeedbackSaveWorker

        return ProfileStrategyFeedbackSaveWorker(
            request_id,
            self.set_strategy_feedback,
            profile_key=profile_key,
            strategy_id=strategy_id,
            rating=rating,
            favorite=favorite,
            parent=parent,
        )

    def save_winws2_settings(
        self,
        *,
        profile_key: str,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
    ) -> str | None:
        return save_winws2_profile_settings(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            profile_key=profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            in_range=in_range,
            out_range=out_range,
        )

    def save_raw_profile_text(self, *, profile_key: str, raw_text: str) -> str | None:
        return save_profile_raw_text(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            profile_key=profile_key,
            raw_text=raw_text,
        )

    def validate_list_file_text(self, *, kind: str, text: str):
        return validate_profile_list_file_text(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            kind=kind,
            text=text,
        )

    def save_list_file_text(self, *, profile_key: str, text: str):
        return save_profile_list_file_text(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            profile_key=profile_key,
            text=text,
        )

    def set_enabled(
        self,
        *,
        profile_key: str,
        enabled: bool,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> str | None:
        return set_profile_enabled(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            profile_key=profile_key,
            enabled=enabled,
            filter_kind=filter_kind,
            filter_value=filter_value,
        )

    def update_user_profile(self, *, profile_id: str, name: str, protocol: str, ports: str) -> int:
        return int(self._actions.update_user_profile(
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        ))

    def list_profiles(self, launch_method: str = ""):
        return self._actions.list_profiles(launch_method or self._launch_method)

    def load_user_profile_items(self, profile_id: str):
        from profile.profile_setup_loader import load_user_profile_items_from_payload

        return load_user_profile_items_from_payload(self.list_profiles, profile_id)

    def delete_user_profile(self, *, profile_id: str) -> int:
        return int(self._actions.delete_user_profile(profile_id))

    def apply_strategy(self, *, profile_key: str, strategy_id: str) -> str | None:
        return apply_strategy_to_profile(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            profile_key=profile_key,
            strategy_id=strategy_id,
        )

    def set_strategy_feedback(
        self,
        *,
        profile_key: str,
        rating: str | None = None,
        favorite: bool | None = None,
    ):
        return set_current_strategy_feedback(
            profile_actions=self._actions,
            launch_method=self._launch_method,
            profile_key=profile_key,
            rating=rating,
            favorite=favorite,
        )
