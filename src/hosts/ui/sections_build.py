"""Build-helper простых секций Hosts page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QHBoxLayout

from ui.accessibility import set_control_accessibility
from ui.fluent_widgets import SettingsCard, SemanticNotice
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_semantic import get_semantic_palette
from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon, PushButton, StrongBodyLabel, SwitchButton


@dataclass(slots=True)
class HostsInfoNoteWidgets:
    card: SettingsCard
    info_text_label: object


@dataclass(slots=True)
class HostsStatusWidgets:
    card: SettingsCard
    status_dot: QLabel
    status_label: object
    clear_button: object
    open_hosts_button: object


@dataclass(slots=True)
class HostsAdobeWidgets:
    card: SettingsCard
    description_label: object
    title_label: object
    switch: object


def build_hosts_info_note(*, tr_fn) -> HostsInfoNoteWidgets:
    semantic = get_semantic_palette()
    info_card = SettingsCard()

    info_layout = QHBoxLayout()
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(10)

    icon_label = QLabel()
    icon_label.setPixmap(get_cached_qta_pixmap('fa5s.lightbulb', color=semantic.warning, size=20))
    icon_label.setFixedSize(24, 24)
    info_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

    info_text_label = CaptionLabel(
        tr_fn(
            "page.hosts.info.note",
            "Некоторые сервисы (ChatGPT, Spotify и др.) сами блокируют доступ из России — это не блокировка РКН. Решается не через Zapret, а через проксирование: домены направляются через отдельный прокси-сервер в файле hosts.",
        )
    )
    info_text_label.setWordWrap(True)
    info_layout.addWidget(info_text_label, 1)

    info_card.add_layout(info_layout)
    return HostsInfoNoteWidgets(
        card=info_card,
        info_text_label=info_text_label,
    )


def build_hosts_browser_warning(*, tr_fn):
    return SemanticNotice(
        tr_fn(
            "page.hosts.warning.browser_restart",
            "После добавления или удаления доменов необходимо перезапустить браузер, чтобы изменения вступили в силу.",
        ),
        tone="warning",
    )


def build_hosts_status_section(
    *,
    tr_fn,
    active_count: int,
    on_clear_clicked,
    on_open_hosts_file,
) -> HostsStatusWidgets:
    status_card = SettingsCard()
    status_layout = QHBoxLayout()
    status_layout.setContentsMargins(0, 0, 0, 0)
    status_layout.setSpacing(10)

    tokens = get_theme_tokens()
    semantic = get_semantic_palette()

    status_dot = QLabel("●")
    dot_color = semantic.success if active_count > 0 else tokens.fg_faint
    status_dot.setStyleSheet(f"color: {dot_color}; font-size: 12px;")
    status_layout.addWidget(status_dot)

    status_label = BodyLabel(
        tr_fn("page.hosts.status.active_domains", "Активно {count} доменов", count=active_count)
        if active_count > 0
        else tr_fn("page.hosts.status.none_active", "Нет активных")
    )
    status_label.setProperty("tone", "primary")
    status_layout.addWidget(status_label, 1)

    clear_btn = PushButton(
        tr_fn("page.hosts.button.clear", "Очистить"),
        icon=FluentIcon.DELETE,
    )
    clear_btn.clicked.connect(on_clear_clicked)
    set_control_accessibility(
        clear_btn,
        name=tr_fn("page.hosts.button.clear.accessible_name", "Очистить hosts"),
        description=tr_fn(
            "page.hosts.button.clear.accessible_description",
            "Удаляет активные домены из файла hosts.",
        ),
    )
    status_layout.addWidget(clear_btn)

    open_hosts_button = PushButton(
        tr_fn("page.hosts.button.open", "Открыть"),
        icon=FluentIcon.LINK,
    )
    open_hosts_button.clicked.connect(on_open_hosts_file)
    set_control_accessibility(
        open_hosts_button,
        name=tr_fn("page.hosts.button.open.accessible_name", "Открыть файл hosts"),
        description=tr_fn(
            "page.hosts.button.open.accessible_description",
            "Открывает системный файл hosts для просмотра или ручной проверки.",
        ),
    )
    status_layout.addWidget(open_hosts_button)

    status_card.add_layout(status_layout)
    return HostsStatusWidgets(
        card=status_card,
        status_dot=status_dot,
        status_label=status_label,
        clear_button=clear_btn,
        open_hosts_button=open_hosts_button,
    )


def build_hosts_adobe_section(
    *,
    tr_fn,
    adobe_active: bool,
    on_toggle_adobe,
    switch_button_cls=SwitchButton,
) -> HostsAdobeWidgets:
    adobe_card = SettingsCard()

    adobe_description = tr_fn(
        "page.hosts.adobe.description",
        "⚠️ Блокирует серверы проверки активации Adobe. Включите, если у вас установлена пиратская версия.",
    )
    adobe_desc_label = CaptionLabel(adobe_description)
    adobe_desc_label.setWordWrap(True)
    adobe_card.add_widget(adobe_desc_label)

    adobe_layout = QHBoxLayout()
    adobe_layout.setContentsMargins(0, 0, 0, 0)
    adobe_layout.setSpacing(8)

    icon_label = QLabel()
    icon_label.setPixmap(get_cached_qta_pixmap('fa5s.puzzle-piece', color='#ff0000', size=20))
    adobe_layout.addWidget(icon_label)

    adobe_title = tr_fn("page.hosts.adobe.title", "Блокировка Adobe")
    adobe_title_label = StrongBodyLabel(adobe_title)
    adobe_layout.addWidget(adobe_title_label, 1)

    adobe_switch = switch_button_cls()
    adobe_switch.setChecked(adobe_active)
    _update_adobe_switch_accessibility(
        adobe_switch,
        title=adobe_title,
        description=adobe_description,
        checked=adobe_active,
    )
    try:
        adobe_switch.checkedChanged.connect(
            lambda checked: _update_adobe_switch_accessibility(
                adobe_switch,
                title=adobe_title,
                description=adobe_description,
                checked=checked,
            )
        )
    except Exception:
        pass
    adobe_switch.checkedChanged.connect(on_toggle_adobe)
    adobe_layout.addWidget(adobe_switch)

    adobe_card.add_layout(adobe_layout)
    return HostsAdobeWidgets(
        card=adobe_card,
        description_label=adobe_desc_label,
        title_label=adobe_title_label,
        switch=adobe_switch,
    )


def _update_adobe_switch_accessibility(switch, *, title: str, description: str, checked: bool) -> None:
    state = "включено" if bool(checked) else "выключено"
    set_control_accessibility(
        switch,
        name=f"{title}, {state}",
        description=description,
    )
