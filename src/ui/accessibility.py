from __future__ import annotations

from types import MethodType

from PyQt6.QtCore import Qt


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
    _sync_spinbox_children_accessibility(widget, name=name, description=description)


def set_state_text(widget, text: object) -> None:
    """Записывает текстовое состояние, чтобы смысл не зависел от цвета/иконки."""

    value = _clean_text(text)
    if not value:
        return
    set_accessible_name(widget, value)
    _sync_spinbox_children_accessibility(widget, name=value, description=None)
    try:
        if _clean_text(widget.property("screenReaderStateText")) == value:
            return
    except Exception:
        pass
    try:
        widget.setProperty("screenReaderStateText", value)
    except Exception:
        pass


def _sync_spinbox_children_accessibility(
    widget,
    *,
    name: object | None,
    description: object | None,
) -> None:
    value = _clean_text(name)
    if widget is None or not value:
        return
    try:
        children = widget.findChildren(object)
    except Exception:
        return
    for child in children:
        try:
            object_name = str(child.objectName() or "")
        except Exception:
            object_name = ""
        child_type = type(child).__name__
        if object_name == "qt_spinbox_lineedit":
            set_accessible_name(child, value)
            if description is not None:
                set_accessible_description(child, description)
            continue
        if child_type != "SpinButton":
            continue
        try:
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception:
            pass


def set_item_accessible_text(item, text: object, *, description: object | None = None) -> None:
    """Задаёт текст для диктора у строки/ячейки Qt item-модели."""

    if item is None:
        return
    value = _clean_text(text)
    if value:
        try:
            item.setData(Qt.ItemDataRole.AccessibleTextRole, value)
        except Exception:
            pass
    if description is not None:
        description_value = _clean_text(description)
        if description_value:
            try:
                item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, description_value)
            except Exception:
                pass


def remove_line_edit_buttons_from_tab_order(line_edit) -> None:
    """Убирает служебные кнопки qfluentwidgets LineEdit/SearchLineEdit из Tab-порядка."""

    if line_edit is None:
        return
    try:
        children = line_edit.findChildren(object)
    except Exception:
        return
    for child in children:
        try:
            object_name = str(child.objectName() or "")
        except Exception:
            continue
        if object_name != "lineEditButton":
            continue
        try:
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception:
            pass


def remove_scrollbar_arrow_buttons_from_tab_order(widget) -> None:
    """Убирает служебные стрелки qfluentwidgets ScrollBar из Tab-порядка."""

    if widget is None:
        return
    try:
        children = widget.findChildren(object)
    except Exception:
        return
    for child in children:
        if type(child).__name__ != "ArrowButton":
            continue
        try:
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception:
            pass


def set_breadcrumb_accessibility(widget, parts: object) -> None:
    """Записывает путь навигации как обычный текст для диктора."""

    if widget is None:
        return
    cleaned_parts = [_clean_text(part) for part in tuple(parts or ())]
    visible_parts = [part for part in cleaned_parts if part]
    if not visible_parts:
        return
    text = f"Навигация: {' > '.join(visible_parts)}"
    set_control_accessibility(
        widget,
        name=text,
        description="Показывает путь до текущей страницы. Выберите пункт, чтобы вернуться назад.",
    )
    set_state_text(widget, text)


def enable_keyboard_click(widget) -> None:
    """Делает кликабельную карточку доступной через Tab, Enter и Пробел."""

    if widget is None:
        return
    try:
        if widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    except Exception:
        return
    try:
        if widget.property("_keyboardClickEnabled"):
            return
        widget.setProperty("_keyboardClickEnabled", True)
    except Exception:
        pass

    original_key_press = getattr(widget, "keyPressEvent", None)

    def _keyboard_click_key_press(self, event):  # noqa: ANN001
        try:
            key = event.key()
        except Exception:
            key = None
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            clicked = getattr(self, "clicked", None)
            emit = getattr(clicked, "emit", None)
            if emit is not None:
                emit()
                try:
                    event.accept()
                except Exception:
                    pass
                return
        if original_key_press is not None:
            return original_key_press(event)
        return None

    try:
        widget.keyPressEvent = MethodType(_keyboard_click_key_press, widget)
    except Exception:
        pass


def enable_keyboard_toggle(widget) -> None:
    """Делает переключатель доступным через Tab, Enter и Пробел."""

    if widget is None:
        return
    try:
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    except Exception:
        return
    try:
        if widget.property("_keyboardToggleEnabled"):
            return
        widget.setProperty("_keyboardToggleEnabled", True)
    except Exception:
        pass

    original_key_press = getattr(widget, "keyPressEvent", None)

    def _keyboard_toggle_key_press(self, event):  # noqa: ANN001
        try:
            key = event.key()
        except Exception:
            key = None
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            try:
                self.setChecked(not bool(self.isChecked()))
                event.accept()
                return
            except Exception:
                pass
        if original_key_press is not None:
            return original_key_press(event)
        return None

    try:
        widget.keyPressEvent = MethodType(_keyboard_toggle_key_press, widget)
    except Exception:
        pass


__all__ = [
    "enable_keyboard_click",
    "enable_keyboard_toggle",
    "remove_line_edit_buttons_from_tab_order",
    "remove_scrollbar_arrow_buttons_from_tab_order",
    "set_breadcrumb_accessibility",
    "set_accessible_description",
    "set_accessible_name",
    "set_control_accessibility",
    "set_item_accessible_text",
    "set_state_text",
]
