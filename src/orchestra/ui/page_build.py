"""Build-helper основных карточек Orchestra page."""

from __future__ import annotations

from dataclasses import dataclass
from types import MethodType

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QLabel, QHBoxLayout
from qfluentwidgets import FluentIcon

from ui.pages.base_page import ScrollBlockingTextEdit
from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import set_tooltip


@dataclass(slots=True)
class OrchestraStatusWidgets:
    card: object
    title_label: object
    status_icon: QLabel
    status_label: object
    info_label: object


@dataclass(slots=True)
class OrchestraLogWidgets:
    card: object
    title_label: object
    log_text: object
    filter_label: object
    log_filter_input: object
    log_protocol_filter: object
    clear_filter_btn: object
    clear_log_btn: object
    clear_learned_btn: object


@dataclass(slots=True)
class OrchestraLogHistoryWidgets:
    card: object
    title_label: object
    desc_label: object
    log_history_list: object
    view_log_btn: object
    delete_log_btn: object
    clear_all_logs_btn: object


def _clean_orchestra_status_text(text: object) -> str:
    value = " ".join(str(text or "").strip().split())
    for prefix in ("⏸", "🔄", "✅", "🔓"):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
    return value


def set_orchestra_status_accessibility(status_label, text: object, *, status_icon=None) -> None:
    status_text = _clean_orchestra_status_text(text)
    if not status_text:
        return
    set_state_text(status_label, f"Статус обучения Оркестратора: {status_text}")
    if status_icon is not None:
        set_state_text(status_icon, f"Индикатор обучения Оркестратора: {status_text}")


def build_orchestra_status_card(
    *,
    create_card,
    tr_fn,
    body_label_cls,
    caption_label_cls,
) -> OrchestraStatusWidgets:
    status_card, status_layout, status_title = create_card(
        tr_fn("page.orchestra.training_status", "Статус обучения")
    )

    status_row = QHBoxLayout()
    status_icon = QLabel()
    status_icon.setFixedSize(24, 24)
    status_label = body_label_cls(tr_fn("page.orchestra.status.not_started", "Не запущен"))
    set_orchestra_status_accessibility(status_label, status_label.text(), status_icon=status_icon)
    status_row.addWidget(status_icon)
    status_row.addWidget(status_label)
    status_row.addStretch()
    status_layout.addLayout(status_row)

    info_label = caption_label_cls(
        tr_fn(
            "page.orchestra.status.modes",
            "• IDLE - ожидание соединений\n"
            "• LEARNING - перебирает стратегии\n"
            "• RUNNING - работает на лучших стратегиях\n"
            "• UNLOCKED - переобучение (RST блокировка)",
        )
    )
    status_layout.addWidget(info_label)

    return OrchestraStatusWidgets(
        card=status_card,
        title_label=status_title,
        status_icon=status_icon,
        status_label=status_label,
        info_label=info_label,
    )


