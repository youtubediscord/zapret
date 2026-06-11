"""Build-helper shell и простых панелей Telegram Proxy page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget
from qfluentwidgets import FluentIcon

from ui.accessibility import set_control_accessibility, set_state_text
from ui.segmented_accessibility import set_segmented_items_accessibility
from ui.pages.base_page import ScrollBlockingPlainTextEdit
from ui.log_limits import (
    TELEGRAM_PROXY_DIAG_VIEW_MAX_LINES,
    TELEGRAM_PROXY_LOG_VIEW_MAX_LINES,
    apply_text_line_limit,
)


@dataclass(slots=True)
class TelegramProxyShellWidgets:
    pivot: object
    stacked: QStackedWidget
    settings_panel: QWidget
    settings_layout: QVBoxLayout
    logs_panel: QWidget
    logs_layout: QVBoxLayout
    diag_panel: QWidget
    diag_layout: QVBoxLayout


@dataclass(slots=True)
class TelegramProxyLogsWidgets:
    btn_copy_logs: object
    btn_open_log_file: object
    btn_clear_logs: object
    log_edit: object


@dataclass(slots=True)
class TelegramProxyDiagWidgets:
    diag_desc_label: object
    btn_run_diag: object
    btn_copy_diag: object
    diag_edit: object


def update_telegram_proxy_pivot_accessibility(pivot, *, current: object | None = None) -> None:
    if pivot is None:
        return
    labels = {
        "settings": "Настройки",
        "logs": "Логи",
        "diag": "Диагностика",
    }
    key = str(current or "").strip()
    if not key:
        try:
            key = str(pivot.currentItem() or "").strip()
        except Exception:
            key = ""
    selected = labels.get(key, key or "Настройки")
    state = f"Раздел Telegram Proxy, выбрано: {selected}"
    set_state_text(pivot, state)
    set_control_accessibility(
        pivot,
        name=state,
        description="Выберите раздел Telegram Proxy: Настройки, Логи или Диагностика.",
    )
    set_segmented_items_accessibility(pivot, name="Раздел Telegram Proxy")


def build_telegram_proxy_shell(*, segmented_widget_cls, parent, on_switch_tab) -> TelegramProxyShellWidgets:
    pivot = segmented_widget_cls(parent)
    stacked = QStackedWidget(parent)

    settings_panel = QWidget(stacked)
    settings_layout = QVBoxLayout(settings_panel)
    settings_layout.setContentsMargins(0, 0, 0, 0)
    settings_layout.setSpacing(12)
    stacked.addWidget(settings_panel)

    logs_panel = QWidget(stacked)
    logs_layout = QVBoxLayout(logs_panel)
    logs_layout.setContentsMargins(0, 0, 0, 0)
    logs_layout.setSpacing(8)
    stacked.addWidget(logs_panel)

    diag_panel = QWidget(stacked)
    diag_layout = QVBoxLayout(diag_panel)
    diag_layout.setContentsMargins(0, 0, 0, 0)
    diag_layout.setSpacing(8)
    stacked.addWidget(diag_panel)

    pivot.addItem("settings", "Настройки", lambda: on_switch_tab(0))
    pivot.addItem("logs", "Логи", lambda: on_switch_tab(1))
    pivot.addItem("diag", "Диагностика", lambda: on_switch_tab(2))
    pivot.setCurrentItem("settings")
    update_telegram_proxy_pivot_accessibility(pivot, current="settings")
    pivot.currentItemChanged.connect(
        lambda item: update_telegram_proxy_pivot_accessibility(pivot, current=item)
    )

    return TelegramProxyShellWidgets(
        pivot=pivot,
        stacked=stacked,
        settings_panel=settings_panel,
        settings_layout=settings_layout,
        logs_panel=logs_panel,
        logs_layout=logs_layout,
        diag_panel=diag_panel,
        diag_layout=diag_layout,
    )


def build_telegram_proxy_logs_panel(
    layout: QVBoxLayout,
    *,
    push_button_cls,
    on_copy_all_logs,
    on_open_log_file,
    on_clear_logs,
) -> TelegramProxyLogsWidgets:
    toolbar = QHBoxLayout()
    toolbar.setSpacing(8)

    btn_copy_logs = push_button_cls("Копировать все", icon=FluentIcon.COPY)
    set_control_accessibility(
        btn_copy_logs,
        name="Копировать лог Telegram Proxy",
        description="Копирует весь лог Telegram Proxy в буфер обмена.",
    )
    btn_copy_logs.clicked.connect(on_copy_all_logs)
    toolbar.addWidget(btn_copy_logs)

    btn_open_log_file = push_button_cls("Открыть файл лога", icon=FluentIcon.DOCUMENT)
    set_control_accessibility(
        btn_open_log_file,
        name="Открыть файл лога Telegram Proxy",
        description="Открывает файл с полным логом Telegram Proxy.",
    )
    btn_open_log_file.clicked.connect(on_open_log_file)
    toolbar.addWidget(btn_open_log_file)

    btn_clear_logs = push_button_cls("Очистить", icon=FluentIcon.ERASE_TOOL)
    set_control_accessibility(
        btn_clear_logs,
        name="Очистить лог Telegram Proxy",
        description="Очищает видимый лог Telegram Proxy на этой странице.",
    )
    btn_clear_logs.clicked.connect(on_clear_logs)
    toolbar.addWidget(btn_clear_logs)

    toolbar.addStretch()
    layout.addLayout(toolbar)

    log_edit = ScrollBlockingPlainTextEdit()
    log_edit.setReadOnly(True)
    log_edit.setPlaceholderText("Лог подключений появится здесь...")
    set_control_accessibility(
        log_edit,
        name="Лог Telegram Proxy",
        description="Показывает события подключений и работы Telegram Proxy.",
    )
    set_state_text(log_edit, "Лог Telegram Proxy: пока нет событий подключений")
    apply_text_line_limit(log_edit, TELEGRAM_PROXY_LOG_VIEW_MAX_LINES)
    layout.addWidget(log_edit)

    return TelegramProxyLogsWidgets(
        btn_copy_logs=btn_copy_logs,
        btn_open_log_file=btn_open_log_file,
        btn_clear_logs=btn_clear_logs,
        log_edit=log_edit,
    )


def build_telegram_proxy_diag_panel(
    layout: QVBoxLayout,
    *,
    caption_label_cls,
    primary_push_button_cls,
    push_button_cls,
    on_run_diagnostics,
    on_copy_diag,
) -> TelegramProxyDiagWidgets:
    desc = caption_label_cls(
        "Проверка соединений к Telegram DC, WSS relay эндпоинтов (kws1-kws5), "
        "SOCKS5 прокси и определение типа блокировки."
    )
    desc.setWordWrap(True)
    set_control_accessibility(
        desc,
        name="Описание диагностики Telegram Proxy",
        description=desc.text(),
    )
    layout.addWidget(desc)

    toolbar = QHBoxLayout()
    toolbar.setSpacing(8)

    btn_run_diag = primary_push_button_cls("Запустить диагностику", icon=FluentIcon.DEVELOPER_TOOLS)
    set_control_accessibility(
        btn_run_diag,
        name="Запустить диагностику Telegram Proxy",
        description="Проверяет соединения к Telegram DC, WSS relay, SOCKS5 прокси и тип блокировки.",
    )
    btn_run_diag.clicked.connect(on_run_diagnostics)
    toolbar.addWidget(btn_run_diag)

    btn_copy_diag = push_button_cls("Копировать результат", icon=FluentIcon.COPY)
    set_control_accessibility(
        btn_copy_diag,
        name="Копировать результат диагностики Telegram Proxy",
        description="Копирует результат диагностики Telegram Proxy в буфер обмена.",
    )
    btn_copy_diag.clicked.connect(on_copy_diag)
    toolbar.addWidget(btn_copy_diag)

    toolbar.addStretch()
    layout.addLayout(toolbar)

    diag_edit = ScrollBlockingPlainTextEdit()
    diag_edit.setReadOnly(True)
    diag_edit.setPlaceholderText("Нажмите 'Запустить диагностику'...")
    set_control_accessibility(
        diag_edit,
        name="Результат диагностики Telegram Proxy",
        description="Показывает подробный результат диагностики Telegram Proxy.",
    )
    set_state_text(diag_edit, "Результат диагностики Telegram Proxy: диагностика пока не запускалась")
    apply_text_line_limit(diag_edit, TELEGRAM_PROXY_DIAG_VIEW_MAX_LINES)
    layout.addWidget(diag_edit)

    return TelegramProxyDiagWidgets(
        diag_desc_label=desc,
        btn_run_diag=btn_run_diag,
        btn_copy_diag=btn_copy_diag,
        diag_edit=diag_edit,
    )
