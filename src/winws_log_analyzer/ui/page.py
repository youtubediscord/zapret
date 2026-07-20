"""Страница «Анализ лога winws2»: выбор debug-лога и таблица соединений."""

from __future__ import annotations

import glob
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog, QTableWidgetItem

from config.runtime_layout import APPLICATION_PATHS
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.pages.base_page import BasePage

from ..filters import filter_connections
from ..models import (
    VERDICT_DROP,
    VERDICT_MODIFIED,
    VERDICT_UNMODIFIED,
    ConnectionRecord,
    WinwsLogParseResult,
)
from ..worker import WinwsLogParseWorker
from .build import PACKETS_PLACEHOLDER_TITLE, build_winws_log_analyzer_ui

LOGS_FOLDER = str(APPLICATION_PATHS.logs_dir)

# Цвета вердиктов — те же, что у статусов blockcheck.
_VERDICT_COLORS = {
    VERDICT_UNMODIFIED: QColor("#52c477"),
    VERDICT_MODIFIED: QColor("#e0a854"),
    VERDICT_DROP: QColor("#e05454"),
}
_VERDICT_TITLES = {
    VERDICT_UNMODIFIED: "ok",
    VERDICT_MODIFIED: "mod",
    VERDICT_DROP: "drop",
    "": "нет",
}

# Только логи с выводом winws2: <preset>_debug.log (стабильное имя по пресету,
# см. _build_stable_debug_log_file), устаревшие zapret_winws2_debug_*.log и
# raw-вывод оркестратора orchestra_*.log. Остальное (zapret_log_*.txt — логи GUI,
# tg_proxy.log, crashes.log) — другой формат, парсеру не подходит.
_RECENT_LOG_PATTERNS = ("*_debug.log", "zapret_winws2_debug_*.log", "orchestra_*.log")
_RECENT_LOG_LIMIT = 20

_DROP_ALLOWED_EXTENSIONS = (".log", ".txt")


class WinwsLogAnalyzerPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "Анализ лога winws2",
            "Разбор debug-лога: соединения, протоколы, профили и вердикты",
            parent,
            title_key="page.winws_log_analyzer.title",
            subtitle_key="page.winws_log_analyzer.subtitle",
        )
        self._runtime = OneShotWorkerRuntime()
        self._result: WinwsLogParseResult | None = None
        self._filtered: list[ConnectionRecord] = []
        self._ui = build_winws_log_analyzer_ui(self)
        # Debounce текстового фильтра: не пересобирать таблицу на каждый символ.
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._refresh_connections_table)
        self._connect_signals()
        self.setAcceptDrops(True)
        self._apply_page_theme(force=True)

    # ------------------------------------------------------------------ setup

    def _connect_signals(self) -> None:
        ui = self._ui
        ui.open_file_btn.clicked.connect(self._open_file_dialog)
        ui.recent_combo.activated.connect(self._on_recent_selected)
        ui.search_edit.textChanged.connect(lambda _text: self._filter_timer.start())
        ui.only_hostname_cb.toggled.connect(lambda _on: self._refresh_connections_table())
        ui.only_affected_cb.toggled.connect(lambda _on: self._refresh_connections_table())
        ui.connections_table.itemSelectionChanged.connect(self._on_connection_selected)

    def on_page_activated(self) -> None:
        super().on_page_activated()
        self._refresh_recent_combo()

    def cleanup(self) -> None:
        super().cleanup()
        self._filter_timer.stop()
        self._runtime.stop(blocking=False)

    # ------------------------------------------------------------ drag&drop

    @staticmethod
    def _dropped_log_path(mime_data) -> str:
        """Путь локального файла из перетаскивания, если он похож на текстовый лог."""
        if mime_data is None or not mime_data.hasUrls():
            return ""
        for url in mime_data.urls():
            path = url.toLocalFile()
            if not path or not os.path.isfile(path):
                continue
            if path.lower().endswith(_DROP_ALLOWED_EXTENSIONS):
                return path
        return ""

    def dragEnterEvent(self, event):  # noqa: N802 (Qt override)
        if self._dropped_log_path(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802 (Qt override)
        path = self._dropped_log_path(event.mimeData())
        if not path:
            event.ignore()
            return
        event.acceptProposedAction()
        self._start_parse(path)

    # ---------------------------------------------------------- выбор файла

    def _refresh_recent_combo(self) -> None:
        combo = self._ui.recent_combo
        current_path = combo.currentData()
        files: list[str] = []
        for pattern in _RECENT_LOG_PATTERNS:
            files.extend(glob.glob(os.path.join(LOGS_FOLDER, pattern)))
        files = list(dict.fromkeys(files))  # паттерны пересекаются
        files.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
        files = files[:_RECENT_LOG_LIMIT]
        combo.blockSignals(True)
        combo.clear()
        for path in files:
            combo.addItem(os.path.basename(path), userData=path)
        if current_path:
            index = combo.findData(current_path)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _open_file_dialog(self) -> None:
        start_dir = LOGS_FOLDER if os.path.isdir(LOGS_FOLDER) else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать debug-лог winws2",
            start_dir,
            "Файлы логов (*.log *.txt);;Все файлы (*.*)",
        )
        if not path:
            return
        self._start_parse(path)

    def _on_recent_selected(self, index: int) -> None:
        path = self._ui.recent_combo.itemData(index)
        if path:
            self._start_parse(path)

    # -------------------------------------------------------------- парсинг

    def _start_parse(self, path: str) -> None:
        ui = self._ui
        self._runtime.stop(blocking=False)
        ui.path_label.setText(path)
        ui.path_label.setToolTip(path)
        ui.summary_label.setVisible(False)
        ui.progress_bar.setValue(0)
        ui.progress_bar.setVisible(True)

        def _bind_worker(worker) -> None:
            worker.progress.connect(self._on_parse_progress)

        self._runtime.start_qobject_worker(
            parent=self,
            worker_factory=lambda _req: WinwsLogParseWorker(file_path=path),
            on_loaded=self._on_parse_loaded,
            on_failed=self._on_parse_failed,
            bind_worker=_bind_worker,
        )

    def _on_parse_progress(self, bytes_read: int, bytes_total: int) -> None:
        if bytes_total > 0:
            self._ui.progress_bar.setValue(min(100, int(bytes_read * 100 / bytes_total)))

    def _on_parse_loaded(self, request_id: int, result: WinwsLogParseResult) -> None:
        if not self._runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        self._result = result
        self._ui.progress_bar.setVisible(False)
        self._show_summary(result)
        self._refresh_connections_table()

    def _on_parse_failed(self, request_id: int, message: str) -> None:
        if not self._runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        self._ui.progress_bar.setVisible(False)
        self._ui.summary_label.setText(f"Ошибка чтения лога: {message}")
        self._ui.summary_label.setVisible(True)

    def _show_summary(self, result: WinwsLogParseResult) -> None:
        parts = [
            f"Пакетов: {result.packets_total}",
            f"Соединений: {len(result.connections)}",
            f"Совпадений hostlist/ipset: {result.positive_checks_total}",
        ]
        if result.profiles:
            parts.append(f"Профилей: {len(result.profiles)}")
        if result.unparsed_blocks:
            parts.append(f"Нераспознанных блоков: {result.unparsed_blocks}")
        if result.unrecognized_packet_lines:
            parts.append(f"Нераспознанных packet-строк: {result.unrecognized_packet_lines}")
        if result.packets_total == 0:
            parts = ["В файле не найдено пакетных блоков — это debug-лог winws2?"]
        self._ui.summary_label.setText(" · ".join(parts))
        self._ui.summary_label.setVisible(True)

    # -------------------------------------------------------------- таблицы

    def _refresh_connections_table(self) -> None:
        ui = self._ui
        connections = self._result.connections if self._result is not None else []
        self._filtered = filter_connections(
            connections,
            text=ui.search_edit.text(),
            only_with_hostname=ui.only_hostname_cb.isChecked(),
            only_affected=ui.only_affected_cb.isChecked(),
        )
        table = ui.connections_table
        table.setUpdatesEnabled(False)
        try:
            table.clearSelection()
            table.setRowCount(len(self._filtered))
            for row, conn in enumerate(self._filtered):
                self._set_connection_row(table, row, conn)
        finally:
            table.setUpdatesEnabled(True)
        self._show_packets(None)

    def _set_connection_row(self, table, row: int, conn: ConnectionRecord) -> None:
        profile = ", ".join(
            f"{pid} ({name})" if name else str(pid)
            for pid, name in zip(conn.profile_ids, conn.profile_names)
        )
        verdicts = " · ".join(
            f"{count} {_VERDICT_TITLES.get(verdict, verdict)}"
            for verdict, count in sorted(conn.verdict_counts.items())
        )
        values = [
            conn.hostname or "—",
            conn.remote_ip,
            str(conn.remote_port),
            conn.proto,
            conn.l7proto or "—",
            profile or "—",
            f"{conn.packets_total} ({conn.packets_out}/{conn.packets_in})",
            verdicts or "—",
            ", ".join(conn.positive_lists) or "—",
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, row)
            if col == 7:
                item.setForeground(self._verdict_color(conn))
            if col == 8 and conn.positive_lists:
                item.setForeground(_VERDICT_COLORS[VERDICT_MODIFIED])
            table.setItem(row, col, item)

    @staticmethod
    def _verdict_color(conn: ConnectionRecord) -> QColor:
        if conn.verdict_counts.get(VERDICT_DROP):
            return _VERDICT_COLORS[VERDICT_DROP]
        if conn.verdict_counts.get(VERDICT_MODIFIED):
            return _VERDICT_COLORS[VERDICT_MODIFIED]
        return _VERDICT_COLORS[VERDICT_UNMODIFIED]

    def _on_connection_selected(self) -> None:
        rows = {item.row() for item in self._ui.connections_table.selectedItems()}
        if len(rows) != 1:
            self._show_packets(None)
            return
        row = rows.pop()
        if 0 <= row < len(self._filtered):
            self._show_packets(self._filtered[row])

    def _show_packets(self, conn: ConnectionRecord | None) -> None:
        # Секция пакетов всегда видима — layout не прыгает при выборе строки.
        ui = self._ui
        if conn is None:
            ui.packets_title.setText(PACKETS_PLACEHOLDER_TITLE)
            ui.packets_table.setRowCount(0)
            return
        title = conn.hostname or f"{conn.remote_ip}:{conn.remote_port}"
        suffix = f" (показаны первые {len(conn.packets)})" if conn.packets_truncated else ""
        ui.packets_title.setText(f"Пакеты соединения {title} — {conn.packets_total}{suffix}")
        table = ui.packets_table
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(conn.packets))
            for row, pkt in enumerate(conn.packets):
                profile = f"{pkt.profile_id}" if pkt.profile_id is not None else "—"
                if pkt.profile_name:
                    profile += f" ({pkt.profile_name})"
                if pkt.profile_cached:
                    profile += " *"
                values = [
                    str(pkt.packet_id),
                    "→ out" if pkt.direction == "out" else "← in",
                    str(pkt.length),
                    pkt.tcp_flags or "—",
                    pkt.payload_type or "—",
                    profile,
                    ", ".join(pkt.lua_applied) or "—",
                    "; ".join(pkt.tls_details) or "—",
                    _VERDICT_TITLES.get(pkt.verdict, pkt.verdict),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == len(values) - 1:
                        color = _VERDICT_COLORS.get(pkt.verdict)
                        if color is not None:
                            item.setForeground(color)
                    table.setItem(row, col, item)
        finally:
            table.setUpdatesEnabled(True)


__all__ = ["WinwsLogAnalyzerPage"]
