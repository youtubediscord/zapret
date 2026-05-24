"""Workflow полей редактируемых настроек profile."""

from __future__ import annotations

import re


_SIMPLE_RANGE_RE = re.compile(r"^-?(?P<mode>[nd])(?P<value>\d+)$", re.IGNORECASE)


def set_combo_by_data(combo, value: str) -> None:
    wanted = str(value or "").strip()
    for index in range(combo.count()):
        if str(combo.itemData(index) or "") == wanted:
            combo.setCurrentIndex(index)
            return


def sync_range_value_enabled(combo, value_edit) -> None:
    mode = str(combo.itemData(combo.currentIndex()) or "").strip()
    value_edit.setEnabled(mode not in {"a", "x"})
    if mode in {"a", "x"}:
        value_edit.clear()
    if mode == "custom":
        value_edit.setPlaceholderText("s1<d1")
    elif mode in {"n", "d"}:
        value_edit.setPlaceholderText("номер")
    else:
        value_edit.setPlaceholderText("")


def set_range_controls(combo, value_edit, expression: str) -> None:
    expr = str(expression or "").strip().lower()
    if expr in {"a", "x"}:
        set_combo_by_data(combo, expr)
        value_edit.clear()
        sync_range_value_enabled(combo, value_edit)
        return

    match = _SIMPLE_RANGE_RE.match(expr)
    if match:
        set_combo_by_data(combo, match.group("mode").lower())
        value_edit.setText(match.group("value"))
        sync_range_value_enabled(combo, value_edit)
        return

    set_combo_by_data(combo, "custom")
    value_edit.setText(expr)
    sync_range_value_enabled(combo, value_edit)


def range_expression_from_controls(combo, value_edit, *, default: str) -> str:
    mode = str(combo.itemData(combo.currentIndex()) or "").strip().lower()
    value = value_edit.text().strip()
    if mode in {"a", "x"}:
        return mode
    if mode in {"n", "d"}:
        return f"-{mode}{value}" if value.isdigit() else default
    if mode == "custom":
        return value or default
    return default
