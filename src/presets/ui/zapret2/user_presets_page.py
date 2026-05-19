"""Страница пользовательских preset-ов Zapret 2."""

from __future__ import annotations

from presets.ui.common.user_presets_page import UserPresetsPageBase, UserPresetsPageConfig
from presets.ui.zapret2.user_presets_dialogs import (
    CreatePresetDialog,
    RenamePresetDialog,
    ResetAllPresetsDialog,
)
from settings.mode import PRESETS_SCOPE_WINWS2, ZAPRET2_MODE


class Zapret2UserPresetsPage(UserPresetsPageBase):
    page_config = UserPresetsPageConfig(
        launch_method=ZAPRET2_MODE,
        folder_scope=PRESETS_SCOPE_WINWS2,
        tr_prefix="page.winws2_user_presets",
        title_key="page.winws2_user_presets.title",
        log_prefix="Winws2UserPresetsPage",
        activate_error_level="error",
        activate_error_mode="raw",
        create_dialog_cls=CreatePresetDialog,
        rename_dialog_cls=RenamePresetDialog,
        reset_all_dialog_cls=ResetAllPresetsDialog,
        delegate_language_scope="winws2",
    )


__all__ = ["Zapret2UserPresetsPage"]
