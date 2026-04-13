"""Build-helper для панели exclusions в странице Листы."""

from __future__ import annotations

from dataclasses import dataclass

from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class ExclusionsPanelWidgets:
    panel: object
    excl_add_card: object
    excl_input: object
    excl_add_btn: object
    excl_actions_group: object
    excl_actions_bar: object
    excl_defaults_action_card: object
    excl_open_action_card: object
    excl_open_final_action_card: object
    excl_clear_action_card: object
    excl_editor_card: object
    excl_editor: object
    excl_hint_label: object
    excl_status: object
    ipru_title_label: object
    ipru_desc_label: object
    ipru_add_card: object
    ipru_input: object
    ipru_add_btn: object
    ipru_actions_group: object
    ipru_actions_bar: object
    ipru_open_action_card: object
    ipru_open_final_action_card: object
    ipru_clear_action_card: object
    ipru_editor_card: object
    ipru_editor: object
    ipru_hint_label: object
    ipru_error_label: object
    ipru_status: object


def build_exclusions_panel_ui(
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
    strong_body_label_cls,
    line_edit_cls,
    primary_push_button_cls,
    setting_card_group_cls,
    quick_actions_bar_cls,
    action_button_cls,
    plain_text_edit_cls,
    insert_widget_into_setting_card_group_fn,
    set_tooltip_fn,
    qta_module,
    on_excl_add,
    on_excl_defaults,
    on_excl_open_file,
    on_excl_open_final,
    on_excl_clear_all,
    on_excl_text_changed,
    on_ipru_add,
    on_ipru_open_file,
    on_ipru_open_final,
    on_ipru_clear_all,
    on_ipru_text_changed,
) -> ExclusionsPanelWidgets:
    tokens = get_theme_tokens_fn()
    panel = qwidget_cls()
    layout = qvbox_layout_cls(panel)
    layout.setContentsMargins(0, 8, 0, 0)
    layout.setSpacing(12)

    desc_card = settings_card_cls()
    desc = body_label_cls(
        tr_fn(
            "page.hostlist.exclusions.desc",
            "Исключения для хостлистов и ipset.\n"
            "• Домены: netrogat.user.txt -> netrogat.txt (--hostlist-exclude)\n"
            "• IP/подсети: ipset-ru.user.txt -> ipset-ru.txt (--ipset-exclude)",
        )
    )
    desc.setWordWrap(True)
    desc_card.add_widget(desc)
    layout.addWidget(desc_card)

    excl_add_card = settings_card_cls(
        tr_fn("page.hostlist.exclusions.section.add_domain", "Добавить домен")
    )
    add_row = qhbox_layout_cls()
    add_row.setSpacing(8)
    excl_input = line_edit_cls()
    if hasattr(excl_input, "setPlaceholderText"):
        excl_input.setPlaceholderText(
            tr_fn(
                "page.hostlist.exclusions.input.domain.placeholder",
                "Введите домен (например: gosuslugi.ru)",
            )
        )
    if hasattr(excl_input, "returnPressed"):
        excl_input.returnPressed.connect(on_excl_add)
    add_row.addWidget(excl_input, 1)
    excl_add_btn = primary_push_button_cls()
    excl_add_btn.setText(tr_fn("page.hostlist.button.add", "Добавить"))
    excl_add_btn.setIcon(get_themed_qta_icon("fa5s.plus", color=tokens.accent_hex))
    excl_add_btn.setFixedHeight(38)
    excl_add_btn.clicked.connect(on_excl_add)
    add_row.addWidget(excl_add_btn)
    excl_add_card.add_layout(add_row)
    layout.addWidget(excl_add_card)

    excl_actions_group = setting_card_group_cls(tr_fn("page.hostlist.section.actions", "Действия"), content_parent)
    excl_actions_bar = quick_actions_bar_cls(content_parent)

    excl_defaults_action_card = action_button_cls(
        tr_fn("page.hostlist.exclusions.button.add_missing", "Добавить недостающие"),
        "fa5s.plus-circle",
    )
    excl_defaults_action_card.clicked.connect(on_excl_defaults)
    set_tooltip_fn(
        excl_defaults_action_card,
        tr_fn(
            "page.hostlist.exclusions.action.add_missing.description",
            "Восстановить недостающие домены по умолчанию в системной базе netrogat.",
        ),
    )

    excl_open_action_card = action_button_cls(
        tr_fn("page.hostlist.button.open_file", "Открыть файл"),
        "fa5s.external-link-alt",
    )
    excl_open_action_card.clicked.connect(on_excl_open_file)
    set_tooltip_fn(
        excl_open_action_card,
        tr_fn(
            "page.hostlist.exclusions.action.open_file.description",
            "Сохраняет изменения и открывает netrogat.user.txt в проводнике.",
        ),
    )

    excl_open_final_action_card = action_button_cls(
        tr_fn("page.hostlist.exclusions.button.open_final", "Открыть итоговый"),
        "fa5s.file-alt",
    )
    excl_open_final_action_card.clicked.connect(on_excl_open_final)
    set_tooltip_fn(
        excl_open_final_action_card,
        tr_fn(
            "page.hostlist.exclusions.action.open_final.description",
            "Сохраняет изменения и открывает собранный итоговый файл netrogat.txt.",
        ),
    )

    excl_clear_action_card = action_button_cls(
        tr_fn("page.hostlist.button.clear_all", "Очистить всё"),
        "fa5s.trash-alt",
    )
    excl_clear_action_card.clicked.connect(on_excl_clear_all)
    set_tooltip_fn(
        excl_clear_action_card,
        tr_fn(
            "page.hostlist.exclusions.action.clear_all.description",
            "Удаляет все пользовательские домены из netrogat.user.txt.",
        ),
    )

    excl_actions_bar.add_buttons([
        excl_defaults_action_card,
        excl_open_action_card,
        excl_open_final_action_card,
        excl_clear_action_card,
    ])
    insert_widget_into_setting_card_group_fn(excl_actions_group, 1, excl_actions_bar)
    layout.addWidget(excl_actions_group)

    excl_editor_card = settings_card_cls(
        tr_fn("page.hostlist.exclusions.section.editor_domain", "netrogat.user.txt (редактор)")
    )
    excl_editor_layout = qvbox_layout_cls()
    excl_editor_layout.setSpacing(8)
    excl_editor = plain_text_edit_cls()
    excl_editor.setPlaceholderText(
        tr_fn(
            "page.hostlist.exclusions.editor.domain.placeholder",
            "Домены по одному на строку:\ngosuslugi.ru\nvk.com\n\nКомментарии начинаются с #",
        )
    )
    excl_editor.setMinimumHeight(350)
    excl_editor.textChanged.connect(on_excl_text_changed)
    excl_editor_layout.addWidget(excl_editor)
    excl_hint_label = caption_label_cls(
        tr_fn("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
    )
    excl_editor_layout.addWidget(excl_hint_label)
    excl_editor_card.add_layout(excl_editor_layout)
    layout.addWidget(excl_editor_card)

    excl_status = caption_label_cls()
    layout.addWidget(excl_status)

    ipru_intro = settings_card_cls()
    ipru_title_label = strong_body_label_cls(
        tr_fn("page.hostlist.exclusions.ipru.title", "IP-исключения (--ipset-exclude)")
    )
    ipru_title_label.setWordWrap(True)
    ipru_intro.add_widget(ipru_title_label)
    ipru_desc_label = caption_label_cls(
        tr_fn(
            "page.hostlist.exclusions.ipru.desc",
            "Редактируйте только ipset-ru.user.txt. "
            "Системная база хранится в ipset-ru.base.txt и автоматически объединяется в ipset-ru.txt.",
        )
    )
    ipru_desc_label.setWordWrap(True)
    ipru_intro.add_widget(ipru_desc_label)
    layout.addWidget(ipru_intro)

    ipru_add_card = settings_card_cls(
        tr_fn("page.hostlist.exclusions.ipru.section.add", "Добавить IP/подсеть в исключения")
    )
    ipru_add_row = qhbox_layout_cls()
    ipru_add_row.setSpacing(8)
    ipru_input = line_edit_cls()
    if hasattr(ipru_input, "setPlaceholderText"):
        ipru_input.setPlaceholderText(
            tr_fn("page.hostlist.ips.input.placeholder", "Например: 1.2.3.4 или 10.0.0.0/8")
        )
    if hasattr(ipru_input, "returnPressed"):
        ipru_input.returnPressed.connect(on_ipru_add)
    ipru_add_row.addWidget(ipru_input, 1)
    ipru_add_btn = primary_push_button_cls()
    ipru_add_btn.setText(tr_fn("page.hostlist.button.add", "Добавить"))
    ipru_add_btn.setIcon(get_themed_qta_icon("fa5s.plus", color=tokens.accent_hex))
    ipru_add_btn.setFixedHeight(38)
    ipru_add_btn.clicked.connect(on_ipru_add)
    ipru_add_row.addWidget(ipru_add_btn)
    ipru_add_card.add_layout(ipru_add_row)
    layout.addWidget(ipru_add_card)

    ipru_actions_group = setting_card_group_cls(
        tr_fn("page.hostlist.exclusions.ipru.section.actions", "Действия IP-исключений"),
        content_parent,
    )
    ipru_actions_bar = quick_actions_bar_cls(content_parent)

    ipru_open_action_card = action_button_cls(
        tr_fn("page.hostlist.button.open_file", "Открыть файл"),
        "fa5s.external-link-alt",
    )
    ipru_open_action_card.clicked.connect(on_ipru_open_file)
    set_tooltip_fn(
        ipru_open_action_card,
        tr_fn(
            "page.hostlist.exclusions.ipru.action.open_file.description",
            "Сохраняет изменения и открывает ipset-ru.user.txt в проводнике.",
        ),
    )

    ipru_open_final_action_card = action_button_cls(
        tr_fn("page.hostlist.exclusions.button.open_final", "Открыть итоговый"),
        "fa5s.file-alt",
    )
    ipru_open_final_action_card.clicked.connect(on_ipru_open_final)
    set_tooltip_fn(
        ipru_open_final_action_card,
        tr_fn(
            "page.hostlist.exclusions.ipru.action.open_final.description",
            "Сохраняет изменения и открывает итоговый ipset-ru.txt.",
        ),
    )

    ipru_clear_action_card = action_button_cls(
        tr_fn("page.hostlist.button.clear_all", "Очистить всё"),
        "fa5s.trash-alt",
    )
    ipru_clear_action_card.clicked.connect(on_ipru_clear_all)
    set_tooltip_fn(
        ipru_clear_action_card,
        tr_fn(
            "page.hostlist.exclusions.ipru.action.clear_all.description",
            "Удаляет все пользовательские IP-исключения из ipset-ru.user.txt.",
        ),
    )

    ipru_actions_bar.add_buttons([
        ipru_open_action_card,
        ipru_open_final_action_card,
        ipru_clear_action_card,
    ])
    insert_widget_into_setting_card_group_fn(ipru_actions_group, 1, ipru_actions_bar)
    layout.addWidget(ipru_actions_group)

    ipru_editor_card = settings_card_cls(
        tr_fn("page.hostlist.exclusions.ipru.section.editor", "ipset-ru.user.txt (редактор)")
    )
    ipru_editor_layout = qvbox_layout_cls()
    ipru_editor_layout.setSpacing(8)
    ipru_editor = plain_text_edit_cls()
    ipru_editor.setPlaceholderText(
        tr_fn(
            "page.hostlist.exclusions.ipru.editor.placeholder",
            "IP/подсети по одному на строку:\n"
            "31.13.64.0/18\n"
            "77.88.0.0/18\n\n"
            "Комментарии начинаются с #",
        )
    )
    ipru_editor.setMinimumHeight(260)
    ipru_editor.textChanged.connect(on_ipru_text_changed)
    ipru_editor_layout.addWidget(ipru_editor)
    ipru_hint_label = caption_label_cls(
        tr_fn("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
    )
    ipru_editor_layout.addWidget(ipru_hint_label)
    ipru_error_label = caption_label_cls()
    ipru_error_label.setWordWrap(True)
    ipru_error_label.hide()
    ipru_editor_layout.addWidget(ipru_error_label)
    ipru_editor_card.add_layout(ipru_editor_layout)
    layout.addWidget(ipru_editor_card)

    ipru_status = caption_label_cls()
    layout.addWidget(ipru_status)
    layout.addStretch()

    return ExclusionsPanelWidgets(
        panel=panel,
        excl_add_card=excl_add_card,
        excl_input=excl_input,
        excl_add_btn=excl_add_btn,
        excl_actions_group=excl_actions_group,
        excl_actions_bar=excl_actions_bar,
        excl_defaults_action_card=excl_defaults_action_card,
        excl_open_action_card=excl_open_action_card,
        excl_open_final_action_card=excl_open_final_action_card,
        excl_clear_action_card=excl_clear_action_card,
        excl_editor_card=excl_editor_card,
        excl_editor=excl_editor,
        excl_hint_label=excl_hint_label,
        excl_status=excl_status,
        ipru_title_label=ipru_title_label,
        ipru_desc_label=ipru_desc_label,
        ipru_add_card=ipru_add_card,
        ipru_input=ipru_input,
        ipru_add_btn=ipru_add_btn,
        ipru_actions_group=ipru_actions_group,
        ipru_actions_bar=ipru_actions_bar,
        ipru_open_action_card=ipru_open_action_card,
        ipru_open_final_action_card=ipru_open_final_action_card,
        ipru_clear_action_card=ipru_clear_action_card,
        ipru_editor_card=ipru_editor_card,
        ipru_editor=ipru_editor,
        ipru_hint_label=ipru_hint_label,
        ipru_error_label=ipru_error_label,
        ipru_status=ipru_status,
    )