def build_orchestra_log_card(
    *,
    create_card,
    tr_fn,
    line_edit_cls,
    combo_cls,
    body_label_cls,
    caption_label_cls,
    transparent_tool_button_cls,
    fluent_push_button_cls,
    on_show_log_context_menu,
    on_apply_log_filter,
    on_clear_log_filter,
    on_clear_log,
    on_clear_learned_clicked,
):
    log_card, log_layout, log_title = create_card(
        tr_fn("page.orchestra.log", "Лог обучения")
    )

    log_text = ScrollBlockingTextEdit()
    log_text.setReadOnly(True)
    log_text.setMinimumHeight(300)
    log_text.setPlaceholderText(
        tr_fn("page.orchestra.log.placeholder", "Логи обучения будут отображаться здесь...")
    )
    set_control_accessibility(
        log_text,
        name=tr_fn("page.orchestra.log.accessible_name", "Лог обучения Оркестратора"),
        description=tr_fn(
            "page.orchestra.log.accessible_description",
            "Показывает строки обучения и события работы Оркестратора.",
        ),
    )
    set_state_text(log_text, "Лог обучения Оркестратора: пока нет записей обучения")
    log_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    log_text.customContextMenuRequested.connect(on_show_log_context_menu)
    log_layout.addWidget(log_text)

    filter_row = QHBoxLayout()

    filter_label = body_label_cls(tr_fn("page.orchestra.filter.label", "Фильтр:"))
    filter_row.addWidget(filter_label)

    log_filter_input = line_edit_cls()
    log_filter_input.setPlaceholderText(
        tr_fn("page.orchestra.filter.domain.placeholder", "Домен (например: youtube.com)")
    )
    set_control_accessibility(
        log_filter_input,
        name=tr_fn("page.orchestra.filter.domain.accessible_name", "Фильтр лога Оркестратора по домену"),
        description=tr_fn(
            "page.orchestra.filter.domain.accessible_description",
            (
                "Введите домен, например example.com, чтобы оставить в логе только подходящие строки. "
                "После ввода перейдите к логу клавишей Tab или нажмите Стрелка вниз."
            ),
        ),
    )
    log_filter_input.textChanged.connect(on_apply_log_filter)
    _wire_filter_arrow_down_to_log(log_filter_input, log_text)
    filter_row.addWidget(log_filter_input, 2)

    log_protocol_filter = combo_cls()
    log_protocol_filter.currentTextChanged.connect(on_apply_log_filter)
    filter_row.addWidget(log_protocol_filter)

    clear_filter_btn = transparent_tool_button_cls()
    set_tooltip(clear_filter_btn, tr_fn("page.orchestra.filter.clear.tooltip", "Сбросить фильтр"))
    set_control_accessibility(
        clear_filter_btn,
        name=tr_fn("page.orchestra.filter.clear.accessible_name", "Сбросить фильтр лога Оркестратора"),
        description=tr_fn(
            "page.orchestra.filter.clear.accessible_description",
            "Очищает фильтр домена и протокола в логе Оркестратора.",
        ),
    )
    clear_filter_btn.setFixedSize(28, 28)
    clear_filter_btn.clicked.connect(on_clear_log_filter)
    filter_row.addWidget(clear_filter_btn)

    log_layout.addLayout(filter_row)

    btn_row1 = QHBoxLayout()

    clear_log_btn = fluent_push_button_cls()
    clear_log_btn.setText(tr_fn("page.orchestra.button.clear_log", "Очистить лог"))
    clear_log_btn.setIcon(FluentIcon.BROOM)
    clear_log_btn.setIconSize(QSize(16, 16))
    clear_log_btn.setFixedHeight(32)
    clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    set_control_accessibility(
        clear_log_btn,
        name=tr_fn("page.orchestra.button.clear_log.accessible_name", "Очистить лог обучения Оркестратора"),
        description=tr_fn(
            "page.orchestra.button.clear_log.accessible_description",
            "Удаляет видимые строки текущего лога обучения.",
        ),
    )
    clear_log_btn.clicked.connect(on_clear_log)
    btn_row1.addWidget(clear_log_btn)

    clear_learned_btn = fluent_push_button_cls()
    clear_learned_btn.setText(
        tr_fn("page.orchestra.button.clear_learning", "Сбросить обучение")
    )
    clear_learned_btn.setIconSize(QSize(16, 16))
    clear_learned_btn.setFixedHeight(32)
    clear_learned_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    set_control_accessibility(
        clear_learned_btn,
        name=tr_fn("page.orchestra.button.clear_learning.accessible_name", "Сбросить данные обучения Оркестратора"),
        description=tr_fn(
            "page.orchestra.button.clear_learning.accessible_description",
            "Очищает сохранённые результаты обучения стратегий.",
        ),
    )
    clear_learned_btn.clicked.connect(on_clear_learned_clicked)
    btn_row1.addWidget(clear_learned_btn)

    btn_row1.addStretch()
    log_layout.addLayout(btn_row1)

    return OrchestraLogWidgets(
        card=log_card,
        title_label=log_title,
        log_text=log_text,
        filter_label=filter_label,
        log_filter_input=log_filter_input,
        log_protocol_filter=log_protocol_filter,
        clear_filter_btn=clear_filter_btn,
        clear_log_btn=clear_log_btn,
        clear_learned_btn=clear_learned_btn,
    )


def _wire_filter_arrow_down_to_log(log_filter_input, log_text) -> None:
    if log_filter_input is None or log_text is None:
        return
    if bool(getattr(log_filter_input, "_orchestra_log_filter_keyboard_focus", False)):
        return
    original_key_press = getattr(log_filter_input, "keyPressEvent", None)

    def _filter_key_press(self, event):
        if event.key() == Qt.Key.Key_Down:
            log_text.setFocus(Qt.FocusReason.OtherFocusReason)
            event.accept()
            return
        if callable(original_key_press):
            return original_key_press(event)
        return None

    log_filter_input.keyPressEvent = MethodType(_filter_key_press, log_filter_input)
    log_filter_input._orchestra_log_filter_keyboard_focus = True


