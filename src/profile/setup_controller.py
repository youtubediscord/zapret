"""Контроллер экрана настройки profile."""

from __future__ import annotations

from profile.setup_workflow import (
    apply_strategy_to_profile,
    load_profile_setup,
    save_winws2_profile_settings,
    set_current_strategy_feedback,
    set_profile_enabled,
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

    def set_enabled(self, *, profile_key: str, enabled: bool) -> str | None:
        return set_profile_enabled(
            profile_feature=self._profile,
            launch_method=self._launch_method,
            profile_key=profile_key,
            enabled=enabled,
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
