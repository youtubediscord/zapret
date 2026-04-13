"""Build-helper простых секций Control page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QIcon
from qfluentwidgets import SettingCard
from PyQt6.QtWidgets import QLabel

from direct_preset.ui.control.shared_builders import (
    build_direct_management_section_common,
    build_direct_status_section_common,
    build_push_setting_card_common,
)
from ui.theme import get_cached_qta_pixmap


@dataclass(slots=True)
class ControlStatusWidgets:
    card: object
    status_dot: object
    status_title: object
    status_desc: object


@dataclass(slots=True)
class ControlManagementWidgets:
    card: object
    start_btn: object
    stop_winws_btn: object
    stop_and_exit_btn: object
    progress_bar: object
    loading_label: object


@dataclass(slots=True)
class ControlStrategyWidgets:
    card: object
    strategy_label: object
    strategy_desc: object


@dataclass(slots=True)
class ControlExtraActionsWidgets:
    section_label: object | None
    actions_group: object
    test_card: object
    folder_card: object
    test_btn: object
    folder_btn: object


def build_control_status_section(
    *,
    tr_fn,
    subtitle_label_cls,
    caption_label_cls,
) -> ControlStatusWidgets:
    status_card, status_dot, status_title, status_desc = build_direct_status_section_common(
        tr_fn=tr_fn,
        strong_body_label_cls=subtitle_label_cls,
        caption_label_cls=caption_label_cls,
        checking_key="page.control.status.checking",
        checking_default="Проверка...",
        detecting_key="page.control.status.detecting",
        detecting_default="Определение состояния процесса",
    )
    return ControlStatusWidgets(
        card=status_card,
        status_dot=status_dot,
        status_title=status_title,
        status_desc=status_desc,
    )


def build_control_management_section(
    *,
    tr_fn,
    caption_label_cls,
    indeterminate_progress_bar_cls,
    big_action_button_cls,
    stop_button_cls,
    on_start,
    on_stop_winws,
    on_stop_and_exit,
    parent,
) -> ControlManagementWidgets:
    control_card, start_btn, stop_winws_btn, stop_and_exit_btn, progress_bar, loading_label = (
        build_direct_management_section_common(
            tr_fn=tr_fn,
            caption_label_cls=caption_label_cls,
            indeterminate_progress_bar_cls=indeterminate_progress_bar_cls,
            big_action_button_cls=big_action_button_cls,
            stop_button_cls=stop_button_cls,
            start_key="page.control.button.start",
            start_default="Запустить Zapret",
            stop_key="page.control.button.stop_only_winws",
            stop_default="Остановить только winws.exe",
            stop_exit_key="page.control.button.stop_and_exit",
            stop_exit_default="Остановить и закрыть программу",
            on_start=on_start,
            on_stop=on_stop_winws,
            on_stop_and_exit=on_stop_and_exit,
            parent=parent,
        )
    )

    return ControlManagementWidgets(
        card=control_card,
        start_btn=start_btn,
        stop_winws_btn=stop_winws_btn,
        stop_and_exit_btn=stop_and_exit_btn,
        progress_bar=progress_bar,
        loading_label=loading_label,
    )


def build_control_strategy_section(
    *,
    tr_fn,
    accent_hex: str,
) -> ControlStrategyWidgets:
    strategy_card = SettingCard(
        QIcon(get_cached_qta_pixmap('fa5s.cog', color=accent_hex, size=20)),
        tr_fn("page.control.strategy.not_selected", "Не выбрана"),
        tr_fn("page.control.strategy.select_hint", "Выберите стратегию в разделе «Стратегии»"),
    )

    return ControlStrategyWidgets(
        card=strategy_card,
        strategy_label=strategy_card.titleLabel,
        strategy_desc=strategy_card.contentLabel,
    )


def build_control_extra_actions_section(
    *,
    tr_fn,
    setting_card_group_cls,
    push_setting_card_cls,
    parent,
    on_test,
    on_open_folder,
) -> ControlExtraActionsWidgets:
    actions_group = setting_card_group_cls(
        tr_fn("page.control.section.additional", "Дополнительные действия"),
        parent,
    )
    test_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.control.button.open", "Открыть"),
        icon=get_cached_qta_pixmap("fa5s.wifi", color="#60cdff", size=20),
        title_text=tr_fn("page.control.button.connection_test", "Тест соединения"),
        content_text=tr_fn(
            "page.control.section.additional.test_desc",
            "Проверить сетевое подключение и доступность маршрута",
        ),
        on_click=on_test,
        parent=parent,
    )
    folder_card = build_push_setting_card_common(
        push_setting_card_cls=push_setting_card_cls,
        button_text=tr_fn("page.control.button.open", "Открыть"),
        icon=get_cached_qta_pixmap("fa5s.folder-open", color="#f5c04d", size=20),
        title_text=tr_fn("page.control.button.open_folder", "Открыть папку"),
        content_text=tr_fn(
            "page.control.section.additional.folder_desc",
            "Быстро перейти к рабочей папке программы",
        ),
        on_click=on_open_folder,
        parent=parent,
    )
    actions_group.addSettingCard(test_card)
    actions_group.addSettingCard(folder_card)

    return ControlExtraActionsWidgets(
        section_label=None,
        actions_group=actions_group,
        test_card=test_card,
        folder_card=folder_card,
        test_btn=test_card.button,
        folder_btn=folder_card.button,
    )
