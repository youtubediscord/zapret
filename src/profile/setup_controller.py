"""Контроллер экрана настройки profile."""

from __future__ import annotations

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


class ProfileSetupController:
    """Действия страницы настройки profile без привязки к QWidget."""

    def __init__(self, *, profile_feature, launch_method: str) -> None:
        self._profile = profile_feature
        self._launch_method = launch_method

    def load(self, profile_key: str):
        return load_profile_setup(
            profile_feature=self._profile,
            launch_method=self._launch_method,
            profile_key=profile_key,
        )

    def create_load_worker(self, request_id: int, profile_key: str, parent=None):
        from profile.profile_setup_loader import ProfileSetupLoadWorker

        return ProfileSetupLoadWorker(request_id, self, profile_key, parent)

    def load_list_file_editor_state(self, profile_key: str, *, filter_kind: str = "", filter_value: str = ""):
        return load_profile_list_file_editor_state(
            profile_feature=self._profile,
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
            self,
            profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            parent=parent,
        )

    def create_strategy_apply_worker(self, request_id: int, *, profile_key: str, strategy_id: str, parent=None):
        from profile.profile_setup_loader import ProfileStrategyApplyWorker

        return ProfileStrategyApplyWorker(request_id, self, profile_key, strategy_id, parent)

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
            profile_feature=self._profile,
            launch_method=self._launch_method,
            profile_key=profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            in_range=in_range,
            out_range=out_range,
        )

    def save_raw_profile_text(self, *, profile_key: str, raw_text: str) -> str | None:
        return save_profile_raw_text(
            profile_feature=self._profile,
            launch_method=self._launch_method,
            profile_key=profile_key,
            raw_text=raw_text,
        )

    def validate_list_file_text(self, *, kind: str, text: str):
        return validate_profile_list_file_text(
            profile_feature=self._profile,
            launch_method=self._launch_method,
            kind=kind,
            text=text,
        )

    def save_list_file_text(self, *, profile_key: str, text: str):
        return save_profile_list_file_text(
            profile_feature=self._profile,
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
            profile_feature=self._profile,
            launch_method=self._launch_method,
            profile_key=profile_key,
            enabled=enabled,
            filter_kind=filter_kind,
            filter_value=filter_value,
        )

    def update_user_profile(self, *, profile_id: str, name: str, protocol: str, ports: str) -> int:
        return int(self._profile.update_user_profile(
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        ))

    def delete_user_profile(self, *, profile_id: str) -> int:
        return int(self._profile.delete_user_profile(profile_id))

    def apply_strategy(self, *, profile_key: str, strategy_id: str) -> str | None:
        return apply_strategy_to_profile(
            profile_feature=self._profile,
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
    ) -> None:
        set_current_strategy_feedback(
            profile_feature=self._profile,
            launch_method=self._launch_method,
            profile_key=profile_key,
            rating=rating,
            favorite=favorite,
        )
