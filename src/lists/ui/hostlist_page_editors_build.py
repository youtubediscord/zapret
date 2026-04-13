"""Build-helper'ы editor-панелей domains и ips для страницы Листы."""

from __future__ import annotations

from dataclasses import dataclass

from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class DomainsPanelWidgets:
    panel: object
    add_card: object
    input_edit: object
    add_button: object
    actions_group: object
    actions_bar: object
    open_action: object
    reset_action: object
    clear_action: object
    editor_card: object
    editor: object
    hint_label: object
    status_label: object


@dataclass(slots=True)
class IpsPanelWidgets:
    panel: object
    add_card: object
    input_edit: object
    add_button: object
    actions_group: object
    actions_bar: object
    open_action: object
    clear_action: object
    editor_card: object
    editor: object
    hint_label: object
    error_label: object
    status_label: object


def build_domains_panel_ui(
    *,
    content_parent,
    tr_fn,
    get_theme_tokens_fn,
    qwidget_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    settings_card_cls,
    body_label_cls,
    caption_label_cls,
    line_edit_cls,
    primary_push_button_cls,
    setting_card_group_cls,
    quick_actions_bar_cls,
    action_button_cls,
    plain_text_edit_cls,
    insert_widget_into_setting_card_group_fn,
    set_tooltip_fn,
    qta_module,
    on_add,
    on_open_file,
    on_reset_file,
    on_clear_all,
    on_text_changed,
) -> DomainsPanelWidgets:
    tokens = get_theme_tokens_fn()
    panel = qwidget_cls()
    layout = qvbox_layout_cls(panel)
    layout.setContentsMargins(0, 8, 0, 0)
    layout.setSpacing(12)

    desc_card = settings_card_cls()
    desc = body_label_cls(
        tr_fn(
            "page.hostlist.domains.desc",
            "Редактируется файл other.user.txt (только ваши домены). "
            "Системная база хранится в other.base.txt, общий other.txt собирается автоматически. "
            "URL автоматически преобразуются в домены. Изменения сохраняются автоматически. "
            "Поддерживается Ctrl+Z.",
        )
    )
    desc.setWordWrap(True)
    desc_card.add_widget(desc)
    layout.addWidget(desc_card)

    add_card = settings_card_cls(tr_fn("page.hostlist.domains.section.add", "Добавить домен"))
    add_row = qhbox_layout_cls()
    add_row.setSpacing(8)
    input_edit = line_edit_cls()
    if hasattr(input_edit, "setPlaceholderText"):
        input_edit.setPlaceholderText(
            tr_fn(
                "page.hostlist.domains.input.placeholder",
                "Введите домен или URL (например: example.com)",
            )
        )
    if hasattr(input_edit, "returnPressed"):
        input_edit.returnPressed.connect(on_add)
    add_row.addWidget(input_edit, 1)
    add_button = primary_push_button_cls()
    add_button.setText(tr_fn("page.hostlist.button.add", "Добавить"))
    add_button.setIcon(get_themed_qta_icon("fa5s.plus", color=tokens.accent_hex))
    add_button.setFixedHeight(38)
    add_button.clicked.connect(on_add)
    add_row.addWidget(add_button)
    add_card.add_layout(add_row)
    layout.addWidget(add_card)

    actions_group = setting_card_group_cls(tr_fn("page.hostlist.section.actions", "Действия"), content_parent)
    actions_bar = quick_actions_bar_cls(content_parent)

    open_action = action_button_cls(
        tr_fn("page.hostlist.button.open_file", "Открыть файл"),
        "fa5s.external-link-alt",
    )
    open_action.clicked.connect(on_open_file)
    set_tooltip_fn(
        open_action,
        tr_fn(
            "page.hostlist.domains.tooltip.open_file",
            "Сохраняет изменения и открывает other.user.txt в проводнике",
        ),
    )

    reset_action = action_button_cls(
        tr_fn("page.hostlist.button.reset_file", "Сбросить файл"),
        "fa5s.undo",
    )
    reset_action.clicked.connect(on_reset_file)
    set_tooltip_fn(
        reset_action,
        tr_fn(
            "page.hostlist.domains.tooltip.reset_file",
            "Очищает other.user.txt и пересобирает other.txt из системной базы",
        ),
    )

    clear_action = action_button_cls(
        tr_fn("page.hostlist.button.clear_all", "Очистить всё"),
        "fa5s.trash-alt",
    )
    clear_action.clicked.connect(on_clear_all)
    set_tooltip_fn(
        clear_action,
        tr_fn("page.hostlist.domains.tooltip.clear_all", "Удаляет только пользовательские домены"),
    )

    actions_bar.add_buttons([open_action, reset_action, clear_action])
    insert_widget_into_setting_card_group_fn(actions_group, 1, actions_bar)
    layout.addWidget(actions_group)

    editor_card = settings_card_cls(
        tr_fn("page.hostlist.domains.section.editor", "other.user.txt (редактор)")
    )
    editor_layout = qvbox_layout_cls()
    editor_layout.setSpacing(8)
    editor = plain_text_edit_cls()
    editor.setPlaceholderText(
        tr_fn(
            "page.hostlist.domains.editor.placeholder",
            "Домены по одному на строку:\nexample.com\nsubdomain.site.org\n\nКомментарии начинаются с #",
        )
    )
    editor.setMinimumHeight(350)
    editor.textChanged.connect(on_text_changed)
    editor_layout.addWidget(editor)
    hint_label = caption_label_cls(
        tr_fn("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
    )
    editor_layout.addWidget(hint_label)
    editor_card.add_layout(editor_layout)
    layout.addWidget(editor_card)

    status_label = caption_label_cls()
    layout.addWidget(status_label)
    layout.addStretch()

    return DomainsPanelWidgets(
        panel=panel,
        add_card=add_card,
        input_edit=input_edit,
        add_button=add_button,
        actions_group=actions_group,
        actions_bar=actions_bar,
        open_action=open_action,
        reset_action=reset_action,
        clear_action=clear_action,
        editor_card=editor_card,
        editor=editor,
        hint_label=hint_label,
        status_label=status_label,
    )


def build_ips_panel_ui(
    *,
    content_parent,
    tr_fn,
    get_theme_tokens_fn,
    qwidget_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    settings_card_cls,
    body_label_cls,
    caption_label_cls,
    line_edit_cls,
    primary_push_button_cls,
    setting_card_group_cls,
    quick_actions_bar_cls,
    action_button_cls,
    plain_text_edit_cls,
    insert_widget_into_setting_card_group_fn,
    set_tooltip_fn,
    qta_module,
    on_add,
    on_open_file,
    on_clear_all,
    on_text_changed,
) -> IpsPanelWidgets:
    tokens = get_theme_tokens_fn()
    panel = qwidget_cls()
    layout = qvbox_layout_cls(panel)
    layout.setContentsMargins(0, 8, 0, 0)
    layout.setSpacing(12)

    desc_card = settings_card_cls()
    desc = body_label_cls(
        tr_fn(
            "page.hostlist.ips.desc",
            "Добавляйте свои IP/подсети в ipset-all.user.txt.\n"
            "• Одиночный IP: 1.2.3.4\n"
            "• Подсеть: 10.0.0.0/8\n"
            "Диапазоны (a-b) не поддерживаются. Изменения сохраняются автоматически.\n"
            "Системная база хранится в ipset-all.base.txt и автоматически объединяется в ipset-all.txt.",
        )
    )
    desc.setWordWrap(True)
    desc_card.add_widget(desc)
    layout.addWidget(desc_card)

    add_card = settings_card_cls(tr_fn("page.hostlist.ips.section.add", "Добавить IP/подсеть"))
    add_row = qhbox_layout_cls()
    add_row.setSpacing(8)
    input_edit = line_edit_cls()
    if hasattr(input_edit, "setPlaceholderText"):
        input_edit.setPlaceholderText(
            tr_fn("page.hostlist.ips.input.placeholder", "Например: 1.2.3.4 или 10.0.0.0/8")
        )
    if hasattr(input_edit, "returnPressed"):
        input_edit.returnPressed.connect(on_add)
    add_row.addWidget(input_edit, 1)
    add_button = primary_push_button_cls()
    add_button.setText(tr_fn("page.hostlist.button.add", "Добавить"))
    add_button.setIcon(get_themed_qta_icon("fa5s.plus", color=tokens.accent_hex))
    add_button.setFixedHeight(38)
    add_button.clicked.connect(on_add)
    add_row.addWidget(add_button)
    add_card.add_layout(add_row)
    layout.addWidget(add_card)

    actions_group = setting_card_group_cls(tr_fn("page.hostlist.section.actions", "Действия"), content_parent)
    actions_bar = quick_actions_bar_cls(content_parent)

    open_action = action_button_cls(
        tr_fn("page.hostlist.button.open_file", "Открыть файл"),
        "fa5s.external-link-alt",
    )
    open_action.clicked.connect(on_open_file)
    set_tooltip_fn(
        open_action,
        tr_fn("page.hostlist.ips.action.open_file.description", "Сохраняет изменения и открывает ipset-all.user.txt в проводнике."),
    )

    clear_action = action_button_cls(
        tr_fn("page.hostlist.button.clear_all", "Очистить всё"),
        "fa5s.trash-alt",
    )
    clear_action.clicked.connect(on_clear_all)
    set_tooltip_fn(
        clear_action,
        tr_fn("page.hostlist.ips.action.clear_all.description", "Удаляет все пользовательские IP и подсети."),
    )

    actions_bar.add_buttons([open_action, clear_action])
    insert_widget_into_setting_card_group_fn(actions_group, 1, actions_bar)
    layout.addWidget(actions_group)

    editor_card = settings_card_cls(
        tr_fn("page.hostlist.ips.section.editor", "ipset-all.user.txt (редактор)")
    )
    editor_layout = qvbox_layout_cls()
    editor_layout.setSpacing(8)
    editor = plain_text_edit_cls()
    editor.setPlaceholderText(
        tr_fn(
            "page.hostlist.ips.editor.placeholder",
            "IP/подсети по одному на строку:\n192.168.0.1\n10.0.0.0/8\n\nКомментарии начинаются с #",
        )
    )
    editor.setMinimumHeight(350)
    editor.textChanged.connect(on_text_changed)
    editor_layout.addWidget(editor)
    hint_label = caption_label_cls(
        tr_fn("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
    )
    editor_layout.addWidget(hint_label)
    error_label = caption_label_cls()
    error_label.setWordWrap(True)
    error_label.hide()
    editor_layout.addWidget(error_label)
    editor_card.add_layout(editor_layout)
    layout.addWidget(editor_card)

    status_label = caption_label_cls()
    layout.addWidget(status_label)
    layout.addStretch()

    return IpsPanelWidgets(
        panel=panel,
        add_card=add_card,
        input_edit=input_edit,
        add_button=add_button,
        actions_group=actions_group,
        actions_bar=actions_bar,
        open_action=open_action,
        clear_action=clear_action,
        editor_card=editor_card,
        editor=editor,
        hint_label=hint_label,
        error_label=error_label,
        status_label=status_label,
    )
