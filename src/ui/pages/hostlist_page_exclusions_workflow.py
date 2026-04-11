"""Workflow/helper'ы статусов exclusions/ipru для страницы Листы."""

from __future__ import annotations


def update_exclusions_status(label, editor, *, build_plan_fn, tr_fn) -> None:
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


def update_ipru_status(label, error_label, editor, *, build_plan_fn, tr_fn) -> None:
    text = editor.toPlainText()
    plan = build_plan_fn(text)
    label.setText(
        tr_fn(
            "page.hostlist.status.ipru_count",
            "📊 IP-исключений: {total} (база: {base}, пользовательские: {user})",
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
