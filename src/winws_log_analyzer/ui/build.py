"""Сборка виджетов страницы «Анализ лога winws2» (без логики)."""

from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QHeaderView, QSizePolicy, QWidget
from qfluentwidgets import (
    CaptionLabel,
    CheckBox,
    ComboBox,
    FluentIcon,
    HyperlinkButton,
    ProgressBar,
    PushButton,
    SearchLineEdit,
    StrongBodyLabel,
    TableWidget,
)

from config.urls import WINWS_LOG_ANALYZER_INFO_URL
from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import SettingsCard

CONNECTION_COLUMNS = [
    "Хост",
    "IP",
    "Порт",
    "Proto",
    "L7",
    "Профиль",
    "Пакеты (out/in)",
    "Вердикты",
    "Списки",
]

PACKET_COLUMNS = [
    "#",
    "Напр.",
    "Длина",
    "Флаги",
    "Payload",
    "Профиль",
    "Lua",
    "TLS",
    "Вердикт",
]

PACKETS_PLACEHOLDER_TITLE = "Пакеты: выберите соединение в таблице выше"

_HELP_BUTTON_TEXT = "Как это б#&^ь работает?"


def _build_title_header(page, ui: SimpleNamespace) -> None:
    """Ставит ссылку на инструкцию справа от стандартного заголовка страницы."""
    title_index = page.layout.indexOf(page.title_label)
    if title_index < 0:
        return

    page.layout.removeWidget(page.title_label)
    ui.title_header = QWidget(page.content)
    ui.title_header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    title_layout = QHBoxLayout(ui.title_header)
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(12)
    title_layout.addWidget(page.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
    title_layout.addStretch(1)

    # В тексте QPushButton двойной && рисуется как один обычный символ &.
    ui.help_button = HyperlinkButton(
        FluentIcon.HELP,
        WINWS_LOG_ANALYZER_INFO_URL,
        _HELP_BUTTON_TEXT.replace("&", "&&"),
        ui.title_header,
    )
    ui.help_button.setToolTip("Открыть инструкцию к анализатору логов winws2")
    set_control_accessibility(
        ui.help_button,
        name=_HELP_BUTTON_TEXT,
        description="Открывает в браузере инструкцию к анализатору логов winws2.",
    )
    title_layout.addWidget(ui.help_button, 0, Qt.AlignmentFlag.AlignVCenter)
    page.layout.insertWidget(title_index, ui.title_header)


def _configure_table(table: TableWidget, columns: list[str], *, min_height: int) -> None:
    table.setColumnCount(len(columns))
    table.setRowCount(0)
    table.setHorizontalHeaderLabels(columns)
    try:
        table.setBorderVisible(True)
        table.setBorderRadius(8)
    except Exception:
        pass
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(TableWidget.SelectionMode.SingleSelection)
    table.setMinimumHeight(min_height)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    table.setWordWrap(False)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


def build_winws_log_analyzer_ui(page) -> SimpleNamespace:
    """Создаёт все виджеты страницы и добавляет их в layout страницы."""
    ui = SimpleNamespace()
    _build_title_header(page, ui)

    # --- Одна компактная карточка: источник и фильтры в одной строке ---
    ui.source_card = SettingsCard("", page.content)

    top_row = QHBoxLayout()
    top_row.setSpacing(8)
    ui.open_file_btn = PushButton(FluentIcon.FOLDER, "Открыть файл…")
    set_control_accessibility(
        ui.open_file_btn,
        name="Открыть файл лога",
        description="Выбрать debug-лог winws2 на диске для анализа.",
    )
    top_row.addWidget(ui.open_file_btn)

    ui.recent_combo = ComboBox()
    ui.recent_combo.setMinimumWidth(240)
    ui.recent_combo.setPlaceholderText("Debug-логи winws2 из папки logs/")
    set_control_accessibility(
        ui.recent_combo,
        name="Debug-логи winws2 из папки приложения",
        description="Быстрый выбор недавнего debug-лога winws2 из папки logs.",
    )
    top_row.addWidget(ui.recent_combo, 1)

    top_row.addSpacing(8)

    ui.search_edit = SearchLineEdit()
    ui.search_edit.setPlaceholderText("Фильтр по хосту или IP")
    ui.search_edit.setFixedWidth(220)
    # Не перехватывать drag&drop лог-файла (иначе LineEdit вставит путь как текст).
    ui.search_edit.setAcceptDrops(False)
    set_control_accessibility(
        ui.search_edit,
        name="Фильтр соединений",
        description="Фильтрует таблицу соединений по хосту или IP-адресу.",
    )
    top_row.addWidget(ui.search_edit)

    ui.only_hostname_cb = CheckBox("Только с hostname")
    set_control_accessibility(
        ui.only_hostname_cb,
        name="Только с hostname",
        description="Показывать только соединения с распознанным именем хоста.",
    )
    top_row.addWidget(ui.only_hostname_cb)

    ui.only_affected_cb = CheckBox("Только modified/drop")
    set_control_accessibility(
        ui.only_affected_cb,
        name="Только modified и drop",
        description="Показывать только соединения с изменёнными или отброшенными пакетами.",
    )
    top_row.addWidget(ui.only_affected_cb)
    ui.source_card.add_layout(top_row)

    # Путь и сводка — одной тонкой строкой под контролами.
    info_row = QHBoxLayout()
    info_row.setSpacing(12)
    ui.path_label = CaptionLabel("Файл не выбран — или перетащите лог-файл на страницу")
    # Длинный путь не должен растягивать карточку — лишнее просто обрезается.
    ui.path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    ui.path_label.setMinimumWidth(160)
    info_row.addWidget(ui.path_label, 1)
    info_row.addStretch()
    ui.summary_label = CaptionLabel("")
    ui.summary_label.setVisible(False)
    info_row.addWidget(ui.summary_label)
    ui.source_card.add_layout(info_row)

    ui.progress_bar = ProgressBar()
    ui.progress_bar.setVisible(False)
    ui.source_card.add_widget(ui.progress_bar)

    page.add_widget(ui.source_card)

    # --- Таблица соединений ---
    ui.connections_table = TableWidget()
    _configure_table(ui.connections_table, CONNECTION_COLUMNS, min_height=280)
    set_control_accessibility(
        ui.connections_table,
        name="Таблица соединений",
        description="Выберите строку, чтобы увидеть пакеты соединения.",
    )
    set_state_text(ui.connections_table, "Таблица соединений: лог не загружен")
    header = ui.connections_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for col in range(1, len(CONNECTION_COLUMNS)):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    page.add_widget(ui.connections_table)

    # --- Пакеты выбранного соединения (секция всегда видима: layout не прыгает) ---
    ui.packets_title = StrongBodyLabel(PACKETS_PLACEHOLDER_TITLE)
    page.add_widget(ui.packets_title)
    ui.packets_table = TableWidget()
    _configure_table(ui.packets_table, PACKET_COLUMNS, min_height=200)
    set_control_accessibility(
        ui.packets_table,
        name="Таблица пакетов соединения",
        description="Пакеты выбранного соединения с профилем и вердиктом.",
    )
    packets_header = ui.packets_table.horizontalHeader()
    packets_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
    for col in (0, 1, 2, 3, 4, 5, 6, 8):
        packets_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    page.add_widget(ui.packets_table)

    return ui


__all__ = [
    "build_winws_log_analyzer_ui",
    "CONNECTION_COLUMNS",
    "PACKET_COLUMNS",
    "PACKETS_PLACEHOLDER_TITLE",
]
