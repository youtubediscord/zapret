"""Build-helper верхних секций для Zapret1DirectControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from direct_preset.ui.control.shared_builders import (
    build_direct_management_section_common,
    build_direct_status_section_common,
    build_push_setting_card_common,
)
from ui.theme import get_cached_qta_pixmap


@dataclass(slots=True)
class Zapret1DirectStatusWidgets:
    card: object
    status_dot: object
    status_title: object
    status_desc: object


@dataclass(slots=True)
class Zapret1DirectManagementWidgets:
    card: object
    start_btn: object
    stop_winws_btn: object
    stop_and_exit_btn: object
    progress_bar: object
    loading_label: object


@dataclass(slots=True)
class Zapret1DirectPresetWidgets:
    card: object
    preset_name_label: object
    preset_caption_label: object
    presets_btn: object


def build_z1_direct_status_section(
    *,
    tr_fn,
    strong_body_label_cls,
    caption_label_cls,
) -> Zapret1DirectStatusWidgets:
    status_card, status_dot, status_title, status_desc = build_direct_status_section_common(
        tr_fn=tr_fn,
        strong_body_label_cls=strong_body_label_cls,
        caption_label_cls=caption_label_cls,
        checking_key="page.z1_control.status.checking",
        checking_default="Проверка...",
        detecting_key="page.z1_control.status.detecting",
        detecting_default="Определение состояния процесса",
    )

    return Zapret1DirectStatusWidgets(
        card=status_card,
        status_dot=status_dot,
        status_title=status_title,
        status_desc=status_desc,
    )


def build_z1_direct_management_section(
    *,
    tr_fn,
    caption_label_cls,
    indeterminate_progress_bar_cls,
    big_action_button_cls,
    stop_button_cls,
    on_start,
    on_stop,
    on_stop_and_exit,
    parent,
) -> Zapret1DirectManagementWidgets:
    control_card, start_btn, stop_winws_btn, stop_and_exit_btn, progress_bar, loading_label = (
        build_direct_management_section_common(
            tr_fn=tr_fn,
            caption_label_cls=caption_label_cls,
            indeterminate_progress_bar_cls=indeterminate_progress_bar_cls,
            big_action_button_cls=big_action_button_cls,
            stop_button_cls=stop_button_cls,
            start_key="page.z1_control.button.start",
            start_default="Запустить Zapret",
            stop_key="page.z1_control.button.stop_winws",
            stop_default="Остановить winws.exe",
            stop_exit_key="page.z1_control.button.stop_and_exit",
            stop_exit_default="Остановить и закрыть",
            on_start=on_start,
            on_stop=on_stop,
            on_stop_and_exit=on_stop_and_exit,
            parent=parent,
        )
    )

    return Zapret1DirectManagementWidgets(
        card=control_card,
        start_btn=start_btn,
        stop_winws_btn=stop_winws_btn,
        stop_and_exit_btn=stop_and_exit_btn,
        progress_bar=progress_bar,
        loading_label=loading_label,
    )


def build_z1_direct_preset_section(
    *,
    tr_fn,
    push_setting_card_cls,
    on_open_presets,
) -> Zapret1DirectPresetWidgets:
    preset_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.z1_control.button.my_presets", "Мои пресеты"),
        icon=get_cached_qta_pixmap("fa5s.star", color="#ffc107", size=20),
        title_text=tr_fn("page.z1_control.preset.not_selected", "Не выбран"),
        content_text=tr_fn("page.z1_control.preset.current", "Текущий активный пресет"),
        on_click=on_open_presets,
    )

    return Zapret1DirectPresetWidgets(
        card=preset_card,
        preset_name_label=preset_card.titleLabel,
        preset_caption_label=preset_card.contentLabel,
        presets_btn=preset_card.button,
    )
