"""Общая сборка кнопок Defender/MAX для страниц управления."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WindowsFeatureToggleWidgets:
    defender_toggle: object
    max_block_toggle: object


def build_windows_feature_toggles(
    *,
    tr_fn,
    win11_toggle_row_cls,
    on_defender_toggled,
    on_max_blocker_toggled,
) -> WindowsFeatureToggleWidgets:
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

    return WindowsFeatureToggleWidgets(
        defender_toggle=defender_toggle,
        max_block_toggle=max_block_toggle,
    )


def build_state_media_block_toggle(
    *,
    tr_fn,
    win11_toggle_row_cls,
    on_state_media_block_toggled,
):
    state_media_block_toggle = win11_toggle_row_cls(
        "fa5s.newspaper",
        tr_fn("page.control.setting.state_media_block.title", "Блокировать государственные СМИ РФ"),
        tr_fn(
            "page.control.setting.state_media_block.desc",
            "Добавляет базовый список государственных новостных сайтов в hosts",
        ),
    )
    state_media_block_toggle.toggled.connect(on_state_media_block_toggled)
    return state_media_block_toggle
