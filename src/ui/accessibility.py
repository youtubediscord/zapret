from __future__ import annotations


def _clean_text(text: object) -> str:
    return " ".join(str(text or "").strip().split())


def _widget_text(widget) -> str:
    try:
        return _clean_text(widget.text())
    except Exception:
        return ""


def set_accessible_name(widget, text: object | None = None) -> bool:
    """Задаёт короткое имя элемента для экранного диктора."""

    if widget is None:
        return False
    value = _clean_text(_widget_text(widget) if text is None else text)
    if not value:
        return False
    try:
        if _clean_text(widget.accessibleName()) == value:
            return False
    except Exception:
        pass
    try:
        widget.setAccessibleName(value)
        return True
    except Exception:
        return False


def set_accessible_description(widget, text: object) -> bool:
    """Задаёт пояснение: что произойдёт или что значит элемент."""

    if widget is None:
        return False
    value = _clean_text(text)
    if not value:
        return False
    try:
        if _clean_text(widget.accessibleDescription()) == value:
            return False
    except Exception:
        pass
    try:
        widget.setAccessibleDescription(value)
        return True
    except Exception:
        return False


def set_control_accessibility(
    widget,
    *,
    name: object | None = None,
    description: object | None = None,
) -> None:
    """Заполняет имя и описание обычной кнопки, поля или переключателя."""

    set_accessible_name(widget, name)
    if description is not None:
        set_accessible_description(widget, description)


def set_state_text(widget, text: object) -> None:
    """Записывает текстовое состояние, чтобы смысл не зависел от цвета/иконки."""

    value = _clean_text(text)
    if not value:
        return
    set_accessible_name(widget, value)
    try:
        widget.setProperty("screenReaderStateText", value)
    except Exception:
        pass


__all__ = [
    "set_accessible_description",
    "set_accessible_name",
    "set_control_accessibility",
    "set_state_text",
]
