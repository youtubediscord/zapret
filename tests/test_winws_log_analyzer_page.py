from __future__ import annotations

from pathlib import Path

import pytest

from winws_log_analyzer.filters import filter_connections
from winws_log_analyzer.parser import parse_winws_log_file

FIXTURE = Path(__file__).parent / "fixtures" / "winws2_debug_sample.log"


@pytest.fixture(scope="module")
def result():
    return parse_winws_log_file(str(FIXTURE))


def test_filter_by_text(result):
    conns = filter_connections(result.connections, text="opera-api")
    assert len(conns) == 1
    assert conns[0].hostname == "merchandise.opera-api.com"

    conns = filter_connections(result.connections, text="85.172.")
    assert len(conns) == 1
    assert conns[0].remote_ip == "85.172.79.187"


def test_filter_only_with_hostname(result):
    conns = filter_connections(result.connections, only_with_hostname=True)
    assert [c.hostname for c in conns] == ["merchandise.opera-api.com"]


def test_filter_only_affected(result):
    conns = filter_connections(result.connections, only_affected=True)
    ips = {c.remote_ip for c in conns}
    # drop у 185.26.182.94, modified у 13.107.246.53
    assert ips == {"185.26.182.94", "13.107.246.53"}


def test_filter_no_criteria_returns_all(result):
    assert filter_connections(result.connections) == result.connections


def test_page_smoke_fills_tables(result, tmp_path, monkeypatch):
    # ЕДИНСТВЕННЫЙ тест файла, создающий страницу: повторное создание страницы
    # во втором тесте того же процесса ломает глобальный qconfig qfluentwidgets
    # при teardown (см. предупреждение в tests/conftest.py), поэтому проверка
    # комбобокса недавних логов тоже живёт здесь.
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    import winws_log_analyzer.ui.page as page_module

    (tmp_path / "zapret_winws2_debug_20260102_002451.log").write_text("x")
    (tmp_path / "Default_v1_game_filter_debug.log").write_text("x")
    (tmp_path / "orchestra_20260608_201046.log").write_text("x")
    (tmp_path / "zapret_log_2026-07-07_22-44-09.txt").write_text("x")
    (tmp_path / "tg_proxy.log").write_text("x")
    (tmp_path / "crashes.log").write_text("x")
    monkeypatch.setattr(page_module, "LOGS_FOLDER", str(tmp_path))

    page = page_module.WinwsLogAnalyzerPage()
    try:
        from PyQt6.QtCore import QUrl

        from config.urls import WINWS_LOG_ANALYZER_INFO_URL

        # Кнопка справки находится в строке заголовка и ведёт на нужную статью.
        assert page.layout.indexOf(page._ui.title_header) == 0
        assert page._ui.help_button.getUrl() == QUrl(WINWS_LOG_ANALYZER_INFO_URL)
        assert page._ui.help_button.accessibleName() == "Как это б#&^ь работает?"
        assert "инструкцию" in page._ui.help_button.accessibleDescription()

        # Комбобокс недавних логов показывает ТОЛЬКО debug-логи winws2.
        page._refresh_recent_combo()
        combo = page._ui.recent_combo
        items = sorted(combo.itemText(i) for i in range(combo.count()))
        assert items == [
            "Default_v1_game_filter_debug.log",
            "orchestra_20260608_201046.log",
            "zapret_winws2_debug_20260102_002451.log",
        ]

        # Страница принимает перетаскивание файлов.
        assert page.acceptDrops()

        request_id = page._runtime.next_request_id()
        page._on_parse_loaded(request_id, result)

        table = page._ui.connections_table
        assert table.rowCount() == len(result.connections)
        assert page._ui.summary_label.isVisible() or page._ui.summary_label.text()
        assert "Пакетов: 6" in page._ui.summary_label.text()

        # Фильтр «только с hostname» сужает таблицу до одной строки.
        page._ui.only_hostname_cb.setChecked(True)
        assert table.rowCount() == 1
        assert table.item(0, 0).text() == "merchandise.opera-api.com"

        # Выбор строки заполняет таблицу пакетов.
        table.selectRow(0)
        packets_table = page._ui.packets_table
        assert packets_table.rowCount() == 1
        assert packets_table.item(0, 0).text() == "59"
        assert packets_table.item(0, 8).text() == "drop"

        # Сброс выбора возвращает плейсхолдер, секция остаётся на месте.
        from winws_log_analyzer.ui.build import PACKETS_PLACEHOLDER_TITLE

        table.clearSelection()
        assert packets_table.rowCount() == 0
        assert packets_table.isVisibleTo(page)
        assert page._ui.packets_title.text() == PACKETS_PLACEHOLDER_TITLE
    finally:
        # Удаление виджета делает teardown из conftest — ручной deleteLater
        # здесь провоцирует гибель глобального qconfig (см. conftest).
        page.cleanup()


def test_dropped_log_path_accepts_only_local_text_files(tmp_path):
    from PyQt6.QtCore import QMimeData, QUrl
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from winws_log_analyzer.ui.page import WinwsLogAnalyzerPage

    log_file = tmp_path / "some_debug.log"
    log_file.write_text("x")
    exe_file = tmp_path / "tool.exe"
    exe_file.write_text("x")

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(log_file))])
    assert WinwsLogAnalyzerPage._dropped_log_path(mime) == str(log_file)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(exe_file))])
    assert WinwsLogAnalyzerPage._dropped_log_path(mime) == ""

    mime = QMimeData()
    mime.setText("не файл")
    assert WinwsLogAnalyzerPage._dropped_log_path(mime) == ""
