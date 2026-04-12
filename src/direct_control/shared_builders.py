from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ui.compat_widgets import SettingsCard, PulsingDot


@dataclass(slots=True)
class DirectActionCardWidgets:
    card: QWidget
    icon_label: QLabel
    title_label: object
    content_label: object
    button: QWidget


def build_direct_status_section_common(
    *,
    tr_fn,
    has_fluent_labels: bool,
    strong_body_label_cls,
    caption_label_cls,
    checking_key: str,
    checking_default: str,
    detecting_key: str,
    detecting_default: str,
):
    status_card = SettingsCard()
    status_layout = QHBoxLayout()
    status_layout.setSpacing(16)

    status_dot = PulsingDot()
    status_layout.addWidget(status_dot)

    status_text = QVBoxLayout()
    status_text.setContentsMargins(0, 0, 0, 0)
    status_text.setSpacing(2)

    if has_fluent_labels:
        status_title = strong_body_label_cls(tr_fn(checking_key, checking_default))
        status_desc = caption_label_cls(tr_fn(detecting_key, detecting_default))
    else:
        status_title = QLabel(tr_fn(checking_key, checking_default))
        status_title.setStyleSheet("QLabel { font-size: 15px; font-weight: 600; }")
        status_desc = QLabel(tr_fn(detecting_key, detecting_default))
        status_desc.setStyleSheet("QLabel { font-size: 12px; }")

    status_text.addWidget(status_title)
    status_text.addWidget(status_desc)
    status_layout.addLayout(status_text, 1)
    status_card.add_layout(status_layout)

    return status_card, status_dot, status_title, status_desc


def build_direct_management_section_common(
    *,
    tr_fn,
    has_fluent_labels: bool,
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
    control_card = SettingsCard()
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

    return control_card, start_btn, stop_winws_btn, stop_and_exit_btn, progress_bar, loading_label


def build_reset_program_action_card_common(
    *,
    tr_fn,
    has_fluent_labels: bool,
    caption_label_cls,
    action_button_cls,
    settings_card_cls,
    button_key: str,
    button_default: str,
    button_icon_name: str,
    title_key: str,
    title_default: str,
    desc_key: str,
    desc_default: str,
    on_confirm_reset_program_clicked,
):
    reset_program_btn = action_button_cls(
        tr_fn(button_key, button_default),
        button_icon_name,
    )
    reset_program_btn.setProperty("noDrag", True)
    reset_program_btn.clicked.connect(on_confirm_reset_program_clicked)

    reset_program_card = settings_card_cls(
        tr_fn(title_key, title_default)
    )
    reset_program_desc_label = caption_label_cls(
        tr_fn(desc_key, desc_default)
    ) if has_fluent_labels else QLabel(
        tr_fn(desc_key, desc_default)
    )
    reset_program_desc_label.setWordWrap(True)
    reset_program_card.add_widget(reset_program_desc_label)

    reset_layout = QHBoxLayout()
    reset_layout.setSpacing(8)
    reset_layout.addWidget(reset_program_btn)
    reset_layout.addStretch()
    reset_program_card.add_layout(reset_layout)

    return reset_program_card, reset_program_btn, reset_program_desc_label


def _resolve_card_icon_pixmap(icon_source) -> QPixmap:
    if isinstance(icon_source, QPixmap):
        return icon_source
    if isinstance(icon_source, QIcon):
        return icon_source.pixmap(20, 20)
    try:
        maybe_pixmap = icon_source.pixmap(20, 20)
        if isinstance(maybe_pixmap, QPixmap):
            return maybe_pixmap
    except Exception:
        pass
    return QPixmap()


def build_direct_action_card_common(
    *,
    card_widget_cls,
    strong_body_label_cls,
    caption_label_cls,
    button,
    icon_source,
    title_text: str,
    content_text: str,
    parent=None,
):
    card = card_widget_cls(parent)
    card.setProperty("noDrag", True)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    row = QHBoxLayout(card)
    row.setContentsMargins(16, 14, 16, 14)
    row.setSpacing(12)

    icon_label = QLabel(card)
    icon_label.setFixedSize(24, 24)
    icon_label.setPixmap(_resolve_card_icon_pixmap(icon_source))
    row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(2)

    title_label = strong_body_label_cls(title_text)
    content_label = caption_label_cls(content_text or "")
    content_label.setWordWrap(True)
    content_label.setVisible(bool(content_text))

    text_col.addWidget(title_label)
    text_col.addWidget(content_label)
    row.addLayout(text_col, 1)

    button.setParent(card)
    button.setProperty("noDrag", True)
    row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)

    return DirectActionCardWidgets(
        card=card,
        icon_label=icon_label,
        title_label=title_label,
        content_label=content_label,
        button=button,
    )


def build_connected_direct_action_card_common(
    *,
    on_click=None,
    **kwargs,
):
    widgets = build_direct_action_card_common(**kwargs)
    if on_click is not None:
        widgets.button.clicked.connect(on_click)
    return widgets


def build_direct_extra_buttons_card_common(
    *,
    settings_card_cls,
    action_button_cls,
    actions: list[tuple[str, str, object]],
):
    card = settings_card_cls()
    layout = QHBoxLayout()
    layout.setSpacing(8)
    buttons: list[QWidget] = []

    for text, icon_name, callback in actions:
        button = action_button_cls(text, icon_name)
        button.clicked.connect(callback)
        layout.addWidget(button)
        buttons.append(button)

    layout.addStretch()
    card.add_layout(layout)
    return card, buttons
