"""Страница пользовательских preset-ов Zapret 1."""

from __future__ import annotations

from presets.ui.common.user_presets_page import UserPresetsPageBase, UserPresetsPageConfig
from presets.ui.zapret1.user_presets_dialogs import (
    CreatePresetDialog,
    RenamePresetDialog,
    ResetAllPresetsDialog,
)
from settings.mode import PRESETS_SCOPE_WINWS1, ZAPRET1_MODE


class Zapret1UserPresetsPage(UserPresetsPageBase):
    page_config = UserPresetsPageConfig(
        launch_method=ZAPRET1_MODE,
        folder_scope=PRESETS_SCOPE_WINWS1,
        tr_prefix="page.winws1_user_presets",
        title_key="page.winws1_user_presets.title",
        log_prefix="Winws1UserPresetsPage",
        activate_error_level="warning",
        activate_error_mode="friendly",
        create_dialog_cls=CreatePresetDialog,
        rename_dialog_cls=RenamePresetDialog,
        reset_all_dialog_cls=ResetAllPresetsDialog,
        delegate_language_scope="winws1",
    )


__all__ = ["Zapret1UserPresetsPage"]
