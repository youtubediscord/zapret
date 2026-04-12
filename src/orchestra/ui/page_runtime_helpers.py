"""Runtime/language helper слой для Orchestra page."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QListWidgetItem

from orchestra.page_controller import OrchestraPageController
from orchestra import MAX_ORCHESTRA_LOGS
from ui.compat_widgets import set_tooltip


def protocol_filter_items(*, tr_fn) -> list[tuple[str, str]]:
    return [
        ("all", tr_fn("page.orchestra.filter.protocol.all", "Все")),
        ("tls", tr_fn("page.orchestra.filter.protocol.tls", "TLS")),
        ("http", tr_fn("page.orchestra.filter.protocol.http", "HTTP")),
        ("udp", tr_fn("page.orchestra.filter.protocol.udp", "UDP")),
        ("success", tr_fn("page.orchestra.filter.protocol.success", "SUCCESS")),
        ("fail", tr_fn("page.orchestra.filter.protocol.fail", "FAIL")),
    ]


def set_protocol_filter_items(*, combo, items: list[tuple[str, str]]) -> None:
    if combo is None:
        return

    selected = None
    try:
        selected = combo.currentData()
    except Exception:
        selected = None

    combo.blockSignals(True)
    combo.clear()
    for code, label in items:
        try:
            combo.addItem(label, userData=code)
        except TypeError:
            combo.addItem(label)
    combo.blockSignals(False)

    if selected is not None:
        for idx, (code, _) in enumerate(items):
            if code == selected:
                combo.setCurrentIndex(idx)
                break


def current_protocol_filter_code(*, combo) -> str:
    try:
        code = combo.currentData()
        if isinstance(code, str) and code:
            return code
    except Exception:
        pass

    value = combo.currentText().strip().lower()
    mapping = {
        "все": "all",
        "all": "all",
        "tls": "tls",
        "http": "http",
        "udp": "udp",
        "success": "success",
        "fail": "fail",
    }
    return mapping.get(value, "all")


def apply_orchestra_language(
    *,
    tr_fn,
    current_state: str,
    update_status,
    update_log_history,
    apply_log_filter,
    status_card_title,
    log_card_title,
    log_history_card_title,
    info_label,
    log_text,
    filter_label,
    log_filter_input,
    log_protocol_filter,
    clear_filter_btn,
    clear_log_btn,
    clear_learned_btn,
    clear_learned_pending: bool,
    log_history_desc,
    view_log_btn,
    delete_log_btn,
    clear_all_logs_btn,
) -> None:
    if status_card_title is not None:
        status_card_title.setText(tr_fn("page.orchestra.training_status", "Статус обучения"))
    if log_card_title is not None:
        log_card_title.setText(tr_fn("page.orchestra.log", "Лог обучения"))
    if log_history_card_title is not None:
        log_history_card_title.setText(
            tr_fn(
                "page.orchestra.log_history.title",
                "История логов (макс. {max_logs})",
                max_logs=MAX_ORCHESTRA_LOGS,
            )
        )

    if info_label is not None:
        info_label.setText(
            tr_fn(
                "page.orchestra.status.modes",
                "• IDLE - ожидание соединений\n"
                "• LEARNING - перебирает стратегии\n"
                "• RUNNING - работает на лучших стратегиях\n"
                "• UNLOCKED - переобучение (RST блокировка)",
            )
        )
    if log_text is not None:
        log_text.setPlaceholderText(
            tr_fn("page.orchestra.log.placeholder", "Логи обучения будут отображаться здесь...")
        )
    if filter_label is not None:
        filter_label.setText(tr_fn("page.orchestra.filter.label", "Фильтр:"))

    if log_filter_input is not None:
        log_filter_input.setPlaceholderText(
            tr_fn("page.orchestra.filter.domain.placeholder", "Домен (например: youtube.com)")
        )

    set_protocol_filter_items(combo=log_protocol_filter, items=protocol_filter_items(tr_fn=tr_fn))

    if clear_filter_btn is not None:
        set_tooltip(clear_filter_btn, tr_fn("page.orchestra.filter.clear.tooltip", "Сбросить фильтр"))

    if clear_log_btn is not None:
        clear_log_btn.setText(tr_fn("page.orchestra.button.clear_log", "Очистить лог"))

    if clear_learned_btn is not None:
        done_ru = "✓ Сброшено"
        done_en = "✓ Reset"
        current = clear_learned_btn.text()
        if clear_learned_pending:
            clear_learned_btn.setText(
                tr_fn("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!")
            )
        elif current in (done_ru, done_en):
            clear_learned_btn.setText(
                tr_fn("page.orchestra.button.clear_learning.done", "✓ Сброшено")
            )
        else:
            clear_learned_btn.setText(
                tr_fn("page.orchestra.button.clear_learning", "Сбросить обучение")
            )

    if log_history_desc is not None:
        log_history_desc.setText(
            tr_fn(
                "page.orchestra.log_history.desc",
                "Каждый запуск оркестратора создаёт новый лог с уникальным ID. Старые логи автоматически удаляются.",
            )
        )
    if view_log_btn is not None:
        view_log_btn.setText(tr_fn("page.orchestra.button.view_log", "Просмотреть"))
    if delete_log_btn is not None:
        delete_log_btn.setText(tr_fn("page.orchestra.button.delete_log", "Удалить"))
    if clear_all_logs_btn is not None:
        clear_all_logs_btn.setText(tr_fn("page.orchestra.button.clear_all_logs", "Очистить все"))

    update_status(current_state)
    update_log_history()
    apply_log_filter()


def append_log_line(*, text: str, full_log_lines: list[str], max_log_lines: int, matches_filter, log_text) -> list[str]:
    full_log_lines.append(text)
    if len(full_log_lines) > max_log_lines:
        full_log_lines = full_log_lines[-max_log_lines:]

    if matches_filter(text):
        log_text.append(text)
        cursor = log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        log_text.setTextCursor(cursor)
    return full_log_lines


def apply_log_filter_to_view(*, lines: list[str], domain_filter: str, protocol_filter: str, log_text) -> None:
    filtered_lines = OrchestraPageController.filter_lines(
        lines=lines,
        domain_filter=domain_filter,
        protocol_filter=protocol_filter,
    )
    log_text.clear()
    for line in filtered_lines:
        log_text.append(line)
    cursor = log_text.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    log_text.setTextCursor(cursor)


def update_log_history_view(*, runner, tr_fn, log_history_list) -> None:
    log_history_list.clear()

    logs = runner.get_log_history()
    plan = OrchestraPageController.build_log_history_plan(
        logs=logs,
        current_suffix_text=tr_fn("page.orchestra.log_history.current_suffix", " (текущий)"),
        none_text=tr_fn("page.orchestra.log_history.none", "  Нет сохранённых логов"),
    )

    for entry in plan.entries:
        item = QListWidgetItem(entry.text)
        item.setData(Qt.ItemDataRole.UserRole, entry.log_id)

        if entry.is_current:
            item.setForeground(Qt.GlobalColor.green)
        elif entry.is_placeholder:
            item.setForeground(Qt.GlobalColor.gray)

        log_history_list.addItem(item)
