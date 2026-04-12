"""Build-helper shell страницы Zapret2StrategiesPageNew."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ui.compat_widgets import QuickActionsBar, RefreshButton
from ui.theme import get_theme_tokens, get_themed_qta_icon
from qfluentwidgets import BodyLabel, PushButton, PrimaryPushButton


@dataclass(slots=True)
class Zapret2DirectShellWidgets:
    toolbar_actions_bar: object
    request_btn: object
    reload_btn: object
    expand_btn: object
    collapse_btn: object
    info_btn: object
    content_host: object
    content_host_layout: object
    loading_label: object


def build_z2_direct_shell(
    *,
    content_parent,
    content_layout,
    add_section_title,
    tr_fn,
    on_open_category_request_form,
    on_reload,
    on_expand_all,
    on_collapse_all,
    on_show_info_popup,
) -> Zapret2DirectShellWidgets:
    add_section_title(text_key="page.z2_direct.toolbar.title")
    toolbar_actions_bar = QuickActionsBar(content_parent)

    request_btn = PrimaryPushButton()
    request_btn.setText(
        tr_fn("page.z2_direct.request.button", "ОТКРЫТЬ ФОРМУ НА GITHUB")
    )
    request_btn.setIcon(get_themed_qta_icon("fa5b.github", color=get_theme_tokens().accent_hex))
    request_btn.clicked.connect(on_open_category_request_form)
    request_btn.setToolTip(
        tr_fn(
            "page.z2_direct.request.hint",
            "Хотите добавить новый сайт или сервис в Zapret 2? Откройте готовую форму на GitHub и опишите, что нужно добавить в hostlist или ipset.",
        )
    )
    toolbar_actions_bar.add_button(request_btn)

    reload_btn = RefreshButton()
    reload_btn.clicked.connect(on_reload)
    reload_btn.setToolTip(
        tr_fn(
            "page.z2_direct.toolbar.reload.description",
            "Обновить список категорий, target'ов и выбранных стратегий.",
        )
    )
    toolbar_actions_bar.add_button(reload_btn)

    expand_btn = PushButton()
    expand_btn.setText(tr_fn("page.z2_direct.toolbar.expand", "Развернуть"))
    expand_btn.setIcon(get_themed_qta_icon("fa5s.expand-alt", color="#4CAF50"))
    expand_btn.clicked.connect(on_expand_all)
    expand_btn.setToolTip(
        tr_fn(
            "page.z2_direct.toolbar.expand.description",
            "Развернуть все категории и target'ы в списке.",
        )
    )
    toolbar_actions_bar.add_button(expand_btn)

    collapse_btn = PushButton()
    collapse_btn.setText(tr_fn("page.z2_direct.toolbar.collapse", "Свернуть"))
    collapse_btn.setIcon(get_themed_qta_icon("fa5s.compress-alt", color="#ff9800"))
    collapse_btn.clicked.connect(on_collapse_all)
    collapse_btn.setToolTip(
        tr_fn(
            "page.z2_direct.toolbar.collapse.description",
            "Свернуть все категории и target'ы в списке.",
        )
    )
    toolbar_actions_bar.add_button(collapse_btn)

    info_btn = PushButton()
    info_btn.setText(tr_fn("page.z2_direct.toolbar.info", "Что это такое?"))
    info_btn.setIcon(get_themed_qta_icon("fa5s.question-circle", color="#60cdff"))
    info_btn.clicked.connect(on_show_info_popup)
    info_btn.setToolTip(
        tr_fn(
            "page.z2_direct.toolbar.info.description",
            "Показать краткое объяснение по работе прямого запуска Zapret 2.",
        )
    )
    toolbar_actions_bar.add_button(info_btn)
    content_layout.addWidget(toolbar_actions_bar)

    content_host = QWidget(content_parent)
    content_host_layout = QVBoxLayout(content_host)
    content_host_layout.setContentsMargins(0, 0, 0, 0)
    content_host_layout.setSpacing(8)

    loading_label = BodyLabel(
        tr_fn("page.z2_direct.loading", "Загрузка категорий и target'ов...")
    )
    loading_label.setWordWrap(True)
    loading_label.hide()
    content_host_layout.addWidget(loading_label)

    content_layout.addWidget(content_host, 1)

    return Zapret2DirectShellWidgets(
        toolbar_actions_bar=toolbar_actions_bar,
        request_btn=request_btn,
        reload_btn=reload_btn,
        expand_btn=expand_btn,
        collapse_btn=collapse_btn,
        info_btn=info_btn,
        content_host=content_host,
        content_host_layout=content_host_layout,
        loading_label=loading_label,
    )
