"""Build-helper секции program settings для Control page."""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(slots=True)
class ControlProgramSettingsWidgets:
    section_label: object | None
    program_settings_card: object
    auto_dpi_toggle: object
    defender_toggle: object
    max_block_toggle: object


def build_control_program_settings_section(
    *,
    tr_fn,
    content_parent,
    setting_card_group_cls,
    win11_toggle_row_cls,
    on_auto_dpi_toggled,
    on_defender_toggled,
    on_max_blocker_toggled,
) -> ControlProgramSettingsWidgets:
    program_settings_title = tr_fn(
        "page.control.section.program_settings",
        "Настройки программы",
    )

    section_label = None
    program_settings_card = setting_card_group_cls(program_settings_title, content_parent)

    auto_dpi_toggle = win11_toggle_row_cls(
        "fa5s.bolt",
        tr_fn("page.control.setting.autostart.title", "Автозапуск DPI после старта программы"),
        tr_fn("page.control.setting.autostart.desc", "После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
    )
    auto_dpi_toggle.toggled.connect(on_auto_dpi_toggled)

    defender_toggle = win11_toggle_row_cls(
        "fa5s.shield-alt",
        tr_fn("page.control.setting.defender.title", "Отключить Windows Defender"),
        tr_fn("page.control.setting.defender.desc", "Требуются права администратора"),
    )
    defender_toggle.toggled.connect(on_defender_toggled)

    max_block_toggle = win11_toggle_row_cls(
        "fa5s.ban",
        tr_fn("page.control.setting.max_block.title", "Блокировать установку MAX"),
        tr_fn("page.control.setting.max_block.desc", "Блокирует запуск/установку MAX и домены в hosts"),
    )
    max_block_toggle.toggled.connect(on_max_blocker_toggled)

    program_settings_card.addSettingCard(auto_dpi_toggle)
    program_settings_card.addSettingCard(defender_toggle)
    program_settings_card.addSettingCard(max_block_toggle)

    return ControlProgramSettingsWidgets(
        section_label=section_label,
        program_settings_card=program_settings_card,
        auto_dpi_toggle=auto_dpi_toggle,
        defender_toggle=defender_toggle,
        max_block_toggle=max_block_toggle,
    )
