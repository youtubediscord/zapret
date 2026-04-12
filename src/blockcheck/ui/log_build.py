"""Build-helper log card секции для Blockcheck page."""

from __future__ import annotations

from dataclasses import dataclass

from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class BlockcheckLogWidgets:
    card: object
    expand_button: object
    support_status_label: object
    prepare_support_button: object
    log_edit: object


def build_log_card_section(
    *,
    tr_fn,
    settings_card_cls,
    qhbox_layout_cls,
    caption_label_cls,
    push_button_cls,
    qta_module,
    theme_color_fn,
    text_edit_cls,
    qfont_cls,
    on_toggle_expand,
    on_prepare_support,
) -> BlockcheckLogWidgets:
    card = settings_card_cls(
        tr_fn("page.blockcheck.log", "Подробный лог")
    )

    expand_btn = push_button_cls()
    expand_btn.setText("Развернуть")
    expand_btn.setFixedWidth(120)
    expand_btn.clicked.connect(on_toggle_expand)

    log_header = qhbox_layout_cls()
    support_status_label = caption_label_cls("")
    support_status_label.setWordWrap(True)
    log_header.addWidget(support_status_label, 1)
    log_header.addStretch()

    prepare_support_btn = push_button_cls()
    prepare_support_btn.setText(
        tr_fn("page.blockcheck.prepare_support", "Подготовить обращение")
    )
    prepare_support_btn.setIcon(get_themed_qta_icon("fa5b.github", color=theme_color_fn().name()))
    prepare_support_btn.clicked.connect(on_prepare_support)
    log_header.addWidget(prepare_support_btn)
    log_header.addWidget(expand_btn)
    card.add_layout(log_header)

    log_edit = text_edit_cls()
    log_edit.setReadOnly(True)
    log_edit.setMinimumHeight(180)
    log_edit.setMaximumHeight(300)
    log_edit.setFont(qfont_cls("Consolas", 9))
    card.add_widget(log_edit)

    return BlockcheckLogWidgets(
        card=card,
        expand_button=expand_btn,
        support_status_label=support_status_label,
        prepare_support_button=prepare_support_btn,
        log_edit=log_edit,
    )
