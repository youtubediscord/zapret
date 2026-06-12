from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout

from qfluentwidgets import CardWidget, FluentIcon

from presets.ui.control.control_page_runtime_shared import set_button_text_accessibility
from ui.pulsing_dot import PulsingDot
from ui.accessibility import enable_keyboard_click, set_control_accessibility, set_state_text
from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class LastStatusMessageWidgets:
    card: object
    dot: object
    title_label: object
    message_label: object


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


def build_last_status_message_card_common(
    *,
    tr_fn,
    strong_body_label_cls,
    caption_label_cls,
):
    card = CardWidget()
    layout = QHBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(14)

    dot = PulsingDot()
    dot.set_color("#8ab4f8")
    layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

    text_layout = QVBoxLayout()
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(2)

    title_label = strong_body_label_cls(
        tr_fn("page.control.last_message.title", "Последнее сообщение")
    )
    message_label = caption_label_cls(
        tr_fn("page.control.last_message.empty", "Пока нет новых сообщений")
    )
    message_label.setWordWrap(True)

    text_layout.addWidget(title_label)
    text_layout.addWidget(message_label)
    layout.addLayout(text_layout, 1)

    return LastStatusMessageWidgets(
        card=card,
        dot=dot,
        title_label=title_label,
        message_label=message_label,
    )


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

    start_text = tr_fn(start_key, start_default)
    start_btn = big_action_button_cls(
        start_text,
        icon=FluentIcon.PLAY,
    )
    set_control_accessibility(
        start_btn,
        description="Запускает обход блокировок в выбранном режиме.",
    )
    set_state_text(start_btn, start_text)
    start_btn.clicked.connect(on_start)
    buttons_layout.addWidget(start_btn)

    stop_text = tr_fn(stop_key, stop_default)
    stop_winws_btn = stop_button_cls(stop_text)
    set_control_accessibility(
        stop_winws_btn,
        description="Останавливает запущенный процесс обхода блокировок.",
    )
    set_state_text(stop_winws_btn, stop_text)
    stop_winws_btn.clicked.connect(on_stop)
    stop_winws_btn.setVisible(False)
    schedule_stop_button_icon(stop_winws_btn)
    buttons_layout.addWidget(stop_winws_btn)

    stop_exit_text = tr_fn(stop_exit_key, stop_exit_default)
    stop_and_exit_btn = stop_button_cls(
        stop_exit_text,
        icon=FluentIcon.POWER_BUTTON,
    )
    set_control_accessibility(
        stop_and_exit_btn,
        description="Останавливает обход блокировок и закрывает программу.",
    )
    set_state_text(stop_and_exit_btn, stop_exit_text)
    stop_and_exit_btn.clicked.connect(on_stop_and_exit)
    stop_and_exit_btn.setVisible(False)
    buttons_layout.addWidget(stop_and_exit_btn)

    buttons_layout.addStretch()
    content_layout.addLayout(buttons_layout)

    progress_bar = indeterminate_progress_bar_cls(parent)
    progress_bar.setVisible(False)
    set_control_accessibility(
        progress_bar,
        name="Ход запуска Zapret: не выполняется",
        description="Показывает, что запуск или остановка Zapret выполняется.",
    )
    set_state_text(progress_bar, "Ход запуска Zapret: не выполняется")
    content_layout.addWidget(progress_bar)

    loading_label = caption_label_cls("")
    loading_label.setVisible(False)
    set_state_text(loading_label, "Статус запуска Zapret: нет активного запуска")
    content_layout.addWidget(loading_label)

    return control_card, start_btn, stop_winws_btn, stop_and_exit_btn, progress_bar, loading_label


def schedule_stop_button_icon(button, *, delay_ms: int = 250) -> None:
    def _apply_icon() -> None:
        try:
            button.setIcon(get_themed_qta_icon("fa5s.stop"))
        except Exception:
            pass

    try:
        QTimer.singleShot(delay_ms, _apply_icon)
    except Exception:
        _apply_icon()


def build_deferred_themed_push_setting_card_common(
    *,
    push_setting_card_cls,
    button_text: str,
    icon_name: str,
    icon_color: str | None,
    title_text: str,
    content_text: str,
    on_click,
    button_icon_name=FluentIcon.LINK,
    button_alignment: str = "left",
    button_accessible_name: str | None = None,
    parent=None,
    delay_ms: int = 250,
):
    card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=button_text,
        icon=QIcon(),
        title_text=title_text,
        content_text=content_text,
        on_click=on_click,
        button_icon_name=button_icon_name,
        button_alignment=button_alignment,
        button_accessible_name=button_accessible_name,
        parent=parent,
    )
    schedule_push_setting_card_icon(card, icon_name=icon_name, icon_color=icon_color, delay_ms=delay_ms)
    return card


def schedule_push_setting_card_icon(card, *, icon_name: str, icon_color: str | None = None, delay_ms: int = 250) -> None:
    def _apply_icon() -> None:
        try:
            icon = get_themed_qta_icon(icon_name, color=icon_color) if icon_color else get_themed_qta_icon(icon_name)
            icon_label = getattr(card, "iconLabel", None)
            set_icon = getattr(icon_label, "setIcon", None)
            if callable(set_icon):
                set_icon(icon)
        except Exception:
            pass

    try:
        QTimer.singleShot(delay_ms, _apply_icon)
    except Exception:
        _apply_icon()


def build_push_setting_card_common(
    *,
    push_setting_card_cls,
    button_text: str,
    icon,
    title_text: str,
    content_text: str,
    on_click,
    button_icon_name=FluentIcon.LINK,
    button_alignment: str = "left",
    button_accessible_name: str | None = None,
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
    accessible_name = button_accessible_name or _push_setting_button_accessible_name(button_text, title_text)
    set_state_text(card, accessible_name)
    set_control_accessibility(card, name=accessible_name, description=content_text)
    enable_keyboard_click(card)
    button = getattr(card, "button", None)
    if button is not None:
        if hasattr(button_icon_name, "icon"):
            button_icon_name = button_icon_name.icon()
        button.setIcon(button_icon_name)
        button.setMinimumWidth(128)
        set_button_text_accessibility(
            button,
            button_text,
            accessible_name=accessible_name,
            description=content_text,
        )
    card.clicked.connect(on_click)
    return card


def _push_setting_button_accessible_name(button_text: str, title_text: str) -> str:
    button = str(button_text or "").strip()
    title = str(title_text or "").strip()
    if not button:
        return title
    if not title:
        return button
    if title.casefold().startswith(button.casefold()):
        return title
    return f"{button} {title[:1].lower()}{title[1:]}"
