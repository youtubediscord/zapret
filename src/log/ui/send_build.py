"""Build-helper send/support вкладки для страницы логов."""

from __future__ import annotations

from dataclasses import dataclass

from qfluentwidgets import FluentIcon

from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import set_tooltip
from ui.theme import get_cached_qta_pixmap


def apply_logs_send_text_accessibility(*, desc_label, info_label, tr_catalog_fn, ui_language: str) -> None:
    """Обновляет текст для диктора у описаний вкладки поддержки."""

    if desc_label is not None:
        desc_name = tr_catalog_fn(
            "page.logs.send.accessibility.description.name",
            language=ui_language,
            default="Описание подготовки обращения",
        )
        try:
            desc_text = str(desc_label.text() or "").strip()
        except Exception:
            desc_text = ""
        set_control_accessibility(desc_label, name=desc_name, description=desc_text)
        if desc_text:
            set_state_text(desc_label, f"{desc_name}: {desc_text}")

    if info_label is not None:
        info_name = tr_catalog_fn(
            "page.logs.send.accessibility.info.name",
            language=ui_language,
            default="Что будет подготовлено",
        )
        try:
            info_text = str(info_label.text() or "").strip()
        except Exception:
            info_text = ""
        set_control_accessibility(info_label, name=info_name, description=info_text)
        if info_text:
            set_state_text(info_label, f"{info_name}: {info_text}")


@dataclass(slots=True)
class LogsSendTabWidgets:
    send_card: object
    orchestra_mode_container: object
    orchestra_icon_label: object
    orchestra_text_label: object
    info_icon_label: object
    send_desc_label: object
    send_info_label: object
    send_status_label: object
    send_actions_title: object
    send_actions_bar: object
    send_log_btn: object
    open_logs_folder_btn: object


