"""Build-helper shell страницы профилей."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ui.fluent_widgets import set_tooltip
from ui.presets_menu.toolbar import PresetsToolbarLayout
from qfluentwidgets import FluentIcon, PrimaryPushButton, PrimaryToolButton, PushButton, SearchLineEdit


@dataclass(slots=True)
class ProfileShellWidgets:
    toolbar_actions_bar: object
    add_profile_btn: object
    request_btn: object
    expand_btn: object
    collapse_btn: object
    order_btn: object
    info_btn: object
    profile_search_input: object
    content_host: object
    content_host_layout: object


def build_profile_shell(
    *,
    content_parent,
    content_layout,
    add_section_title,
    tr_fn,
    engine_label: str,
    toolbar_title_key: str,
    request_button_key: str,
    request_hint_key: str,
    loading_key: str,
    on_open_profile_request_form,
    on_add_user_profile,
    on_expand_all,
    on_collapse_all,
    on_open_profile_order,
    on_show_info_popup,
    on_profile_search_text_changed,
) -> ProfileShellWidgets:
    toolbar_key_prefix = str(toolbar_title_key or "").rsplit(".", 1)[0]

    def _toolbar_key(name: str) -> str:
        if toolbar_key_prefix:
            return f"{toolbar_key_prefix}.{name}"
        return f"page.winws2_pages.toolbar.{name}"

    _ = add_section_title
    toolbar_actions_bar = PresetsToolbarLayout(content_parent)

    add_profile_btn = toolbar_actions_bar.create_primary_tool_button(
        PrimaryToolButton,
        FluentIcon.ADD,
    )
    add_profile_btn.clicked.connect(on_add_user_profile)
    set_tooltip(
        add_profile_btn,
        tr_fn(
            _toolbar_key("add.description"),
            "Добавить новый пользовательский profile в общий список.",
        )
    )

    request_btn = PrimaryPushButton(
        tr_fn(request_button_key, "ОТКРЫТЬ ФОРМУ НА GITHUB"),
        icon=FluentIcon.GITHUB,
    )
    request_btn.clicked.connect(on_open_profile_request_form)
    set_tooltip(
        request_btn,
        tr_fn(
            request_hint_key,
            f"Хотите добавить новый сайт или сервис в {engine_label}? Откройте готовую форму на GitHub и опишите, что нужно добавить в hostlist или ipset.",
        )
    )

    expand_btn = PushButton(
        tr_fn(_toolbar_key("expand"), "Развернуть"),
        icon=FluentIcon.FULL_SCREEN,
    )
    expand_btn.clicked.connect(on_expand_all)
    set_tooltip(
        expand_btn,
        tr_fn(
            _toolbar_key("expand.description"),
            "Развернуть все группы профилей в списке.",
        )
    )

    collapse_btn = PushButton(
        tr_fn(_toolbar_key("collapse"), "Свернуть"),
        icon=FluentIcon.BACK_TO_WINDOW,
    )
    collapse_btn.clicked.connect(on_collapse_all)
    set_tooltip(
        collapse_btn,
        tr_fn(
            _toolbar_key("collapse.description"),
            "Свернуть все группы профилей в списке.",
        )
    )

    order_btn = PushButton(
        tr_fn(_toolbar_key("order"), "Порядок в пресете"),
        icon=FluentIcon.MENU,
    )
    order_btn.clicked.connect(on_open_profile_order)
    set_tooltip(
        order_btn,
        tr_fn(
            _toolbar_key("order.description"),
            "Открыть отдельный список для изменения реального порядка профилей внутри файла пресета.",
        )
    )

    info_btn = PushButton(
        tr_fn(_toolbar_key("info"), "Что это такое?"),
        icon=FluentIcon.QUESTION,
    )
    info_btn.clicked.connect(on_show_info_popup)
    set_tooltip(
        info_btn,
        tr_fn(
            _toolbar_key("info.description"),
            f"Показать краткое объяснение по работе режима профилей {engine_label}.",
        )
    )

    profile_search_input = SearchLineEdit(content_parent)
    profile_search_input.setPlaceholderText(
        tr_fn(_toolbar_key("search.placeholder"), "Поиск профиля по имени, портам и т.д.")
    )
    profile_search_input.setClearButtonEnabled(True)
    profile_search_input.setFixedHeight(34)
    profile_search_input.setProperty("noDrag", True)
    profile_search_input.textChanged.connect(on_profile_search_text_changed)

    toolbar_actions_bar.set_buttons([
        add_profile_btn,
        request_btn,
        expand_btn,
        collapse_btn,
        order_btn,
        info_btn,
    ])
    toolbar_actions_bar.set_trailing_widget(profile_search_input, minimum_width=280)
    toolbar_actions_bar.refresh_for_viewport(content_parent.width(), content_layout.contentsMargins())
    content_layout.addWidget(toolbar_actions_bar.container)

    content_host = QWidget(content_parent)
    content_host_layout = QVBoxLayout(content_host)
    content_host_layout.setContentsMargins(0, 0, 0, 0)
    content_host_layout.setSpacing(8)

    _ = loading_key

    content_layout.addWidget(content_host, 1)

    return ProfileShellWidgets(
        toolbar_actions_bar=toolbar_actions_bar,
        add_profile_btn=add_profile_btn,
        request_btn=request_btn,
        expand_btn=expand_btn,
        collapse_btn=collapse_btn,
        order_btn=order_btn,
        info_btn=info_btn,
        profile_search_input=profile_search_input,
        content_host=content_host,
        content_host_layout=content_host_layout,
    )
