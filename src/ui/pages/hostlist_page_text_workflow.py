"""Workflow/helper'ы текстовых редакторов для страницы Листы."""

from __future__ import annotations


def load_text_into_editor(editor, text: str) -> None:
    editor.blockSignals(True)
    try:
        editor.setPlainText(text)
    finally:
        editor.blockSignals(False)


def apply_normalized_text(editor, normalized_text: str, *, current_text: str, update_status_fn=None) -> bool:
    if normalized_text == current_text:
        return False

    cursor = editor.textCursor()
    position = cursor.position()
    editor.blockSignals(True)
    try:
        editor.setPlainText(normalized_text)
        cursor = editor.textCursor()
        cursor.setPosition(min(position, len(normalized_text)))
        editor.setTextCursor(cursor)
    finally:
        editor.blockSignals(False)

    if callable(update_status_fn):
        update_status_fn()
    return True


def update_domains_status(label, editor, *, build_plan_fn, tr_fn) -> None:
    text = editor.toPlainText()
    plan = build_plan_fn(text)
    label.setText(
        tr_fn(
            "page.hostlist.status.domains_full_count",
            "📊 Доменов: {total} (база: {base}, пользовательские: {user})",
            total=plan.total_count,
            base=plan.base_count,
            user=plan.user_count,
        )
    )


def update_ips_status(label, error_label, editor, *, build_plan_fn, tr_fn) -> None:
    text = editor.toPlainText()
    plan = build_plan_fn(text)

    label.setText(
        tr_fn(
            "page.hostlist.status.entries_count",
            "📊 Записей: {total} (база: {base}, пользовательские: {user})",
            total=plan.total_count,
            base=plan.base_count,
            user=plan.user_count,
        )
    )

    if error_label is None:
        return

    if plan.invalid_lines:
        error_label.setText(
            tr_fn(
                "page.hostlist.ips.error.invalid_format",
                "❌ Неверный формат: {items}",
                items=", ".join(item for _, item in plan.invalid_lines[:5]),
            )
        )
        error_label.show()
    else:
        error_label.hide()


def apply_add_plan(*, plan, input_widget, editor_widget, info_bar, window, tr_fn) -> bool:
    if plan.level == "warning" and info_bar:
        info_bar.warning(
            title=plan.title or tr_fn("common.error.title", "Ошибка"),
            content=plan.content,
            parent=window,
        )
        return False
    if plan.level == "info" and info_bar:
        info_bar.info(
            title=plan.title or tr_fn("page.hostlist.infobar.info", "Информация"),
            content=plan.content,
            parent=window,
        )
        return False
    if plan.new_text is not None:
        editor_widget.setPlainText(plan.new_text)
    if plan.clear_input and hasattr(input_widget, "clear"):
        input_widget.clear()
    if plan.level == "success" and info_bar:
        info_bar.success(
            title=plan.title or tr_fn("page.hostlist.infobar.added", "Добавлено"),
            content=plan.content,
            parent=window,
        )
    return True


def clear_editor_with_confirm(*, editor, message_box_cls, window, title: str, body: str) -> bool:
    text = editor.toPlainText().strip()
    if not text:
        return False

    if message_box_cls:
        box = message_box_cls(title, body, window)
        if not box.exec():
            return False

    editor.clear()
    return True