def build_orchestra_log_history_card(
    *,
    create_card,
    tr_fn,
    max_logs: int,
    list_widget_cls,
    caption_label_cls,
    fluent_push_button_cls,
    on_view_log_history,
    on_delete_log_history,
    on_clear_all_log_history,
):
    log_history_card, log_history_layout, log_history_title = create_card(
        tr_fn("page.orchestra.log_history.title", "История логов (макс. {max_logs})", max_logs=max_logs)
    )

    log_history_desc = caption_label_cls(
        tr_fn(
            "page.orchestra.log_history.desc",
            "Каждый запуск оркестратора создаёт новый лог с уникальным ID. Старые логи автоматически удаляются.",
        )
    )
    log_history_desc.setWordWrap(True)
    set_control_accessibility(
        log_history_desc,
        name=tr_fn("page.orchestra.log_history.desc.accessible_name", "Описание истории логов Оркестратора"),
        description=tr_fn(
            "page.orchestra.log_history.desc.accessible_description",
            "Поясняет, что каждый запуск Оркестратора создаёт отдельный лог.",
        ),
    )
    log_history_layout.addWidget(log_history_desc)

    log_history_list = list_widget_cls()
    log_history_list.setMaximumHeight(150)
    set_control_accessibility(
        log_history_list,
        name=tr_fn("page.orchestra.log_history.list.accessible_name", "История логов Оркестратора"),
        description=tr_fn(
            "page.orchestra.log_history.list.accessible_description",
            "Выберите лог стрелками и нажмите Просмотреть или Удалить.",
        ),
    )
    set_state_text(log_history_list, "История логов Оркестратора: список пока не загружен")
    log_history_list.itemDoubleClicked.connect(on_view_log_history)
    log_history_layout.addWidget(log_history_list)

    log_history_buttons = QHBoxLayout()

    view_log_btn = fluent_push_button_cls()
    view_log_btn.setText(tr_fn("page.orchestra.button.view_log", "Просмотреть"))
    view_log_btn.setIconSize(QSize(16, 16))
    view_log_btn.setFixedHeight(32)
    set_control_accessibility(
        view_log_btn,
        name=tr_fn("page.orchestra.button.view_log.accessible_name", "Просмотреть выбранный лог Оркестратора"),
        description=tr_fn(
            "page.orchestra.button.view_log.accessible_description",
            "Открывает выбранный сохранённый лог Оркестратора.",
        ),
    )
    view_log_btn.clicked.connect(on_view_log_history)
    log_history_buttons.addWidget(view_log_btn)

    delete_log_btn = fluent_push_button_cls()
    delete_log_btn.setText(tr_fn("page.orchestra.button.delete_log", "Удалить"))
    delete_log_btn.setIconSize(QSize(16, 16))
    delete_log_btn.setFixedHeight(32)
    set_control_accessibility(
        delete_log_btn,
        name=tr_fn("page.orchestra.button.delete_log.accessible_name", "Удалить выбранный лог Оркестратора"),
        description=tr_fn(
            "page.orchestra.button.delete_log.accessible_description",
            "Удаляет выбранный сохранённый лог Оркестратора.",
        ),
    )
    delete_log_btn.clicked.connect(on_delete_log_history)
    log_history_buttons.addWidget(delete_log_btn)

    log_history_buttons.addStretch()

    clear_all_logs_btn = fluent_push_button_cls()
    clear_all_logs_btn.setText(tr_fn("page.orchestra.button.clear_all_logs", "Очистить все"))
    clear_all_logs_btn.setIconSize(QSize(16, 16))
    clear_all_logs_btn.setFixedHeight(32)
    clear_all_logs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    set_control_accessibility(
        clear_all_logs_btn,
        name=tr_fn("page.orchestra.button.clear_all_logs.accessible_name", "Очистить всю историю логов Оркестратора"),
        description=tr_fn(
            "page.orchestra.button.clear_all_logs.accessible_description",
            "Удаляет все сохранённые логи Оркестратора.",
        ),
    )
    clear_all_logs_btn.clicked.connect(on_clear_all_log_history)
    log_history_buttons.addWidget(clear_all_logs_btn)

    log_history_layout.addLayout(log_history_buttons)

    return OrchestraLogHistoryWidgets(
        card=log_history_card,
        title_label=log_history_title,
        desc_label=log_history_desc,
        log_history_list=log_history_list,
        view_log_btn=view_log_btn,
        delete_log_btn=delete_log_btn,
        clear_all_logs_btn=clear_all_logs_btn,
    )
