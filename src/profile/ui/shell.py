"""Build-helper shell страницы профилей."""

from __future__ import annotations

from dataclasses import dataclass
from types import MethodType

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from profile.ui.shell_accessibility import apply_profile_shell_accessibility
from ui.fluent_widgets import set_tooltip
from ui.popup_menu import exec_popup_menu
from ui.presets_menu.common import fluent_icon, make_menu_action
from ui.presets_menu.toolbar import PresetsToolbarLayout
from qfluentwidgets import FluentIcon, PrimaryPushButton, PrimaryToolButton, PushButton, RoundMenu, SearchLineEdit


@dataclass(slots=True)
class ProfileShellWidgets:
    toolbar_actions_bar: object
    add_profile_btn: object
    request_btn: object
    view_menu_btn: object
    order_btn: object
    info_btn: object
    profile_search_input: object
    content_host: object
    content_host_layout: object


def wire_profile_search_keyboard_activation(profile_search_input, profiles_list) -> None:
    """Enter в поиске profile открывает текущий элемент списка."""

    if profile_search_input is None or profiles_list is None:
        return
    if bool(getattr(profile_search_input, "_profile_search_keyboard_activation", False)):
        return
    original_key_press = getattr(profile_search_input, "keyPressEvent", None)

    def _search_key_press(self, event):
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Down,
            Qt.Key.Key_Up,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_PageUp,
        ):
            profiles_list.setFocus(Qt.FocusReason.OtherFocusReason)
            profiles_list.keyPressEvent(event)
            return
        if callable(original_key_press):
            original_key_press(event)

    profile_search_input.keyPressEvent = MethodType(_search_key_press, profile_search_input)
    profile_search_input._profile_search_keyboard_activation = True


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
    on_show_added_only,
    on_show_all_profiles,
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
    add_profile_description = tr_fn(
        _toolbar_key("add.description"),
        "Добавить новый пользовательский profile в общий список.",
    )
    set_tooltip(
        add_profile_btn,
        add_profile_description,
    )

    request_hint = tr_fn(
        request_hint_key,
        f"Хотите добавить новый сайт или сервис в {engine_label}? Откройте готовую форму на GitHub и опишите, что нужно добавить в hostlist или ipset.",
    )
    request_btn = PrimaryPushButton(
        tr_fn(request_button_key, "ОТКРЫТЬ ФОРМУ НА GITHUB"),
        icon=FluentIcon.GITHUB,
    )
    request_btn.clicked.connect(on_open_profile_request_form)
    set_tooltip(
        request_btn,
        request_hint,
    )

    view_menu_description = tr_fn(
        _toolbar_key("view_menu.description"),
        "Открывает меню, где можно развернуть или свернуть группы и выбрать, какие профили показывать.",
    )
    view_menu_btn = PushButton(
        tr_fn(_toolbar_key("view_menu"), "Вид"),
        icon=FluentIcon.MENU,
    )
    view_menu_btn.clicked.connect(
        lambda: show_profile_view_menu(
            parent=content_parent,
            button=view_menu_btn,
            tr_fn=tr_fn,
            toolbar_key=_toolbar_key,
            on_expand_all=on_expand_all,
            on_collapse_all=on_collapse_all,
            on_show_added_only=on_show_added_only,
            on_show_all_profiles=on_show_all_profiles,
        )
    )
    set_tooltip(
        view_menu_btn,
        view_menu_description,
    )

    order_description = tr_fn(
        _toolbar_key("order.description"),
        "Открыть отдельный список для изменения реального порядка профилей внутри файла пресета.",
    )
    order_btn = PushButton(
        tr_fn(_toolbar_key("order"), "Порядок в пресете"),
        icon=FluentIcon.MENU,
    )
    order_btn.clicked.connect(on_open_profile_order)
    set_tooltip(
        order_btn,
        order_description,
    )

    info_description = tr_fn(
        _toolbar_key("info.description"),
        f"Показать краткое объяснение по работе режима профилей {engine_label}.",
    )
    info_btn = PushButton(
        tr_fn(_toolbar_key("info"), "Что это такое?"),
        icon=FluentIcon.QUESTION,
    )
    info_btn.clicked.connect(on_show_info_popup)
    set_tooltip(
        info_btn,
        info_description,
    )

    search_placeholder = tr_fn(_toolbar_key("search.placeholder"), "Поиск профиля по имени, портам и т.д.")
    profile_search_input = SearchLineEdit(content_parent)
    profile_search_input.setPlaceholderText(search_placeholder)
    profile_search_input.setClearButtonEnabled(True)
    profile_search_input.setFixedHeight(34)
    profile_search_input.setProperty("noDrag", True)
    profile_search_input.textChanged.connect(on_profile_search_text_changed)
    apply_profile_shell_accessibility(
        add_profile_btn=add_profile_btn,
        request_btn=request_btn,
        view_menu_btn=view_menu_btn,
        order_btn=order_btn,
        info_btn=info_btn,
        profile_search_input=profile_search_input,
        tr_fn=tr_fn,
        toolbar_key=_toolbar_key,
        request_hint=request_hint,
        engine_label=engine_label,
    )

    toolbar_actions_bar.set_buttons([
        add_profile_btn,
        request_btn,
        view_menu_btn,
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
        view_menu_btn=view_menu_btn,
        order_btn=order_btn,
        info_btn=info_btn,
        profile_search_input=profile_search_input,
        content_host=content_host,
        content_host_layout=content_host_layout,
    )


def show_profile_view_menu(
    *,
    parent,
    button,
    tr_fn,
    toolbar_key,
    on_expand_all,
    on_collapse_all,
    on_show_added_only,
    on_show_all_profiles,
) -> None:
    menu = RoundMenu(parent=parent)
    action_map: dict[object, str] = {}

    def _add_action(text: str, *, icon_name: str, command: str, accessible_text: str):
        action = make_menu_action(text, icon=fluent_icon(icon_name), parent=menu)
        menu.addAction(action)
        menu_item = menu.view.item(menu.view.count() - 1)
        if menu_item is not None:
            menu_item.setData(Qt.ItemDataRole.AccessibleTextRole, accessible_text)
            menu_item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, accessible_text)
        action_map[action] = command

    _add_action(
        tr_fn(toolbar_key("expand"), "Развернуть все группы"),
        icon_name="FULL_SCREEN",
        command="expand",
        accessible_text=tr_fn(toolbar_key("expand.accessible_name"), "Развернуть все группы профилей"),
    )
    _add_action(
        tr_fn(toolbar_key("collapse"), "Свернуть все группы"),
        icon_name="BACK_TO_WINDOW",
        command="collapse",
        accessible_text=tr_fn(toolbar_key("collapse.accessible_name"), "Свернуть все группы профилей"),
    )
    menu.addSeparator()
    _add_action(
        tr_fn(toolbar_key("show_added_only"), "Показать только добавленные"),
        icon_name="ACCEPT",
        command="show_added_only",
        accessible_text=tr_fn(
            toolbar_key("show_added_only.accessible_name"),
            "Показать только профили, добавленные в текущий пресет",
        ),
    )
    _add_action(
        tr_fn(toolbar_key("show_all_profiles"), "Показать все профили"),
        icon_name="VIEW",
        command="show_all_profiles",
        accessible_text=tr_fn(toolbar_key("show_all_profiles.accessible_name"), "Показать все профили"),
    )

    try:
        global_pos = button.mapToGlobal(QPoint(0, button.height() + 4))
    except Exception:
        global_pos = None
    chosen = exec_popup_menu(menu, global_pos, owner=parent, capture_action=True)
    command = action_map.get(chosen, "")
    if command == "expand":
        on_expand_all()
    elif command == "collapse":
        on_collapse_all()
    elif command == "show_added_only":
        on_show_added_only()
    elif command == "show_all_profiles":
        on_show_all_profiles()
