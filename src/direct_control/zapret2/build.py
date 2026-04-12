"""Build-helper верхних секций для Zapret2DirectControlPage."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy

from ui.compat_widgets import SettingsCard, PulsingDot
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

    status_card = SettingsCard()
    status_layout = QHBoxLayout()
    status_layout.setSpacing(16)

    status_dot = PulsingDot()
    status_layout.addWidget(status_dot)

    status_text = QVBoxLayout()
    status_text.setContentsMargins(0, 0, 0, 0)
    status_text.setSpacing(2)

    if has_fluent_labels:
        status_title = strong_body_label_cls(tr_fn("page.z2_control.status.checking", "Проверка..."))
        status_desc = caption_label_cls(tr_fn("page.z2_control.status.detecting", "Определение состояния процесса"))
    else:
        status_title = QLabel(tr_fn("page.z2_control.status.checking", "Проверка..."))
        status_title.setStyleSheet("QLabel { font-size: 15px; font-weight: 600; }")
        status_desc = QLabel(tr_fn("page.z2_control.status.detecting", "Определение состояния процесса"))
        status_desc.setStyleSheet("QLabel { font-size: 12px; }")

    status_text.addWidget(status_title)
    status_text.addWidget(status_desc)
    status_layout.addLayout(status_text, 1)
    status_card.add_layout(status_layout)

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

    control_card = SettingsCard()
    buttons_layout = QHBoxLayout()
    buttons_layout.setSpacing(12)

    start_btn = big_action_button_cls(
        tr_fn("page.z2_control.button.start", "Запустить Zapret"),
        "fa5s.play",
        accent=True,
    )
    start_btn.clicked.connect(on_start)
    buttons_layout.addWidget(start_btn)

    stop_winws_btn = stop_button_cls(
        tr_fn("page.z2_control.button.stop_only_winws", "Остановить только winws.exe"),
        "fa5s.stop",
    )
    stop_winws_btn.clicked.connect(on_stop)
    stop_winws_btn.setVisible(False)
    buttons_layout.addWidget(stop_winws_btn)

    stop_and_exit_btn = stop_button_cls(
        tr_fn("page.z2_control.button.stop_and_exit", "Остановить и закрыть программу"),
        "fa5s.power-off",
    )
    stop_and_exit_btn.clicked.connect(on_stop_and_exit)
    stop_and_exit_btn.setVisible(False)
    buttons_layout.addWidget(stop_and_exit_btn)

    buttons_layout.addStretch()
    control_card.add_layout(buttons_layout)

    progress_bar = indeterminate_progress_bar_cls(parent)
    progress_bar.setVisible(False)
    control_card.add_widget(progress_bar)

    if has_fluent_labels:
        loading_label = caption_label_cls("")
    else:
        loading_label = QLabel("")
        loading_label.setStyleSheet("QLabel { font-size: 12px; padding-top: 4px; }")
    loading_label.setVisible(False)
    control_card.add_widget(loading_label)

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

    preset_card = card_widget_cls()
    preset_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    preset_row = QHBoxLayout(preset_card)
    preset_row.setContentsMargins(16, 14, 16, 14)
    preset_row.setSpacing(12)

    preset_icon_lbl = QLabel()
    preset_icon_lbl.setPixmap(get_cached_qta_pixmap("fa5s.star", color="#ffc107", size=20))
    preset_icon_lbl.setFixedSize(24, 24)
    preset_row.addWidget(preset_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

    preset_col = QVBoxLayout()
    preset_col.setSpacing(2)
    preset_name_label = strong_body_label_cls(
        tr_fn("page.z2_control.preset.not_selected", "Не выбран")
    )
    preset_col.addWidget(preset_name_label)
    current_preset_caption = caption_label_cls(
        tr_fn("page.z2_control.preset.current", "Текущий активный пресет")
    )
    preset_col.addWidget(current_preset_caption)
    preset_row.addLayout(preset_col, 1)

    presets_btn = push_button_cls()
    presets_btn.setText(tr_fn("page.z2_control.button.my_presets", "Мои пресеты"))
    presets_btn.setIcon(fluent_icon.FOLDER)
    presets_btn.clicked.connect(on_open_presets)
    preset_row.addWidget(presets_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    return Zapret2DirectPresetWidgets(
        section_label=section_label,
        card=preset_card,
        preset_name_label=preset_name_label,
        current_preset_caption=current_preset_caption,
        presets_btn=presets_btn,
    )
