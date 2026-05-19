"""Dialog-окна страницы preset-ов Zapret 1."""

from __future__ import annotations

from presets.ui.common.user_presets_dialogs import (
    CreatePresetDialog as _CreatePresetDialog,
    RenamePresetDialog as _RenamePresetDialog,
    ResetAllPresetsDialog as _ResetAllPresetsDialog,
)


class CreatePresetDialog(_CreatePresetDialog):
    tr_prefix = "page.winws1_user_presets"


class RenamePresetDialog(_RenamePresetDialog):
    tr_prefix = "page.winws1_user_presets"


class ResetAllPresetsDialog(_ResetAllPresetsDialog):
    tr_prefix = "page.winws1_user_presets"


__all__ = ["CreatePresetDialog", "RenamePresetDialog", "ResetAllPresetsDialog"]
