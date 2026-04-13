"""Build-helper custom domains секции для Blockcheck page."""

from __future__ import annotations

from dataclasses import dataclass

from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class BlockcheckDomainsWidgets:
    card: object
    input_edit: object
    add_button: object
    flow_widget: object
    flow_layout: object


def build_blockcheck_domains_ui(
    *,
    tr_fn,
    settings_card_cls,
    qhbox_layout_cls,
    qwidget_cls,
    line_edit_cls,
    push_button_cls,
    qta_module,
    theme_color_fn,
    on_add,
) -> BlockcheckDomainsWidgets:
    card = settings_card_cls(
        tr_fn("page.blockcheck.custom_domains", "Пользовательские домены")
    )

    input_row = qhbox_layout_cls()
    input_row.setSpacing(8)

    input_edit = line_edit_cls()
    input_edit.setPlaceholderText(
        tr_fn("page.blockcheck.domain_placeholder", "example.com")
    )
    input_edit.setFixedHeight(33)
    input_edit.returnPressed.connect(on_add)
    input_row.addWidget(input_edit)

    add_button = push_button_cls()
    add_button.setText(tr_fn("page.blockcheck.add_domain", "Добавить"))
    add_button.setIcon(get_themed_qta_icon("fa5s.plus", color=theme_color_fn().name()))
    add_button.clicked.connect(on_add)
    input_row.addWidget(add_button)

    card.add_layout(input_row)

    flow_widget = qwidget_cls()
    flow_layout = qhbox_layout_cls(flow_widget)
    flow_layout.setContentsMargins(0, 4, 0, 0)
    flow_layout.setSpacing(6)
    flow_layout.addStretch()
    card.add_widget(flow_widget)

    return BlockcheckDomainsWidgets(
        card=card,
        input_edit=input_edit,
        add_button=add_button,
        flow_widget=flow_widget,
        flow_layout=flow_layout,
    )
