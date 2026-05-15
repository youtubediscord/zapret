from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout

from qfluentwidgets import CardWidget

from ui.fluent_widgets import PulsingDot
from ui.theme import get_cached_qta_pixmap


@dataclass(slots=True)
class PresetEntryCardWidgets:
    card: object
    title_label: object
    caption_label: object
    button: object


def build_mode_status_section_common(
    *,
    tr_fn,
    strong_body_label_cls,
    caption_label_cls,
    checking_key: str,
    checking_default: str,
    detecting_key: str,
    detecting_default: str,
):
    status_card = CardWidget()
    status_layout = QHBoxLayout(status_card)
    status_layout.setContentsMargins(16, 14, 16, 14)
    status_layout.setSpacing(16)

    status_dot = PulsingDot()
    status_layout.addWidget(status_dot)

    status_text = QVBoxLayout()
    status_text.setContentsMargins(0, 0, 0, 0)
    status_text.setSpacing(2)

    status_title = strong_body_label_cls(tr_fn(checking_key, checking_default))
    status_desc = caption_label_cls(tr_fn(detecting_key, detecting_default))

    status_text.addWidget(status_title)
    status_text.addWidget(status_desc)
    status_layout.addLayout(status_text, 1)

    return status_card, status_dot, status_title, status_desc


def build_mode_management_section_common(
    *,
    tr_fn,
    caption_label_cls,
    indeterminate_progress_bar_cls,
    big_action_button_cls,
    stop_button_cls,
    start_key: str,
    start_default: str,
    stop_key: str,
    stop_default: str,
    stop_exit_key: str,
    stop_exit_default: str,
    on_start,
    on_stop,
    on_stop_and_exit,
    parent,
):
    control_card = CardWidget()
    content_layout = QVBoxLayout(control_card)
    content_layout.setContentsMargins(16, 16, 16, 16)
    content_layout.setSpacing(12)

    buttons_layout = QHBoxLayout()
    buttons_layout.setSpacing(12)

    start_btn = big_action_button_cls(
        tr_fn(start_key, start_default),
        "fa5s.play",
        accent=True,
    )
    start_btn.clicked.connect(on_start)
    buttons_layout.addWidget(start_btn)

    stop_winws_btn = stop_button_cls(
        tr_fn(stop_key, stop_default),
        "fa5s.stop",
    )
    stop_winws_btn.clicked.connect(on_stop)
    stop_winws_btn.setVisible(False)
    buttons_layout.addWidget(stop_winws_btn)

    stop_and_exit_btn = stop_button_cls(
        tr_fn(stop_exit_key, stop_exit_default),
        "fa5s.power-off",
    )
    stop_and_exit_btn.clicked.connect(on_stop_and_exit)
    stop_and_exit_btn.setVisible(False)
    buttons_layout.addWidget(stop_and_exit_btn)

    buttons_layout.addStretch()
    content_layout.addLayout(buttons_layout)

    progress_bar = indeterminate_progress_bar_cls(parent)
    progress_bar.setVisible(False)
    content_layout.addWidget(progress_bar)

    loading_label = caption_label_cls("")
    loading_label.setVisible(False)
    content_layout.addWidget(loading_label)

    return control_card, start_btn, stop_winws_btn, stop_and_exit_btn, progress_bar, loading_label


def build_push_setting_card_common(
    *,
    push_setting_card_cls,
    button_text: str,
    icon,
    title_text: str,
    content_text: str,
    on_click,
    parent=None,
):
    if isinstance(icon, QPixmap):
        icon = QIcon(icon)

    card = push_setting_card_cls(
        button_text,
        icon,
        title_text,
        content_text or None,
        parent,
    )
    card.setProperty("noDrag", True)
    card.clicked.connect(on_click)
    return card


def build_my_presets_card_common(
    *,
    tr_fn,
    push_setting_card_cls,
    button_key: str,
    not_selected_key: str,
    current_key: str,
    on_open_presets,
    parent=None,
) -> PresetEntryCardWidgets:
    card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn(button_key, "Мои пресеты"),
        icon=get_cached_qta_pixmap("fa5s.star", color="#ffc107", size=20),
        title_text=tr_fn(not_selected_key, "Не выбран"),
        content_text=tr_fn(current_key, "Текущий активный пресет"),
        on_click=on_open_presets,
        parent=parent,
    )
    return PresetEntryCardWidgets(
        card=card,
        title_label=card.titleLabel,
        caption_label=card.contentLabel,
        button=card.button,
    )


def build_preset_setup_open_card_common(
    *,
    tr_fn,
    push_setting_card_cls,
    button_key: str,
    title_key: str,
    desc_key: str,
    on_open_preset_setup_page,
    parent=None,
) -> PresetEntryCardWidgets:
    card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn(button_key, "Открыть"),
        icon=get_cached_qta_pixmap("fa5s.play", color="#60cdff", size=20),
        title_text=tr_fn(title_key, "Настройка пресета"),
        content_text=tr_fn(desc_key, "Открыть профили выбранного пресета и выбрать готовые стратегии"),
        on_click=on_open_preset_setup_page,
        parent=parent,
    )
    return PresetEntryCardWidgets(
        card=card,
        title_label=card.titleLabel,
        caption_label=card.contentLabel,
        button=card.button,
    )
