"""Build-helper верхних секций для Zapret2DirectControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from direct_control.shared_builders import (
    build_direct_action_card_common,
    build_direct_management_section_common,
    build_direct_status_section_common,
)
from ui.theme import get_cached_qta_pixmap


@dataclass(slots=True)
class Zapret2DirectStatusWidgets:
    section_label: object
    card: object
    status_dot: object
    status_title: object
    status_desc: object


@dataclass(slots=True)
class Zapret2DirectManagementWidgets:
    section_label: object
    card: object
    start_btn: object
    stop_winws_btn: object
    stop_and_exit_btn: object
    progress_bar: object
    loading_label: object


@dataclass(slots=True)
class Zapret2DirectPresetWidgets:
    section_label: object
    card: object
    preset_name_label: object
    current_preset_caption: object
    presets_btn: object


def build_z2_direct_status_section(
    *,
    add_section_title,
    tr_fn,
    has_fluent_labels: bool,
    strong_body_label_cls,
    caption_label_cls,
) -> Zapret2DirectStatusWidgets:
    section_label = add_section_title(return_widget=True, text_key="page.z2_control.section.status")
    status_card, status_dot, status_title, status_desc = build_direct_status_section_common(
        tr_fn=tr_fn,
        has_fluent_labels=has_fluent_labels,
        strong_body_label_cls=strong_body_label_cls,
        caption_label_cls=caption_label_cls,
        checking_key="page.z2_control.status.checking",
        checking_default="Проверка...",
        detecting_key="page.z2_control.status.detecting",
        detecting_default="Определение состояния процесса",
    )

    return Zapret2DirectStatusWidgets(
        section_label=section_label,
        card=status_card,
        status_dot=status_dot,
        status_title=status_title,
        status_desc=status_desc,
    )


def build_z2_direct_management_section(
    *,
    add_section_title,
    tr_fn,
    has_fluent_labels: bool,
    caption_label_cls,
    indeterminate_progress_bar_cls,
    big_action_button_cls,
    stop_button_cls,
    on_start,
    on_stop,
    on_stop_and_exit,
    parent,
) -> Zapret2DirectManagementWidgets:
    section_label = add_section_title(return_widget=True, text_key="page.z2_control.section.management")
    control_card, start_btn, stop_winws_btn, stop_and_exit_btn, progress_bar, loading_label = (
        build_direct_management_section_common(
            tr_fn=tr_fn,
            has_fluent_labels=has_fluent_labels,
            caption_label_cls=caption_label_cls,
            indeterminate_progress_bar_cls=indeterminate_progress_bar_cls,
            big_action_button_cls=big_action_button_cls,
            stop_button_cls=stop_button_cls,
            start_key="page.z2_control.button.start",
            start_default="Запустить Zapret",
            stop_key="page.z2_control.button.stop_only_winws",
            stop_default="Остановить только winws.exe",
            stop_exit_key="page.z2_control.button.stop_and_exit",
            stop_exit_default="Остановить и закрыть программу",
            on_start=on_start,
            on_stop=on_stop,
            on_stop_and_exit=on_stop_and_exit,
            parent=parent,
        )
    )

    return Zapret2DirectManagementWidgets(
        section_label=section_label,
        card=control_card,
        start_btn=start_btn,
        stop_winws_btn=stop_winws_btn,
        stop_and_exit_btn=stop_and_exit_btn,
        progress_bar=progress_bar,
        loading_label=loading_label,
    )


def build_z2_direct_preset_section(
    *,
    add_section_title,
    tr_fn,
    card_widget_cls,
    strong_body_label_cls,
    caption_label_cls,
    push_button_cls,
    fluent_icon,
    on_open_presets,
) -> Zapret2DirectPresetWidgets:
    section_label = add_section_title(return_widget=True, text_key="page.z2_control.section.preset_switch")
    presets_btn = push_button_cls()
    presets_btn.setText(tr_fn("page.z2_control.button.my_presets", "Мои пресеты"))
    presets_btn.setIcon(fluent_icon.FOLDER)
    presets_btn.clicked.connect(on_open_presets)

    preset_widgets = build_direct_action_card_common(
        card_widget_cls=card_widget_cls,
        strong_body_label_cls=strong_body_label_cls,
        caption_label_cls=caption_label_cls,
        button=presets_btn,
        icon_source=get_cached_qta_pixmap("fa5s.star", color="#ffc107", size=20),
        title_text=tr_fn("page.z2_control.preset.not_selected", "Не выбран"),
        content_text=tr_fn("page.z2_control.preset.current", "Текущий активный пресет"),
    )

    return Zapret2DirectPresetWidgets(
        section_label=section_label,
        card=preset_widgets.card,
        preset_name_label=preset_widgets.title_label,
        current_preset_caption=preset_widgets.content_label,
        presets_btn=preset_widgets.button,
    )
