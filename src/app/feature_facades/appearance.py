from __future__ import annotations


class AppearanceFeature:
    @staticmethod
    def _appearance():
        import settings.appearance as appearance_settings

        return appearance_settings

    def create_initial_state_load_worker(self, request_id: int, *, parent=None):
        from settings.appearance_workers import AppearanceInitialStateLoadWorker

        return AppearanceInitialStateLoadWorker(
            request_id,
            load_page_initial_state=lambda: self._appearance().load_page_initial_state(),
            parent=parent,
        )

    def create_appearance_save_worker(
        self,
        request_id: int,
        *,
        action: str,
        value=None,
        context_extra: dict | None = None,
        parent=None,
    ):
        from settings.appearance_workers import AppearanceSettingsSaveWorker

        appearance = self._appearance()
        return AppearanceSettingsSaveWorker(
            request_id,
            action=action,
            value=value,
            context_extra=context_extra,
            save_display_mode=appearance.save_display_mode,
            save_ui_language=appearance.save_ui_language,
            save_background_preset=appearance.save_background_preset,
            save_rkn_background=appearance.save_rkn_background,
            save_window_opacity=appearance.save_window_opacity,
            save_snowflakes_enabled=appearance.save_snowflakes_enabled,
            save_garland_enabled=appearance.save_garland_enabled,
            save_accent_color=appearance.save_accent_color,
            save_follow_windows_accent=appearance.save_follow_windows_accent,
            save_tinted_background=appearance.save_tinted_background,
            save_tinted_background_intensity=appearance.save_tinted_background_intensity,
            save_animations_enabled=appearance.save_animations_enabled,
            save_smooth_scroll_enabled=appearance.save_smooth_scroll_enabled,
            save_editor_smooth_scroll_enabled=appearance.save_editor_smooth_scroll_enabled,
            load_tinted_settings=appearance.load_tinted_settings,
            load_editor_smooth_scroll_enabled=appearance.load_editor_smooth_scroll_enabled,
            parent=parent,
        )

    def create_rkn_background_options_load_worker(self, request_id: int, *, parent=None):
        from settings.appearance_workers import AppearanceRknBackgroundOptionsLoadWorker
        from ui.theme import get_rkn_background_options

        return AppearanceRknBackgroundOptionsLoadWorker(
            request_id,
            load_rkn_background=lambda: self._appearance().load_rkn_background(),
            get_rkn_background_options=get_rkn_background_options,
            parent=parent,
        )

    def create_windows_accent_load_worker(self, request_id: int, *, parent=None):
        from settings.appearance_workers import AppearanceWindowsAccentLoadWorker

        return AppearanceWindowsAccentLoadWorker(
            request_id,
            load_windows_system_accent=lambda: self._appearance().load_windows_system_accent(),
            parent=parent,
        )


def build_appearance_feature() -> AppearanceFeature:
    return AppearanceFeature()


__all__ = ["AppearanceFeature", "build_appearance_feature"]