def build_logs_send_tab(
    *,
    parent_layout,
    ui_language: str,
    tr_catalog_fn,
    settings_card_cls,
    qwidget_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    qlabel_cls,
    body_label_cls,
    caption_label_cls,
    strong_body_label_cls,
    push_button_cls,
    quick_actions_bar_cls,
    qta_module,
    get_theme_tokens_fn,
    on_prepare_support,
    on_open_folder,
) -> LogsSendTabWidgets:
    tokens = get_theme_tokens_fn()

    send_card = settings_card_cls(
        tr_catalog_fn("page.logs.send.card.title", language=ui_language, default="Поддержка через GitHub Discussions")
    )
    send_layout = qvbox_layout_cls()
    send_layout.setSpacing(16)

    orchestra_mode_container = qwidget_cls()
    set_control_accessibility(
        orchestra_mode_container,
        name=tr_catalog_fn(
            "page.logs.send.accessibility.orchestra.name",
            language=ui_language,
            default="Подсказка для режима оркестратора",
        ),
        description=tr_catalog_fn(
            "page.logs.send.accessibility.orchestra.description",
            language=ui_language,
            default="В режиме оркестратора нужно проверять основной лог и файл orchestra.",
        ),
    )
    orchestra_layout = qhbox_layout_cls(orchestra_mode_container)
    orchestra_layout.setContentsMargins(12, 8, 12, 8)
    orchestra_layout.setSpacing(8)

    orchestra_icon = qlabel_cls()
    try:
        from qfluentwidgets import isDarkTheme as _is_dark_theme

        orchestra_color = "#a855f7" if _is_dark_theme() else "#7c3aed"
    except Exception:
        orchestra_color = "#a855f7"
    orchestra_icon.setPixmap(get_cached_qta_pixmap("fa5s.brain", color=orchestra_color, size=16))
    orchestra_layout.addWidget(orchestra_icon)

    orchestra_text = body_label_cls(
        tr_catalog_fn(
            "page.logs.send.orchestra.active",
            language=ui_language,
            default="В режиме оркестратора проверьте основной лог и файл orchestra_*.log",
        )
    )
    orchestra_text.setStyleSheet(
        f"color: {orchestra_color}; font-size: 12px; font-weight: 600; background: transparent;"
    )
    orchestra_layout.addWidget(orchestra_text)
    orchestra_layout.addStretch()

    orchestra_bg = "rgba(124, 58, 237, 0.12)" if orchestra_color == "#7c3aed" else "rgba(168, 85, 247, 0.15)"
    orchestra_mode_container.setStyleSheet(
        "QWidget {"
        f" background-color: {orchestra_bg};"
        " border-radius: 8px;"
        " }"
    )
    orchestra_mode_container.setVisible(False)
    send_layout.addWidget(orchestra_mode_container)

    send_desc_label = body_label_cls(
        tr_catalog_fn(
            "page.logs.send.desc",
            language=ui_language,
            default="Нажмите кнопку, чтобы собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
        )
    )
    send_desc_label.setWordWrap(True)
    send_layout.addWidget(send_desc_label)

    info_container = qwidget_cls()
    info_layout = qhbox_layout_cls(info_container)
    info_layout.setContentsMargins(0, 8, 0, 8)

    info_icon = qlabel_cls()
    info_layout.addWidget(info_icon)

    send_info_label = caption_label_cls(
        tr_catalog_fn(
            "page.logs.send.info",
            language=ui_language,
            default="Будет создан архив в папке logs/support_bundles. Шаблон обращения автоматически попадёт в буфер обмена.",
        )
    )
    send_info_label.setWordWrap(True)
    apply_logs_send_text_accessibility(
        desc_label=send_desc_label,
        info_label=send_info_label,
        tr_catalog_fn=tr_catalog_fn,
        ui_language=ui_language,
    )
    info_layout.addWidget(send_info_label, 1)
    send_layout.addWidget(info_container)

    send_status_label = caption_label_cls()
    set_control_accessibility(
        send_status_label,
        name=tr_catalog_fn(
            "page.logs.send.accessibility.status.name",
            language=ui_language,
            default="Статус подготовки обращения",
        ),
        description=tr_catalog_fn(
            "page.logs.send.accessibility.status.description",
            language=ui_language,
            default="Здесь показывается результат подготовки обращения в поддержку.",
        ),
    )
    set_state_text(
        send_status_label,
        tr_catalog_fn(
            "page.logs.send.accessibility.status.initial_state",
            language=ui_language,
            default="Статус подготовки обращения: пока обращение не подготовлено",
        ),
    )
    send_layout.addWidget(send_status_label)

    send_card.add_layout(send_layout)
    parent_layout.addWidget(send_card)

    send_actions_title = strong_body_label_cls(
        tr_catalog_fn("page.logs.send.actions.title", language=ui_language, default="Действия")
    )
    parent_layout.addWidget(send_actions_title)

    send_actions_bar = quick_actions_bar_cls(send_card)

    send_log_btn = push_button_cls(
        tr_catalog_fn("page.logs.send.button.send", language=ui_language, default="Подготовить обращение"),
        icon=FluentIcon.GITHUB,
    )
    send_action_name = tr_catalog_fn(
        "page.logs.send.accessibility.prepare.name",
        language=ui_language,
        default="Подготовить обращение в поддержку",
    )
    send_action_description = tr_catalog_fn(
        "page.logs.send.action.send.description",
        language=ui_language,
        default="Собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
    )
    set_tooltip(
        send_log_btn,
        send_action_description,
    )
    set_control_accessibility(
        send_log_btn,
        name=send_action_name,
        description=send_action_description,
    )
    set_state_text(send_log_btn, send_action_name)
    send_log_btn.clicked.connect(on_prepare_support)
    send_actions_bar.add_button(send_log_btn)

    open_logs_folder_btn = push_button_cls(
        tr_catalog_fn("page.logs.button.folder", language=ui_language, default="Папка"),
        icon=FluentIcon.FOLDER,
    )
    folder_action_name = tr_catalog_fn(
        "page.logs.send.accessibility.folder.name",
        language=ui_language,
        default="Открыть папку логов и обращений",
    )
    folder_action_description = tr_catalog_fn(
        "page.logs.send.action.folder.description",
        language=ui_language,
        default="Открыть папку logs, где лежат логи и подготовленные support bundles.",
    )
    set_tooltip(
        open_logs_folder_btn,
        folder_action_description,
    )
    set_control_accessibility(
        open_logs_folder_btn,
        name=folder_action_name,
        description=folder_action_description,
    )
    set_state_text(open_logs_folder_btn, folder_action_name)
    open_logs_folder_btn.clicked.connect(on_open_folder)
    send_actions_bar.add_button(open_logs_folder_btn)

    parent_layout.addWidget(send_actions_bar)
    parent_layout.addStretch()

    return LogsSendTabWidgets(
        send_card=send_card,
        orchestra_mode_container=orchestra_mode_container,
        orchestra_icon_label=orchestra_icon,
        orchestra_text_label=orchestra_text,
        info_icon_label=info_icon,
        send_desc_label=send_desc_label,
        send_info_label=send_info_label,
        send_status_label=send_status_label,
        send_actions_title=send_actions_title,
        send_actions_bar=send_actions_bar,
        send_log_btn=send_log_btn,
        open_logs_folder_btn=open_logs_folder_btn,
    )
